"""AI-assisted query planning for retrieval-first fact-checking."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.connectors.regolo_client import RegoloClient
from app.core.state import PipelineState
from app.services.analysis.json_utils import parse_llm_json

logger = logging.getLogger(__name__)


QUERY_GEN_SYSTEM = """\
You are a search-query optimizer for fact-checking.
You will receive a text (short statement OR full article).
Your job: identify the 3 most important *verifiable facts* in the text and turn each into a concise search query.

Rules:
- Focus on concrete facts: names, numbers, dates, events, locations.
- Skip opinions, adjectives, and vague assertions.
- One query in ENGLISH, one in the original language, one mixed/alternate angle.
- Resolve relative time expressions using the CURRENT DATE if provided.
- Never invent absolute years or dates that are not implied by the text or the current date.
- Return ONLY a JSON array of 3 strings. No markdown, no explanation."""

CLAIM_QUERY_GEN_SYSTEM = """\
You are a search-query optimizer for claim-centric fact-checking.
You will receive:
- ARTICLE CONTEXT
- ARTICLE METADATA
- EXTRACTED CLAIMS
- OPTIONAL EXISTING SEARCH QUERIES

Your job:
- Produce exactly one high-quality Tavily web search query for each claim, in the SAME ORDER.
- Each query must be self-contained and include enough context to identify the claim correctly.

Rules:
- Keep queries concise but not vague: typically 5-14 words.
- Include the key subject, predicate, place, and date/year when relevant.
- Resolve relative dates such as "today", "yesterday", "last year", "this month" using CURRENT DATE or article date.
- Never hallucinate years, dates, ages, or places not grounded in the claim/context.
- If a claim is ambiguous without article context, add the missing entity or event context.
- Use the existing search query as a seed only if it is already good; otherwise improve it.
- Prefer the original language for local/national stories and English for international events.
- Do not return explanations.

Return ONLY valid JSON as an array of strings, one query per claim, same order as input."""


QUERY_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "was", "were", "are",
    "been", "being", "will", "would", "could", "should", "into", "about", "their", "which",
    "del", "della", "delle", "degli", "dello", "con", "per", "che", "sono", "era", "dalla",
    "dalle", "nella", "nelle", "alla", "alle", "una", "uno", "gli", "stato", "anche",
    "come", "dopo", "prima", "durante", "secondo", "tra", "ogni", "questo", "quella",
}


class QueryPlanningAgent:
    """Generate search queries using Regolo."""

    def __init__(self, settings: Settings, llm_client: RegoloClient | None = None) -> None:
        self.settings = settings
        self.llm = llm_client or RegoloClient(
            api_key=settings.regolo_api_key,
            base_url=settings.regolo_base_url,
            llm_model=settings.regolo_query_model or settings.regolo_model,
            timeout_seconds=None if settings.request_timeout_seconds <= 0 else float(settings.request_timeout_seconds),
        )

    async def run(self, state: PipelineState) -> PipelineState:
        text = state.normalized_text or state.raw_content
        state.generated_queries = await self.generate_queries(text, claims=state.claims, state=state)
        logger.info("    generated_queries=%d", len(state.generated_queries))
        return state

    async def generate_queries(
        self,
        text: str,
        *,
        claims: list[dict[str, Any]] | None = None,
        state: PipelineState | None = None,
    ) -> list[str]:
        claim_rows = claims or []
        snippet = text[:3000]
        if claim_rows:
            prompt = self._build_claim_prompt(text=snippet, claims=claim_rows, state=state)
            system_prompt = CLAIM_QUERY_GEN_SYSTEM
            max_tokens = min(1800, 220 * max(1, len(claim_rows)))
        else:
            today = datetime.now(timezone.utc).date().isoformat()
            prompt = f'CURRENT DATE: {today}\n\nText to fact-check:\n"""\n{snippet}\n"""'
            system_prompt = QUERY_GEN_SYSTEM
            max_tokens = 300
        try:
            raw = await self.llm.generate_text(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=0.2,
            )
            parsed = parse_llm_json(raw)
            if isinstance(parsed, list) and parsed:
                queries = self._normalize_query_rows(parsed, len(claim_rows) if claim_rows else 3)
                if queries:
                    if claim_rows and len(queries) != len(claim_rows):
                        raise RuntimeError(
                            f"Query planner returned {len(queries)} queries for {len(claim_rows)} claims"
                        )
                    return self._dedupe_queries(queries) if not claim_rows else queries
        except Exception as exc:
            logger.exception("    query gen failed: %r", exc)
            raise
        raise RuntimeError("Query planner returned no usable queries")

    def fallback_queries(
        self,
        text: str,
        *,
        claims: list[dict[str, Any]] | None = None,
        state: PipelineState | None = None,
    ) -> list[str]:
        if claims:
            claim_queries: list[str] = []
            for claim in claims:
                query = self._fallback_claim_query(claim, state=state)
                if query:
                    claim_queries.append(query)
            if claim_queries:
                return claim_queries
        cleaned = " ".join((text or "").split())
        if not cleaned:
            return []
        snippet = cleaned[:300]
        return [snippet]

    def _build_claim_prompt(
        self,
        *,
        text: str,
        claims: list[dict[str, Any]],
        state: PipelineState | None,
    ) -> str:
        metadata_lines: list[str] = []
        metadata_lines.append(f"Current date: {datetime.now(timezone.utc).date().isoformat()}")
        if state:
            if state.article_title:
                metadata_lines.append(f"Title: {state.article_title}")
            if state.article_date:
                metadata_lines.append(f"Date: {state.article_date}")
            if state.article_author:
                metadata_lines.append(f"Author: {state.article_author}")
            if state.country:
                metadata_lines.append(f"Country hint: {state.country}")
            if state.topic:
                metadata_lines.append(f"Topic hint: {state.topic}")

        metadata_block = ""
        if metadata_lines:
            metadata_block = "ARTICLE METADATA:\n" + "\n".join(metadata_lines) + "\n\n"

        return (
            f"{metadata_block}"
            f"ARTICLE CONTEXT:\n\"\"\"\n{text}\n\"\"\"\n\n"
            "CLAIMS TO SEARCH:\n"
            f"{self._claim_context(claims)}"
        )

    def _claim_context(self, claims: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for claim in claims:
            lines.append(
                f'- [{claim.get("type", "other")}] {claim.get("claim", "")} '
                f'(checkability={claim.get("checkability_score", 0.0)}, '
                f'seed_query={claim.get("search_query", "") or "none"})'
            )
        return "\n".join(lines)

    def _normalize_query_rows(self, payload: list[Any], limit: int) -> list[str]:
        queries: list[str] = []
        for item in payload[:limit]:
            if isinstance(item, str):
                value = item
            elif isinstance(item, dict):
                value = str(next(iter(item.values()))) if item else ""
            else:
                value = str(item)
            value = " ".join(value.split()).strip()
            if value:
                queries.append(value)
        return queries

    def _fallback_claim_query(self, claim: dict[str, Any], *, state: PipelineState | None) -> str:
        seed_query = " ".join(str(claim.get("search_query", "")).split()).strip()
        claim_text = " ".join(str(claim.get("claim", "")).split()).strip()
        if seed_query:
            query = seed_query
        else:
            query = self._keywords_from_text(claim_text)

        year = self._extract_year(claim_text, state=state) or (state.article_date[:4] if state and state.article_date else "")
        title_keywords = self._keywords_from_text(state.article_title, limit=4) if state and state.article_title else ""

        if year and year not in query:
            query = f"{query} {year}".strip()
        if title_keywords:
            overlap = set(query.lower().split()) & set(title_keywords.lower().split())
            if len(overlap) < 2:
                query = f"{query} {title_keywords}".strip()

        return " ".join(query.split()[:14]).strip()

    def _keywords_from_text(self, text: str, limit: int = 10) -> str:
        if not text:
            return ""
        keywords: list[str] = []
        for raw in text.split():
            token = re.sub(r"[^\w]", "", raw)
            if not token:
                continue
            lowered = token.lower()
            if lowered in QUERY_STOPWORDS:
                continue
            if token[0].isupper() or any(ch.isdigit() for ch in token) or len(token) > 4:
                keywords.append(token)
        return " ".join(keywords[:limit])

    def _extract_year(self, text: str, *, state: PipelineState | None = None) -> str:
        match = re.search(r"\b(19|20)\d{2}\b", text or "")
        if match:
            return match.group(0)

        lowered = (text or "").lower()
        reference_year = None
        if state and state.article_date[:4].isdigit():
            reference_year = int(state.article_date[:4])
        else:
            reference_year = datetime.now(timezone.utc).year

        if any(token in lowered for token in ("l'anno scorso", "anno scorso", "last year")):
            return str(reference_year - 1)
        if any(token in lowered for token in ("quest'anno", "questo anno", "this year")):
            return str(reference_year)
        if any(token in lowered for token in ("prossimo anno", "next year")):
            return str(reference_year + 1)
        return ""

    def _dedupe_queries(self, queries: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for query in queries:
            normalized = query.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            out.append(query)
        return out
