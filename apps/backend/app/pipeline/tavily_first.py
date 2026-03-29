"""
Tavily-First Fact-Checking Engine with Cascade Search.

Pipeline:
  1. LLM estrae i fatti chiave e genera query per Tavily
  2. Cascade Search (Tier 1 primary → Tier 2 broad)
  3. LLM cross-check: confronta TUTTO il testo vs evidenze Tavily
  4. Produce verdict, truth_score, sources, explanation

Nessuna logica di claims: il testo viene verificato come blocco unico.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any
from urllib.parse import urlparse

from app.config import Settings
from app.core.state import PipelineState
from app.connectors.tavily_search import tavily_search
from app.connectors.tavily_extract import tavily_extract
from app.connectors.regolo_client import RegoloClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tier 1 domains: primary/institutional sources
# ---------------------------------------------------------------------------

TIER1_DOMAINS = [
    "reuters.com", "apnews.com", "afp.com",
    "bbc.com", "bbc.co.uk", "nytimes.com", "washingtonpost.com",
    "theguardian.com", "economist.com", "ft.com", "lemonde.fr",
    "ansa.it", "adnkronos.com", "ilsole24ore.com", "corriere.it",
    "repubblica.it", "rainews.it", "agi.it", "open.online",
    "europa.eu", "who.int", "un.org", "imf.org", "worldbank.org",
    "ecb.europa.eu", "istat.it", "governo.it", "camera.it",
    "snopes.com", "factcheck.org", "politifact.com",
    "pagellapolitica.it", "facta.news", "butac.it",
    "nature.com", "science.org", "pubmed.ncbi.nlm.nih.gov",
]

BLACKLIST_DOMAINS = [
    "reddit.com", "quora.com", "medium.com", "twitter.com", "x.com",
    "facebook.com", "instagram.com", "tiktok.com", "pinterest.com",
    "youtube.com", "linkedin.com", "tumblr.com",
    "wikipedia.org",
    "amazon.com", "ebay.com", "alibaba.com",
    "blogspot.com", "wordpress.com",
]

TIER1_MIN_USEFUL = 2
TIER2_RELEVANCE_THRESHOLD = 0.20


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

QUERY_GEN_SYSTEM = """\
You are a search-query optimizer for fact-checking.
You will receive a text (short statement OR full article).
Your job: identify the 3 most important *verifiable facts* in the text and turn each into a concise search query.

Rules:
- Focus on concrete facts: names, numbers, dates, events, locations.
- Skip opinions, adjectives, and vague assertions.
- One query in ENGLISH, one in the original language, one mixed/alternate angle.
- Return ONLY a JSON array of 3 strings. No markdown, no explanation."""

CROSSCHECK_SYSTEM_TIER1 = """\
You are a rigorous fact-checker. You will receive:
- TEXT: the full article or statement to verify
- SOURCES: evidence from PRIMARY/INSTITUTIONAL web sources

Your job: compare the TEXT against the SOURCES and determine the overall truthfulness.
Analyze the text AS A WHOLE — do NOT split it into individual claims.
Check every verifiable fact (names, numbers, dates, events) against the sources.
If some facts are confirmed and others are not, reflect that in the score.

Respond with ONLY valid JSON (no markdown, no extra text):
{
  "truth_score": <integer 0-100>,
  "confidence_score": <float 0.0-1.0>,
  "verdict": "<verified|mostly_verified|mixed|misleading|mostly_false|false|insufficient_evidence>",
  "explanation": {
    "summary": "<2-3 sentence overall verdict>",
    "why": "<main reasons for the verdict>",
    "supporting_evidence": ["<facts confirmed by sources>"],
    "contradicting_evidence": ["<facts contradicted by sources>"],
    "source_analysis": ["<one-line assessment per source used>"],
    "temporal_context": "<time-related context if relevant>",
    "caveats": ["<limitations>"]
  },
  "per_source": [
    {
      "source_index": <0-based>,
      "stance": "<supporting|contradicting|neutral>",
      "relevance": <0.0-1.0>,
      "key_excerpt": "<most relevant quote, max 200 chars>"
    }
  ]
}"""

CROSSCHECK_SYSTEM_TIER2 = """\
You are a rigorous fact-checker. You will receive:
- TEXT: the full article or statement to verify
- SOURCES: evidence from BROAD web search (local newspapers, niche sites, blogs, lesser-known outlets)

Your job: compare the TEXT against the SOURCES and determine the overall truthfulness.
Analyze the text AS A WHOLE — do NOT split it into individual claims.

Because these are NOT primary sources, also evaluate each source's tone:
- Factual news report (dateline, quotes, attribution) → more reliable
- Opinion/editorial/blog → less reliable
- Local outlet covering a local event → can be reliable for local facts

Confidence rules:
- Cap confidence_score at 0.65 max (only non-primary sources available)
- ALWAYS add this caveat: "Confirmed by local/sector sources only; not yet corroborated by major media."

Respond with ONLY valid JSON (no markdown, no extra text):
{
  "truth_score": <integer 0-100>,
  "confidence_score": <float 0.0-0.65>,
  "verdict": "<verified|mostly_verified|mixed|misleading|mostly_false|false|insufficient_evidence>",
  "explanation": {
    "summary": "<2-3 sentence verdict — mention source tier>",
    "why": "<main reasons, noting source quality>",
    "supporting_evidence": ["<facts confirmed>"],
    "contradicting_evidence": ["<facts contradicted>"],
    "source_analysis": ["<per source: name, type, tone, reliability>"],
    "temporal_context": "<time context>",
    "caveats": ["Confirmed by local/sector sources only; not yet corroborated by major media."]
  },
  "per_source": [
    {
      "source_index": <0-based>,
      "stance": "<supporting|contradicting|neutral>",
      "relevance": <0.0-1.0>,
      "key_excerpt": "<most relevant quote, max 200 chars>"
    }
  ]
}"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url[:60]


def _domain_reliability(domain: str) -> float:
    d = domain.lower()
    if any(x in d for x in [".gov", ".gob."]):
        return 0.92
    if any(x in d for x in [".edu", ".ac."]):
        return 0.87
    if any(x in d for x in [".int", ".europa.eu", "un.org", "who.int"]):
        return 0.90
    if any(x in d for x in [
        "reuters", "apnews", "bbc", "nytimes", "washingtonpost",
        "theguardian", "lemonde", "ansa.it", "ilsole24ore",
        "corriere", "repubblica", "nature.com", "science.org",
    ]):
        return 0.82
    if d.endswith(".org"):
        return 0.70
    return 0.60


def _source_tier(reliability: float) -> str:
    if reliability >= 0.80:
        return "A"
    if reliability >= 0.65:
        return "B"
    return "C"


def _parse_llm_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for pattern in [r"\{[\s\S]*\}", r"\[[\s\S]*\]"]:
        m = re.search(pattern, text)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                continue
    return None


def _to_str_list(items: list) -> list[str]:
    """Coerce list items to strings (LLM sometimes returns dicts)."""
    out = []
    for item in (items or []):
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            for key in ("description", "analysis", "text", "summary", "key_excerpt"):
                if key in item:
                    out.append(str(item[key]))
                    break
            else:
                out.append(json.dumps(item, ensure_ascii=False))
        else:
            out.append(str(item))
    return out


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class TavilyFirstEngine:
    """Fact-checking engine: Tavily cascade search + LLM cross-check.
    No claims — the full text is verified as one block."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = RegoloClient(
            api_key=settings.regolo_api_key,
            base_url=settings.regolo_base_url,
            llm_model=settings.regolo_model,
        )

    async def run(self, state: PipelineState) -> PipelineState:
        text = state.normalized_text or state.raw_content
        if not text.strip():
            state.verdict = "insufficient_evidence"
            state.errors.append("tavily_first: empty input")
            return state

        logger.info("    text length: %d chars", len(text))

        # --- 1. Generate search queries from the full text ---
        t0 = time.time()
        queries = await self._generate_queries(text)
        state.timings["query_generation"] = round(time.time() - t0, 3)
        logger.info("    queries: %s (%.3fs)", queries, state.timings["query_generation"])

        # --- 2. Cascade search ---
        t0 = time.time()
        results, search_tier = await self._cascade_search(queries)
        state.timings["tavily_search"] = round(time.time() - t0, 3)
        logger.info("    results: %d (tier=%s, %.3fs)", len(results), search_tier, state.timings["tavily_search"])

        if not results:
            state.verdict = "insufficient_evidence"
            state.truth_score = 0
            state.confidence_score = 0
            state.explanation = {
                "summary": "No evidence found from any web source.",
                "why": "Both primary and broad searches returned no results.",
                "supporting_evidence": [], "contradicting_evidence": [],
                "source_analysis": [], "temporal_context": "",
                "caveats": ["No web sources found to verify this content."],
            }
            return state

        # --- 2b. Extract full content where missing ---
        t0 = time.time()
        results = await self._enrich_content(results, text)
        state.timings["tavily_extract"] = round(time.time() - t0, 3)

        # --- 3. LLM cross-check (full text vs sources) ---
        t0 = time.time()
        analysis = await self._cross_check(text, results, search_tier)
        state.timings["llm_crosscheck"] = round(time.time() - t0, 3)
        logger.info("    cross-check done (%.3fs)", state.timings["llm_crosscheck"])

        # --- 4. Build state ---
        self._build_state(state, results, analysis, search_tier)
        return state

    # ------------------------------------------------------------------
    # Query generation
    # ------------------------------------------------------------------

    async def _generate_queries(self, text: str) -> list[str]:
        # Truncate very long articles for the query-gen prompt
        snippet = text[:3000]
        try:
            raw = await self.llm.generate_text(
                prompt=f'Text to fact-check:\n"""\n{snippet}\n"""',
                system_prompt=QUERY_GEN_SYSTEM,
                max_tokens=300,
                temperature=0.2,
            )
            parsed = _parse_llm_json(raw)
            if isinstance(parsed, list) and parsed:
                queries = []
                for q in parsed[:3]:
                    if isinstance(q, str):
                        queries.append(q)
                    elif isinstance(q, dict):
                        # LLM returned {"en": "...", "it": "..."} — pick first value
                        queries.append(str(next(iter(q.values()))))
                    else:
                        queries.append(str(q))
                return queries
        except Exception as exc:
            logger.warning("    query gen failed: %s", exc)
        # Fallback: first 300 chars as query
        return [text[:300]]

    # ------------------------------------------------------------------
    # Cascade search
    # ------------------------------------------------------------------

    async def _cascade_search(
        self, queries: list[str],
    ) -> tuple[list[dict[str, Any]], str]:

        # Tier 1
        t1 = await self._tavily_multi(queries, include_domains=TIER1_DOMAINS)
        logger.info("    tier1: %d", len(t1))
        if len(t1) >= TIER1_MIN_USEFUL:
            return t1[:5], "tier1"

        # Tier 2
        t2 = await self._tavily_multi(queries, exclude_domains=BLACKLIST_DOMAINS)
        t2_useful = [r for r in t2 if r.get("score", 0) >= TIER2_RELEVANCE_THRESHOLD]
        logger.info("    tier2: %d total, %d useful", len(t2), len(t2_useful))

        if t1 and t2_useful:
            seen = {r.get("url") for r in t1}
            merged = list(t1)
            for r in t2_useful:
                if r.get("url") not in seen:
                    seen.add(r.get("url"))
                    r["_tier"] = "tier2"
                    merged.append(r)
            return merged[:5], "mixed"

        if t2_useful:
            for r in t2_useful:
                r["_tier"] = "tier2"
            return t2_useful[:5], "tier2"

        # Last resort: best of anything
        everything = t1 + t2
        everything.sort(key=lambda r: r.get("score", 0), reverse=True)
        if everything:
            for r in everything:
                if r not in t1:
                    r["_tier"] = "tier2"
            return everything[:5], "tier2"

        return [], "tier1"

    async def _tavily_multi(
        self,
        queries: list[str],
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for q in queries:
            data = await tavily_search(
                query=q,
                search_depth="advanced",
                max_results=5,
                include_raw_content=True,
                include_answer="basic",
                auto_parameters=True,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
                topic="news",
            )
            for r in data.get("results", []):
                url = r.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    out.append(r)
        out.sort(key=lambda r: r.get("score", 0), reverse=True)
        return out

    # ------------------------------------------------------------------
    # Content enrichment
    # ------------------------------------------------------------------

    async def _enrich_content(
        self, results: list[dict[str, Any]], text: str,
    ) -> list[dict[str, Any]]:
        urls_need = []
        idx_map: dict[str, int] = {}
        for i, r in enumerate(results):
            raw = r.get("raw_content") or ""
            content = r.get("content") or ""
            if len(raw) < 100 and len(content) < 100:
                url = r.get("url", "")
                if url:
                    urls_need.append(url)
                    idx_map[url] = i

        if urls_need:
            try:
                data = await tavily_extract(
                    urls=urls_need[:5],
                    query=text[:300],
                    chunks_per_source=3,
                )
                for er in data.get("results", []):
                    idx = idx_map.get(er.get("url", ""))
                    if idx is not None and er.get("raw_content"):
                        results[idx]["raw_content"] = er["raw_content"]
            except Exception as exc:
                logger.warning("    extract failed: %s", exc)
        return results

    # ------------------------------------------------------------------
    # LLM cross-check
    # ------------------------------------------------------------------

    async def _cross_check(
        self, text: str, results: list[dict[str, Any]], search_tier: str,
    ) -> dict[str, Any]:

        # Build source context — use more content per source
        sources_block = ""
        for i, r in enumerate(results):
            domain = _domain_from_url(r.get("url", ""))
            tier_tag = "PRIMARY" if r.get("_tier") != "tier2" and search_tier != "tier2" else "BROAD"
            body = r.get("raw_content") or r.get("content") or ""
            body = body[:2000]  # generous per-source limit
            sources_block += (
                f"\n--- SOURCE {i} [{domain}] ({tier_tag}) ---\n"
                f"Title: {r.get('title', '')}\n"
                f"URL: {r.get('url', '')}\n"
                f"Content:\n{body}\n"
            )

        # Truncate user text to fit in context
        user_text = text[:4000]
        prompt = (
            f"TEXT TO VERIFY:\n\"\"\"\n{user_text}\n\"\"\"\n\n"
            f"SOURCES FROM WEB SEARCH:\n{sources_block}\n\n"
            "Produce your fact-check verdict as JSON."
        )
        system = CROSSCHECK_SYSTEM_TIER1 if search_tier == "tier1" else CROSSCHECK_SYSTEM_TIER2

        try:
            raw = await self.llm.generate_text(
                prompt=prompt,
                system_prompt=system,
                max_tokens=2000,
                temperature=0.1,
            )
            parsed = _parse_llm_json(raw)
            if isinstance(parsed, dict) and "truth_score" in parsed:
                return parsed
        except Exception as exc:
            logger.error("    cross-check failed: %s", exc)

        return self._fallback(results)

    def _fallback(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        if not results:
            return {
                "truth_score": 0, "confidence_score": 0.0,
                "verdict": "insufficient_evidence",
                "explanation": {
                    "summary": "Unable to verify: no sources.", "why": "No results.",
                    "supporting_evidence": [], "contradicting_evidence": [],
                    "source_analysis": [], "temporal_context": "",
                    "caveats": ["LLM analysis unavailable."],
                },
                "per_source": [],
            }
        avg = sum(r.get("score", 0.5) for r in results) / len(results)
        score = max(0, min(100, int(avg * 80 + 10)))
        for thr, v in [(85, "verified"), (70, "mostly_verified"), (55, "mixed"),
                       (40, "misleading"), (25, "mostly_false"), (0, "false")]:
            if score >= thr:
                verdict = v
                break
        else:
            verdict = "insufficient_evidence"
        return {
            "truth_score": score,
            "confidence_score": round(min(len(results) / 5, 1.0) * 0.6, 2),
            "verdict": verdict,
            "explanation": {
                "summary": f"Fallback analysis from {len(results)} sources.",
                "why": "LLM unavailable.", "supporting_evidence": [],
                "contradicting_evidence": [],
                "source_analysis": [f"{_domain_from_url(r.get('url',''))}: {r.get('score',0):.2f}" for r in results],
                "temporal_context": "", "caveats": ["Fallback scoring."],
            },
            "per_source": [
                {"source_index": i, "stance": "neutral", "relevance": r.get("score", 0.5), "key_excerpt": ""}
                for i, r in enumerate(results)
            ],
        }

    # ------------------------------------------------------------------
    # Build PipelineState (NO claims)
    # ------------------------------------------------------------------

    def _build_state(
        self,
        state: PipelineState,
        results: list[dict[str, Any]],
        analysis: dict[str, Any],
        search_tier: str,
    ) -> None:

        # No claims — empty list
        state.claims = []

        per_source = {ps.get("source_index", -1): ps for ps in analysis.get("per_source", [])}

        sources_used = []
        scored_evidence = []
        contradictions = []

        for i, r in enumerate(results):
            url = r.get("url", "")
            domain = _domain_from_url(url)
            reliability = _domain_reliability(domain)
            tier = _source_tier(reliability)
            sid = f"s{i+1}"
            is_primary = r.get("_tier") != "tier2" and search_tier != "tier2"

            sources_used.append({
                "source_id": sid,
                "source_name": domain,
                "source_type": "primary_media" if is_primary else "local_media",
                "url": url,
                "tier": tier,
                "source_reliability_score": reliability,
                "dimensions": {
                    "domain_trust": reliability,
                    "relevance": r.get("score", 0.5),
                    "is_primary": 1.0 if is_primary else 0.0,
                },
            })

            ps = per_source.get(i, {})
            stance = ps.get("stance", "neutral")
            relevance = ps.get("relevance", r.get("score", 0.5))
            excerpt = ps.get("key_excerpt", "") or (r.get("content") or "")[:300]

            scored_evidence.append({
                "source_id": sid,
                "stance": stance,
                "evidence_score": round(0.5 * relevance + 0.3 * reliability + 0.2 * r.get("score", 0.5), 3),
                "excerpt": excerpt[:400],
            })

            if stance == "contradicting":
                contradictions.append({
                    "claim_id": "",
                    "type": "source_conflict",
                    "description": f"{domain}: {excerpt[:200]}",
                    "severity": round(relevance * reliability, 2),
                })

        state.sources_used = sources_used
        state.scored_evidence = scored_evidence
        state.contradictions = contradictions

        # Scores with tier-based confidence cap
        state.truth_score = max(0, min(100, analysis.get("truth_score", 0)))
        raw_conf = analysis.get("confidence_score", 0.0)
        cap = {"tier1": 1.0, "mixed": 0.80, "tier2": 0.65}.get(search_tier, 1.0)
        state.confidence_score = max(0.0, min(cap, raw_conf))
        state.verdict = analysis.get("verdict", "insufficient_evidence")

        logger.info(
            "    verdict=%s score=%d confidence=%.2f (raw=%.2f cap=%.2f tier=%s)",
            state.verdict, state.truth_score, state.confidence_score, raw_conf, cap, search_tier,
        )

        # Explanation
        expl = analysis.get("explanation", {})
        caveats = _to_str_list(expl.get("caveats", []))
        tier_caveats = {
            "tier2": "Verified using local/sector sources only. Not yet corroborated by major international media.",
            "mixed": "Partially verified by primary sources; some evidence comes from local/sector outlets.",
        }
        if search_tier in tier_caveats:
            ct = tier_caveats[search_tier]
            if not any(ct[:30] in c for c in caveats):
                caveats.insert(0, ct)

        state.explanation = {
            "summary": str(expl.get("summary", "")),
            "why": str(expl.get("why", "")),
            "supporting_evidence": _to_str_list(expl.get("supporting_evidence", [])),
            "contradicting_evidence": _to_str_list(expl.get("contradicting_evidence", [])),
            "source_analysis": _to_str_list(expl.get("source_analysis", [])),
            "temporal_context": str(expl.get("temporal_context", "")),
            "caveats": caveats,
        }

        # Lightweight linguistic risk
        low = (state.normalized_text or state.raw_content).lower()
        markers = ["shock", "bomba", "incredibile", "assurdo", "explosive", "breaking"]
        found = [w for w in markers if w in low]
        state.linguistic_risk = {
            "sensationalism_score": min(len(found) * 0.25, 1.0),
            "emotional_tone_score": 0.0,
            "attribution_risk": 0.0,
            "uncertainty_score": 0.0,
            "manipulation_markers": found,
        }
