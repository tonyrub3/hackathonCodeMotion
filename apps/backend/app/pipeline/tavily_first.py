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

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from app.config import Settings
from app.core.state import PipelineState
from app.agents.query_planning_agent import QueryPlanningAgent
from app.connectors.tavily_search import tavily_search
from app.connectors.tavily_extract import tavily_extract
from app.connectors.regolo_client import RegoloClient
from app.services.analysis.crosscheck import CrossCheckAnalysisLayer
from app.services.retrieval.domain_policy import BLACKLIST_DOMAINS, TIER1_DOMAINS, TRUSTED_DOMAINS
from app.services.retrieval.search_profile import TavilySearchProfileBuilder
from app.services.scoring.evidence_scoring import EvidenceScoringLayer
from app.services.scoring.source_scoring import SourceScoringLayer
from app.utils.pipeline_trace import layer_tag

logger = logging.getLogger(__name__)


TIER1_MIN_USEFUL = 2
TIER2_RELEVANCE_THRESHOLD = 0.20

RECENT_MARKERS_STRONG = (
    "today", "yesterday", "breaking", "latest", "just", "hours ago",
    "oggi", "ieri", "ultim'ora", "appena", "ore fa",
)
RECENT_MARKERS_SOFT = (
    "this week", "this month", "current", "currently", "now", "recent",
    "questa settimana", "questo mese", "attuale", "attualmente", "recente",
)
NEWS_HINTS = (
    "election", "minister", "government", "war", "earthquake", "visit", "appointed",
    "president", "pope", "sports", "match", "breaking", "ministero", "governo",
    "guerra", "terremoto", "visita", "nominato", "presidente", "papa", "partita",
)
FINANCE_HINTS = (
    "stock", "stocks", "market", "markets", "nasdaq", "dow jones", "s&p", "bond",
    "bonds", "inflation", "gdp", "earnings", "revenue", "interest rate", "rates",
    "crypto", "bitcoin", "ethereum", "share price", "fed", "ecb", "inflazione",
    "pil", "mercato", "mercati", "azioni", "obbligazioni", "tassi", "borsa",
    "ricavi", "utili", "criptovalute",
)
TOPIC_ALIASES = {
    "politics": "news",
    "politica": "news",
    "world": "news",
    "cronaca": "news",
    "sport": "news",
    "sports": "news",
    "current_events": "news",
    "attualita": "news",
    "attualità": "news",
    "economy": "finance",
    "economia": "finance",
    "business": "finance",
    "finance": "finance",
    "finanza": "finance",
    "markets": "finance",
    "mercati": "finance",
}
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "was", "were", "are",
    "del", "della", "delle", "degli", "dello", "con", "per", "che", "sono", "era", "dalla",
    "dalle", "nella", "nelle", "alla", "alle", "una", "uno", "gli", "lo", "la", "dei",
}
COUNTRY_ALIASES = {
    "it": "italy",
    "ita": "italy",
    "italia": "italy",
    "us": "united states",
    "usa": "united states",
    "u.s.": "united states",
    "u.s.a.": "united states",
    "uk": "united kingdom",
    "gb": "united kingdom",
    "gbr": "united kingdom",
    "england": "united kingdom",
    "fr": "france",
    "fra": "france",
    "de": "germany",
    "ger": "germany",
    "es": "spain",
    "esp": "spain",
}
ATTRIBUTION_MARKERS = (
    "according to", "reported", "reports", "confirmed", "statement", "official", "data from",
    "said", "told", "announced", "published by", "secondo", "ha detto", "ha dichiarato",
    "ha confermato", "riporta", "comunicato", "dati di", "ufficiale", "ha annunciato",
)
STRUCTURE_MARKERS = (
    "%", "percent", "per cento", "million", "billion", "miliardi", "milioni",
    "202", "2026", "2025", "2024", "monday", "tuesday", "luned", "marted", "mercoled",
)
SPAM_MARKERS = (
    "click here", "buy now", "you won't believe", "shocking", "miracle", "viral",
    "clicca qui", "compra ora", "incredibile", "assurdo", "clamoroso", "miracoloso",
)


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


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _tokenize(text: str) -> set[str]:
    cleaned = re.sub(r"[^\w\s]", " ", _normalize_for_match(text))
    return {part for part in cleaned.split() if len(part) > 2 and part not in STOPWORDS}


def _parse_iso_like_date(value: str) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    for candidate in (text, text[:10]):
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


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
        self.query_planner = QueryPlanningAgent(settings, llm_client=self.llm)
        self.crosscheck = CrossCheckAnalysisLayer(self.llm)
        self.search_profile_builder = TavilySearchProfileBuilder()
        self.source_scoring = SourceScoringLayer()
        self.evidence_scoring = EvidenceScoringLayer()

    async def run(self, state: PipelineState) -> PipelineState:
        text = state.normalized_text or state.raw_content
        if not text.strip():
            state.verdict = "insufficient_evidence"
            state.errors.append("tavily_first: empty input")
            return state

        logger.info("%s text_length=%d chars", layer_tag("pipeline"), len(text))

        # --- 1. Generate search queries from the full text ---
        t0 = time.time()
        logger.info("%s planning queries with Regolo", layer_tag("query"))
        queries = state.generated_queries or await self._generate_queries(text)
        state.generated_queries = list(queries)
        state.timings["query_generation"] = round(time.time() - t0, 3)
        logger.info(
            "%s generated=%d elapsed=%.3fs queries=%s",
            layer_tag("query"),
            len(queries),
            state.timings["query_generation"],
            queries,
        )

        # --- 2. Cascade search ---
        t0 = time.time()
        search_profile = self._build_search_profile(state, text)
        state.tavily_search_profile = dict(search_profile)
        logger.info(
            "%s profile topic=%s country=%s temporal=%s",
            layer_tag("retrieval"),
            search_profile["topic"],
            search_profile.get("country") or "-",
            search_profile["temporal"],
        )
        results, search_tier, retrieval_meta = await self._cascade_search(queries, search_profile)
        state.all_tavily_results = retrieval_meta["all_results"]
        state.tavily_answer_hints = retrieval_meta["answer_hints"]
        state.timings["tavily_search"] = round(time.time() - t0, 3)
        logger.info(
            "%s selected=%d tier=%s all_found=%d hints=%d elapsed=%.3fs",
            layer_tag("retrieval"),
            len(results),
            search_tier,
            len(state.all_tavily_results),
            len(state.tavily_answer_hints),
            state.timings["tavily_search"],
        )

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
        logger.info("%s enriching source content", layer_tag("retrieval"))
        results = await self._enrich_content(results, text)
        state.timings["tavily_extract"] = round(time.time() - t0, 3)
        logger.info("%s extract_elapsed=%.3fs", layer_tag("retrieval"), state.timings["tavily_extract"])

        # --- 2c. Source scoring (domain trust + content trust + local relevance) ---
        t0 = time.time()
        logger.info("%s pre-scoring sources", layer_tag("scoring"))
        results = self._pre_score_sources(results, text)
        state.timings["source_scoring"] = round(time.time() - t0, 3)
        logger.info(
            "%s scored=%d elapsed=%.3fs top_pre_score=%.3f",
            layer_tag("scoring"),
            len(results),
            state.timings["source_scoring"],
            float(results[0].get("_pre_score", 0.0)) if results else 0.0,
        )

        # --- 3. LLM cross-check (full text vs sources) ---
        t0 = time.time()
        logger.info("%s cross-checking evidence with Regolo", layer_tag("analysis"))
        analysis = await self._cross_check(text, results, search_tier)
        state.timings["llm_crosscheck"] = round(time.time() - t0, 3)
        logger.info(
            "%s verdict=%s raw_confidence=%.2f elapsed=%.3fs",
            layer_tag("analysis"),
            analysis.get("verdict", "insufficient_evidence"),
            float(analysis.get("confidence_score", 0.0)),
            state.timings["llm_crosscheck"],
        )

        # --- 4. Build state ---
        logger.info("%s assembling final state", layer_tag("assembly"))
        self._build_state(state, results, analysis, search_tier)
        return state

    # ------------------------------------------------------------------
    # Query generation
    # ------------------------------------------------------------------

    async def _generate_queries(self, text: str) -> list[str]:
        return await self.query_planner.generate_queries(text)

    # ------------------------------------------------------------------
    # Cascade search
    # ------------------------------------------------------------------

    async def _cascade_search(
        self,
        queries: list[str],
        search_profile: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:

        # Tier 1
        t1, t1_hints = await self._tavily_multi(
            queries,
            topic=str(search_profile["topic"]),
            country=str(search_profile.get("country", "")),
            temporal=search_profile["temporal"],
            include_domains=TIER1_DOMAINS,
            tier_label="tier1",
        )
        logger.info("    tier1: %d", len(t1))
        retrieval_meta = self._build_retrieval_meta(t1, [], t1_hints, [])
        if len(t1) >= TIER1_MIN_USEFUL:
            return t1[:5], "tier1", retrieval_meta

        # Tier 2
        t2, t2_hints = await self._tavily_multi(
            queries,
            topic=str(search_profile["topic"]),
            country=str(search_profile.get("country", "")),
            temporal=search_profile["temporal"],
            exclude_domains=BLACKLIST_DOMAINS,
            tier_label="tier2",
        )
        retrieval_meta = self._build_retrieval_meta(t1, t2, t1_hints, t2_hints)
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
            return merged[:5], "mixed", retrieval_meta

        if t2_useful:
            for r in t2_useful:
                r["_tier"] = "tier2"
            return t2_useful[:5], "tier2", retrieval_meta

        # Last resort: best of anything
        everything = t1 + t2
        everything.sort(key=lambda r: r.get("score", 0), reverse=True)
        if everything:
            for r in everything:
                if r not in t1:
                    r["_tier"] = "tier2"
            return everything[:5], "tier2", retrieval_meta

        return [], "tier1", retrieval_meta

    async def _tavily_multi(
        self,
        queries: list[str],
        *,
        topic: str,
        country: str,
        temporal: dict[str, str],
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        tier_label: str = "tier1",
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        answer_hints: list[dict[str, Any]] = []
        tasks = [
            tavily_search(
                query=q,
                search_depth="advanced",
                max_results=5,
                include_raw_content="text",
                include_answer="basic",
                auto_parameters=True,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
                topic=topic,
                time_range=temporal.get("time_range"),
                start_date=temporal.get("start_date"),
                end_date=temporal.get("end_date"),
                country=country or None,
                exact_match=self._should_use_exact_match(q),
            )
            for q in queries
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for q, data in zip(queries, responses):
            if isinstance(data, Exception):
                logger.warning("    tavily search failed for query=%r: %s", q, data)
                continue
            if data.get("answer"):
                answer_hints.append(
                    {
                        "query": q,
                        "answer": data["answer"],
                        "tier": tier_label,
                        "topic": topic,
                        "country": country or "",
                        "request_id": data.get("request_id", ""),
                        "auto_parameters": data.get("auto_parameters", {}),
                        "usage": data.get("usage", {}),
                    }
                )
            for r in data.get("results", []):
                url = r.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    item = dict(r)
                    if data.get("answer"):
                        item["_answer_hint"] = data["answer"]
                    item["_query"] = q
                    item["_request_id"] = data.get("request_id", "")
                    item["_auto_parameters"] = data.get("auto_parameters", {})
                    item["_usage"] = data.get("usage", {})
                    item["_retrieval_tier"] = tier_label
                    item["_search_topic"] = topic
                    if country:
                        item["_search_country"] = country
                    out.append(item)
        out.sort(key=lambda r: r.get("score", 0), reverse=True)
        return out, answer_hints

    def _build_search_profile(self, state: PipelineState, text: str) -> dict[str, Any]:
        return self.search_profile_builder.build(state, text)

    def _select_tavily_topic(self, state: PipelineState, text: str) -> str:
        return self.search_profile_builder.select_tavily_topic(state, text)

    def _select_country_boost(self, state: PipelineState, topic: str) -> str:
        return self.search_profile_builder.select_country_boost(state, topic)

    def _normalize_country(self, country: str) -> str:
        return self.search_profile_builder.normalize_country(country)

    def _build_temporal_filters(self, state: PipelineState, text: str, topic: str) -> dict[str, str]:
        return self.search_profile_builder.build_temporal_filters(state, text, topic)

    def _has_recent_signal(self, state: PipelineState, text: str, strong_only: bool = False) -> bool:
        return self.search_profile_builder.has_recent_signal(state, text, strong_only=strong_only)

    def _should_use_exact_match(self, query: str) -> bool:
        return self.search_profile_builder.should_use_exact_match(query)

    def _build_retrieval_meta(
        self,
        tier1_results: list[dict[str, Any]],
        tier2_results: list[dict[str, Any]],
        tier1_hints: list[dict[str, Any]],
        tier2_hints: list[dict[str, Any]],
    ) -> dict[str, Any]:
        all_results: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for item in tier1_results + tier2_results:
            url = item.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            all_results.append(item)
        all_results.sort(key=lambda item: item.get("score", 0), reverse=True)

        deduped_hints: list[dict[str, Any]] = []
        seen_hints: set[tuple[str, str, str]] = set()
        for hint in tier1_hints + tier2_hints:
            key = (
                str(hint.get("query", "")),
                str(hint.get("tier", "")),
                str(hint.get("answer", "")),
            )
            if key in seen_hints:
                continue
            seen_hints.add(key)
            deduped_hints.append(hint)

        return {
            "all_results": all_results,
            "answer_hints": deduped_hints,
        }

    def _pre_score_sources(self, results: list[dict[str, Any]], text: str) -> list[dict[str, Any]]:
        return self.source_scoring.score_sources(results, text)

    def _source_body(self, source: dict[str, Any]) -> str:
        return self.source_scoring.source_body(source)

    def _content_trust_score(self, text: str) -> float:
        return self.source_scoring.content_trust_score(text)

    def _local_relevance_score(self, text_to_verify: str, source_text: str) -> float:
        return self.source_scoring.local_relevance_score(text_to_verify, source_text)

    def _combine_source_trust(self, domain_trust: float, content_trust: float) -> float:
        return self.source_scoring.combine_source_trust(domain_trust, content_trust)

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
                    extract_depth="advanced",
                    output_format="text",
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
        return await self.crosscheck.run(text, results, search_tier)

    def _fallback(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        return self.crosscheck.fallback(results)

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

        (
            state.sources_used,
            state.scored_evidence,
            state.contradictions,
        ) = self.evidence_scoring.build_records(
            results=results,
            analysis=analysis,
            search_tier=search_tier,
        )

        # Scores with tier-based confidence cap
        state.truth_score = max(0, min(100, analysis.get("truth_score", 0)))
        raw_conf = analysis.get("confidence_score", 0.0)
        cap = {"tier1": 1.0, "mixed": 0.80, "tier2": 0.65}.get(search_tier, 1.0)
        state.confidence_score = max(0.0, min(cap, raw_conf))
        state.verdict = analysis.get("verdict", "insufficient_evidence")

        logger.info(
            "%s verdict=%s score=%d confidence=%.2f raw=%.2f cap=%.2f tier=%s",
            layer_tag("assembly"),
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
