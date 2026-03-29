"""Claim decomposition agent — extracts verifiable statements and search queries."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.connectors.regolo_client import RegoloClient
from app.core.state import PipelineState
from app.services.analysis.json_utils import parse_llm_json
from app.utils.pipeline_trace import layer_tag

logger = logging.getLogger(__name__)


CLAIM_DECOMP_SYSTEM = """\
You are a fact-checking assistant. You decompose articles into verifiable claims \
and compose optimized search queries to check each claim on the web.

You will receive:
- ARTICLE TEXT (full or partial)
- ARTICLE METADATA (title, date, author — when available)

For each verifiable claim in the article, produce:
1. The atomic claim — a single, self-contained, verifiable fact
2. An optimized web search query to find evidence about this claim

Rules for claims:
- Extract up to 10 atomic, verifiable claims central to the article.
- Focus on facts with entities, dates, numbers, events, locations, decisions, appointments, official actions.
- Skip opinions, rhetoric, repetitions, generic background, non-verifiable statements.
- Each claim must be understandable WITHOUT reading the rest of the article — include the relevant context (who, what, where, when).
- Resolve relative temporal expressions using CURRENT DATE or article date when provided.
- Preserve the original language of the claim.
- Try to extract at least 7 claims if the article contains enough verifiable facts.

Rules for search queries:
- Concise: 4-12 words. Think like a journalist fact-checking: what would you search?
- Include key entities: full names of people, organizations, places.
- Include dates/years/months when the claim mentions them.
- Resolve relative dates like "today", "yesterday", "last year" using CURRENT DATE or article date.
- Include specific numbers or statistics when relevant.
- Use the language most likely to find results: English for international events, original language for local/national events.
- Do NOT use full sentences — use keyword-rich search phrases.
- Each query must be specific to its claim, not generic.

Return ONLY valid JSON as an array:
[
  {
    "claim": "<atomic claim in original language, self-contained with context>",
    "search_query": "<optimized web search query, 4-12 words>",
    "type": "<event|institutional|statistical|biographical|policy|other>",
    "checkability_score": <float 0.0-1.0>
  }
]
"""


class ClaimDecompositionAgent:
    """Extract claims from articles and compose search queries for each."""

    def __init__(self, settings: Settings, llm_client: RegoloClient | None = None) -> None:
        self.settings = settings
        self.llm = llm_client or RegoloClient(
            api_key=settings.regolo_api_key,
            base_url=settings.regolo_base_url,
            llm_model=settings.regolo_claim_model or settings.regolo_model,
            timeout_seconds=None if settings.request_timeout_seconds <= 0 else float(settings.request_timeout_seconds),
        )

    async def run(self, state: PipelineState) -> PipelineState:
        if state.input_type != "url":
            return state

        text = state.normalized_text or state.raw_content
        if not text.strip():
            state.claims = []
            return state

        logger.info("%s extracting claims + search queries from article", layer_tag("claims"))
        state.claims = await self.extract_claims(text, state)
        logger.info("%s extracted_claims=%d", layer_tag("claims"), len(state.claims))
        return state

    async def extract_claims(self, text: str, state: PipelineState | None = None) -> list[dict[str, Any]]:
        snippet = text[:8000]
        metadata_block = self._build_metadata_block(state)
        prompt = f"{metadata_block}Article text:\n\"\"\"\n{snippet}\n\"\"\""

        try:
            raw = await self.llm.generate_text(
                prompt=prompt,
                system_prompt=CLAIM_DECOMP_SYSTEM,
                max_tokens=2000,
                temperature=0.15,
            )
            parsed = parse_llm_json(raw)
            normalized = self._normalize_claim_rows(parsed)
            if normalized:
                return normalized
        except Exception as exc:
            logger.exception("%s claim decomposition failed: %r", layer_tag("claims"), exc)
            raise

        raise RuntimeError("Claim decomposition returned no usable claims")

    def _build_metadata_block(self, state: PipelineState | None) -> str:
        if not state:
            return ""
        parts: list[str] = []
        parts.append(f"Current date: {datetime.now(timezone.utc).date().isoformat()}")
        if state.article_title:
            parts.append(f"Title: {state.article_title}")
        if state.article_date:
            parts.append(f"Date: {state.article_date}")
        if state.article_author:
            parts.append(f"Author: {state.article_author}")
        if state.source_url:
            parts.append(f"URL: {state.source_url}")
        if not parts:
            return ""
        return "ARTICLE METADATA:\n" + "\n".join(parts) + "\n\n"

    def _normalize_claim_rows(self, payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, list):
            return []

        out: list[dict[str, Any]] = []
        max_claims = min(10, max(1, self.settings.max_claims_per_request))
        for index, item in enumerate(payload[:max_claims]):
            if isinstance(item, str):
                claim = item.strip()
                search_query = ""
                claim_type = "other"
                checkability = 0.6
            elif isinstance(item, dict):
                claim = str(item.get("claim", "")).strip()
                search_query = str(item.get("search_query", "")).strip()
                claim_type = str(item.get("type", "other")).strip() or "other"
                try:
                    checkability = float(item.get("checkability_score", 0.6))
                except (TypeError, ValueError):
                    checkability = 0.6
            else:
                continue

            if len(claim) < 20:
                continue

            out.append(
                {
                    "id": f"c{index + 1}",
                    "claim": claim,
                    "search_query": search_query or self._fallback_query(claim),
                    "type": claim_type,
                    "partial_verdict": "insufficient_evidence",
                    "partial_score": 0.0,
                    "checkability_score": round(max(0.0, min(1.0, checkability)), 2),
                }
            )
        return out

    def _fallback_query(self, claim: str) -> str:
        """Build a keyword search query from a claim when the LLM didn't provide one."""
        # Extract key tokens: capitalized words, numbers, years
        words = claim.split()
        keywords: list[str] = []
        for w in words:
            clean = re.sub(r"[^\w]", "", w)
            if not clean:
                continue
            # Keep: capitalized words (names/places), numbers, words > 4 chars
            if clean[0].isupper() or any(c.isdigit() for c in clean) or len(clean) > 4:
                if clean.lower() not in _QUERY_STOPWORDS:
                    keywords.append(clean)
        # Cap at 10 keywords
        return " ".join(keywords[:10]) if keywords else claim[:80]

    def _fallback_claims(self, text: str, state: PipelineState | None = None) -> list[dict[str, Any]]:
        sentences = self._split_sentences(text)
        ranked = sorted(sentences, key=self._sentence_priority, reverse=True)
        out: list[dict[str, Any]] = []
        for index, sentence in enumerate(ranked[: min(7, len(ranked))]):
            out.append(
                {
                    "id": f"c{index + 1}",
                    "claim": sentence,
                    "search_query": self._fallback_query(sentence),
                    "type": self._infer_claim_type(sentence),
                    "partial_verdict": "insufficient_evidence",
                    "partial_score": 0.0,
                    "checkability_score": round(min(0.85, max(0.45, self._sentence_priority(sentence))), 2),
                }
            )
        return out

    def _split_sentences(self, text: str) -> list[str]:
        chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
        sentences: list[str] = []
        for chunk in chunks:
            cleaned = " ".join(chunk.split()).strip(" -")
            if len(cleaned) >= 35:
                sentences.append(cleaned)
        return sentences

    def _sentence_priority(self, sentence: str) -> float:
        lowered = sentence.lower()
        score = 0.35
        if any(char.isdigit() for char in sentence):
            score += 0.15
        if any(word in lowered for word in ("ha", "have", "has", "will", "announced", "confirmed", "visit", "nomin", "appoint", "said")):
            score += 0.12
        if any(word in lowered for word in ("minister", "president", "pope", "governo", "government", "bce", "ecb", "istat")):
            score += 0.12
        if len(sentence.split()) >= 12:
            score += 0.08
        if re.search(r"\b(19|20)\d{2}\b", sentence):
            score += 0.08
        return min(score, 0.95)

    def _infer_claim_type(self, sentence: str) -> str:
        lowered = sentence.lower()
        if any(token in lowered for token in ("percent", "%", "istat", "gdp", "inflation", "pil", "tassi")):
            return "statistical"
        if any(token in lowered for token in ("government", "governo", "decree", "law", "europa", "minister", "president", "pope")):
            return "institutional"
        if any(token in lowered for token in ("visit", "meeting", "appointed", "nomin", "announced", "confirmed")):
            return "event"
        return "other"


_QUERY_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "was", "were", "are",
    "been", "being", "will", "would", "could", "should", "into", "about", "their", "which",
    "del", "della", "delle", "degli", "dello", "con", "per", "che", "sono", "era", "dalla",
    "dalle", "nella", "nelle", "alla", "alle", "una", "uno", "gli", "stato", "anche",
    "come", "dopo", "prima", "durante", "secondo", "tra", "ogni", "questo", "quella",
}
