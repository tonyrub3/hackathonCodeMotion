"""
Tavily-First Fact-Checking Engine with Cascade Search.

Pipeline:
  1. Se ci sono claim estratti, li usa come query di ricerca
  2. Cascade Search (Tier 1 primary -> Tier 2 broad)
  3. LLM judge globale: produce verdict, confidence ed explanation
  4. Guardrail deterministici: limitano overclaim e incoerenze evidenti
  5. Assembla la risposta finale in italiano
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
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
from app.services.analysis.explanation_scoring import ExplanationScoringLayer
from app.services.retrieval.domain_policy import BLACKLIST_DOMAINS, TIER1_DOMAINS, TRUSTED_DOMAINS
from app.services.retrieval.search_profile import TavilySearchProfileBuilder
from app.services.scoring.evidence_scoring import EvidenceScoringLayer
from app.services.scoring.source_scoring import SourceScoringLayer
from app.utils.pipeline_trace import layer_tag

logger = logging.getLogger(__name__)


TIER1_MIN_USEFUL = 2
TIER2_RELEVANCE_THRESHOLD = 0.20

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "was", "were", "are",
    "del", "della", "delle", "degli", "dello", "con", "per", "che", "sono", "era", "dalla",
    "dalle", "nella", "nelle", "alla", "alle", "una", "uno", "gli", "lo", "la", "dei",
}

NEGATIVE_EXPLANATION_MARKERS = (
    "non conferma",
    "non confermano",
    "do not confirm",
    "does not confirm",
    "not confirmed",
    "non supporta",
    "non supportano",
    "insufficient evidence",
    "evidenza insufficiente",
    "evidenze insufficienti",
    "non ci sono prove",
    "manca evidenza",
    "mancano evidenze",
    "non verificabile",
    "non verificato",
    "non e confermato",
    "non è confermato",
    "does not mention",
    "non menziona",
    "does not provide",
    "non fornisce",
)

CONTRADICTION_MARKERS = (
    "contraddice",
    "contraddicono",
    "smentisce",
    "smentiscono",
    "false",
    "falso",
    "incorrect",
    "errato",
    "inaccurato",
)

POSITIVE_EXPLANATION_MARKERS = (
    "conferma",
    "confermano",
    "supporta",
    "supportano",
    "verificato",
    "verified",
    "corrobor",
    "riscontro",
    "coerente",
    "coerenti",
    "compatibile",
    "compatibili",
)

UNCERTAINTY_EXPLANATION_MARKERS = (
    "parziale",
    "parzialmente",
    "ambigu",
    "incert",
    "cautela",
    "limit",
    "prudente",
    "non conclusiv",
    "non sempre conclusiv",
    "mixed",
    "misto",
)

LEVEL_POINTS = {
    "none": 0.0,
    "weak": 1.0,
    "moderate": 2.0,
    "strong": 3.0,
}

GRADE_POINTS = {
    "none": 0.0,
    "low": 1.0,
    "medium": 2.0,
    "high": 3.0,
    "weak": 1.0,
    "strong": 3.0,
}

VERDICT_ORDER = [
    "false", "mostly_false", "misleading", "mixed",
    "mostly_verified", "verified",
]


def _request_timeout(settings: Settings) -> float | None:
    return None if settings.request_timeout_seconds <= 0 else float(settings.request_timeout_seconds)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url[:60]


def _to_str_list(items: list) -> list[str]:
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


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class TavilyFirstEngine:
    """Fact-checking engine: claim-guided retrieval + LLM-first judgment."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = RegoloClient(
            api_key=settings.regolo_api_key,
            base_url=settings.regolo_base_url,
            llm_model=settings.regolo_model,
            timeout_seconds=_request_timeout(settings),
        )
        self.crosscheck_llm = RegoloClient(
            api_key=settings.regolo_api_key,
            base_url=settings.regolo_base_url,
            llm_model=settings.regolo_crosscheck_model or settings.regolo_model,
            timeout_seconds=_request_timeout(settings),
        )
        self.scoring_llm = RegoloClient(
            api_key=settings.regolo_api_key,
            base_url=settings.regolo_base_url,
            llm_model=settings.regolo_scoring_model or settings.regolo_model,
            timeout_seconds=_request_timeout(settings),
        )
        self.query_planner = QueryPlanningAgent(settings, llm_client=self.llm)
        self.crosscheck = CrossCheckAnalysisLayer(self.crosscheck_llm)
        self.explanation_scoring = ExplanationScoringLayer(self.scoring_llm)
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

        # --- 1. Build search queries ---
        t0 = time.time()
        logger.info("%s planning queries with Regolo", layer_tag("query"))
        queries = state.generated_queries or await self._generate_queries(text, state.claims, state=state)
        if state.claims and len(queries) == len(state.claims):
            for claim, query in zip(state.claims, queries):
                claim["search_query"] = query

        state.generated_queries = list(queries)
        state.timings["query_generation"] = round(time.time() - t0, 3)
        logger.info(
            "%s generated=%d elapsed=%.3fs claim_guided=%s",
            layer_tag("query"),
            len(queries),
            state.timings["query_generation"],
            "yes" if state.claims else "no",
        )

        # --- 2. Cascade search ---
        t0 = time.time()
        search_profile = self._build_search_profile(state, text, claims=state.claims, queries=queries)
        state.tavily_search_profile = dict(search_profile)
        logger.info(
            "%s profile topic=%s country=%s temporal=%s",
            layer_tag("retrieval"),
            search_profile["topic"],
            search_profile.get("country") or "-",
            search_profile["temporal"],
        )
        max_results = max(5, min(20, len(queries) * 2))
        results, search_tier, retrieval_meta = await self._cascade_search(
            queries, search_profile, max_results=max_results,
        )
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
                "summary": "Nessuna evidenza trovata dalle fonti web.",
                "why": "Le ricerche su fonti primarie e ampie non hanno restituito risultati utili.",
                "supporting_evidence": [], "contradicting_evidence": [],
                "source_analysis": [], "temporal_context": "",
                "caveats": ["Nessuna fonte web trovata per verificare questo contenuto."],
            }
            return state

        # --- 2b. Extract full content where missing ---
        t0 = time.time()
        logger.info("%s enriching source content", layer_tag("retrieval"))
        results = await self._enrich_content(results, text)
        state.timings["tavily_extract"] = round(time.time() - t0, 3)

        # --- 2c. Source scoring (domain trust + editorial quality) ---
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

        # --- 3. LLM judge: verdict globale + analisi per fonte ---
        t0 = time.time()
        effective_claims = state.claims or [
            {"id": "c0", "claim": text[:500], "type": "other", "checkability_score": 0.50}
        ]
        logger.info(
            "%s judging %d claims worth of context against %d sources",
            layer_tag("analysis"), len(effective_claims), len(results),
        )
        analysis = await self._cross_check(text, results, search_tier, effective_claims)
        state.timings["llm_crosscheck"] = round(time.time() - t0, 3)
        analysis["explanation_assessment"] = await self._score_explanation(
            analysis.get("explanation"),
            search_tier=search_tier,
        )
        logger.info(
            "%s judge complete verdict=%s per_source=%d elapsed=%.3fs",
            layer_tag("analysis"),
            analysis.get("verdict", "-"),
            len(analysis.get("per_source", [])),
            state.timings["llm_crosscheck"],
        )

        # --- 4. State assembly with minimal guardrails ---
        logger.info("%s assembling final state with LLM-first judgment", layer_tag("assembly"))
        self._build_state(state, results, analysis, search_tier, effective_claims)
        return state

    # ------------------------------------------------------------------
    # Query generation
    # ------------------------------------------------------------------

    async def _generate_queries(
        self,
        text: str,
        claims: list[dict[str, Any]] | None = None,
        *,
        state: PipelineState | None = None,
    ) -> list[str]:
        return await self.query_planner.generate_queries(text, claims=claims, state=state)

    async def _score_explanation(
        self,
        explanation: dict[str, Any] | None,
        *,
        search_tier: str,
    ) -> dict[str, Any]:
        return await self.explanation_scoring.run(explanation, search_tier=search_tier)

    # ------------------------------------------------------------------
    # Cascade search
    # ------------------------------------------------------------------

    async def _cascade_search(
        self,
        queries: list[str],
        search_profile: dict[str, Any],
        max_results: int = 5,
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
            return t1[:max_results], "tier1", retrieval_meta

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
            return merged[:max_results], "mixed", retrieval_meta

        if t2_useful:
            for r in t2_useful:
                r["_tier"] = "tier2"
            return t2_useful[:max_results], "tier2", retrieval_meta

        everything = t1 + t2
        everything.sort(key=lambda r: r.get("score", 0), reverse=True)
        if everything:
            for r in everything:
                if r not in t1:
                    r["_tier"] = "tier2"
            return everything[:max_results], "tier2", retrieval_meta

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
                timeout_seconds=_request_timeout(self.settings),
            )
            for q in queries
        ]
        responses = await asyncio.gather(*tasks)
        for q, data in zip(queries, responses):
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

    def _build_search_profile(
        self,
        state: PipelineState,
        text: str,
        *,
        claims: list[dict[str, Any]] | None = None,
        queries: list[str] | None = None,
    ) -> dict[str, Any]:
        return self.search_profile_builder.build(state, text, claims=claims, queries=queries)

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
            data = await tavily_extract(
                urls=urls_need[:5],
                query=text[:300],
                chunks_per_source=3,
                extract_depth="advanced",
                output_format="text",
                timeout_seconds=_request_timeout(self.settings),
            )
            for er in data.get("results", []):
                idx = idx_map.get(er.get("url", ""))
                if idx is not None and er.get("raw_content"):
                    results[idx]["raw_content"] = er["raw_content"]
        return results

    # ------------------------------------------------------------------
    # LLM cross-check
    # ------------------------------------------------------------------

    async def _cross_check(
        self,
        text: str,
        results: list[dict[str, Any]],
        search_tier: str,
        claims: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self.crosscheck.run(text, results, search_tier, claims=claims)

    # ------------------------------------------------------------------
    # Deterministic scoring
    # ------------------------------------------------------------------

    def _score_claims(
        self,
        claims: list[dict[str, Any]],
        results: list[dict[str, Any]],
        analysis: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Compute per-claim scores from cross-check signals + source trust.

        For each claim:
        - Collect (stance, relevance, source_trust) from each source
        - supporting_weight = sum(relevance * source_trust) for supporting
        - contradicting_weight = sum(relevance * source_trust) for contradicting
        - claim_score = 0-100 based on net evidence
        - claim_confidence = based on coverage and quality
        - claim_verdict = deterministic from score + confidence
        """
        per_source_list = analysis.get("per_source", [])
        source_trust_map: dict[int, float] = {}
        for i, r in enumerate(results):
            source_trust_map[i] = float(r.get("_source_reliability", 0.5))

        claim_results: list[dict[str, Any]] = []

        for claim in claims:
            cid = claim["id"]
            supporting_weight = 0.0
            contradicting_weight = 0.0
            neutral_weight = 0.0
            coverage = 0
            supporting_excerpts: list[str] = []
            contradicting_excerpts: list[str] = []

            for ps in per_source_list:
                src_idx = ps.get("source_index", -1)
                src_trust = source_trust_map.get(src_idx, 0.5)

                for pc in ps.get("per_claim", []):
                    if pc.get("claim_id") != cid:
                        continue

                    stance = pc.get("stance", "neutral")
                    relevance = max(0.0, min(1.0, float(pc.get("relevance", 0.0))))
                    excerpt = pc.get("key_excerpt", "")
                    weight = relevance * src_trust
                    coverage += 1

                    if stance == "supporting":
                        supporting_weight += weight
                        if excerpt:
                            supporting_excerpts.append(excerpt)
                    elif stance == "contradicting":
                        contradicting_weight += weight
                        if excerpt:
                            contradicting_excerpts.append(excerpt)
                    else:
                        neutral_weight += weight

            # Score: 0-100 where 50 = neutral, 100 = fully supported, 0 = fully contradicted
            total_evidence = supporting_weight + contradicting_weight
            if total_evidence < 0.01:
                claim_score = 50.0  # No directional evidence
            else:
                claim_score = round((supporting_weight / total_evidence) * 100, 1)

            # Confidence: how much we trust the result
            coverage_factor = min(1.0, coverage / 3.0)
            evidence_strength = min(1.0, total_evidence / 1.0)
            claim_confidence = round(coverage_factor * 0.5 + evidence_strength * 0.5, 3)

            # Verdict
            claim_verdict = self._claim_verdict(claim_score, claim_confidence, coverage)

            claim_results.append({
                "claim_id": cid,
                "claim_text": claim.get("claim", ""),
                "claim_type": claim.get("type", "other"),
                "checkability": claim.get("checkability_score", 0.5),
                "supporting_weight": round(supporting_weight, 3),
                "contradicting_weight": round(contradicting_weight, 3),
                "neutral_weight": round(neutral_weight, 3),
                "coverage": coverage,
                "claim_score": claim_score,
                "claim_confidence": claim_confidence,
                "claim_verdict": claim_verdict,
                "supporting_excerpts": supporting_excerpts[:3],
                "contradicting_excerpts": contradicting_excerpts[:3],
            })

        return claim_results

    def _claim_verdict(self, score: float, confidence: float, coverage: int) -> str:
        if coverage == 0:
            return "insufficient_evidence"
        if confidence < 0.15:
            return "insufficient_evidence"

        if score >= 75:
            if confidence >= 0.50:
                return "verified"
            return "mostly_verified"
        elif score >= 60:
            if confidence >= 0.30:
                return "mostly_verified"
            return "mixed"
        elif score >= 40:
            return "mixed"
        elif score >= 25:
            if confidence >= 0.30:
                return "misleading"
            return "mixed"
        else:
            if confidence >= 0.30:
                return "mostly_false"
            return "mixed"

    def _aggregate_document_scores(
        self,
        claim_results: list[dict[str, Any]],
        search_tier: str,
    ) -> tuple[float, float, str]:
        """Aggregate claim-level scores into document-level verdict."""
        if not claim_results:
            return 0.0, 0.0, "insufficient_evidence"

        # Weighted average of claim_score by checkability
        total_weight = 0.0
        weighted_score = 0.0
        weighted_confidence = 0.0
        covered = 0
        has_contradiction = False

        for cr in claim_results:
            w = cr["checkability"]
            weighted_score += cr["claim_score"] * w
            weighted_confidence += cr["claim_confidence"] * w
            total_weight += w
            if cr["coverage"] > 0:
                covered += 1
            if cr["contradicting_weight"] > 0.3:
                has_contradiction = True

        if total_weight == 0:
            return 0.0, 0.0, "insufficient_evidence"

        truth_score = round(weighted_score / total_weight, 1)
        avg_confidence = weighted_confidence / total_weight

        # Coverage ratio
        coverage_ratio = covered / len(claim_results) if claim_results else 0.0
        coverage_factor = 0.5 + 0.5 * coverage_ratio

        # Tier cap
        tier_cap = {"tier1": 1.0, "mixed": 0.80, "tier2": 0.65}.get(search_tier, 1.0)

        # Contradiction penalty
        contradiction_penalty = 0.85 if has_contradiction else 1.0

        confidence = round(
            max(0.0, min(tier_cap, avg_confidence * coverage_factor * contradiction_penalty)),
            3,
        )

        verdict = self._document_verdict(truth_score, confidence)
        return truth_score, confidence, verdict

    def _document_verdict(self, truth_score: float, confidence: float) -> str:
        if confidence < 0.15:
            return "insufficient_evidence"

        # Base verdict from truth_score
        if truth_score >= 80:
            base = "verified"
        elif truth_score >= 65:
            base = "mostly_verified"
        elif truth_score >= 45:
            base = "mixed"
        elif truth_score >= 30:
            base = "misleading"
        elif truth_score >= 15:
            base = "mostly_false"
        else:
            base = "false"

        # Confidence gates the maximum verdict
        if confidence < 0.30:
            max_idx = VERDICT_ORDER.index("mixed")
        elif confidence < 0.45:
            max_idx = VERDICT_ORDER.index("mostly_verified")
        else:
            max_idx = len(VERDICT_ORDER) - 1

        base_idx = VERDICT_ORDER.index(base)
        return VERDICT_ORDER[min(base_idx, max_idx)]

    # ------------------------------------------------------------------
    # Italian explanation builder
    # ------------------------------------------------------------------

    def _build_explanation(
        self,
        claim_results: list[dict[str, Any]],
        search_tier: str,
        sources_used: list[dict[str, Any]],
        scored_evidence: list[dict[str, Any]],
        article_date: str = "",
    ) -> dict[str, Any]:
        """Build reader-facing explanation in the legacy narrative structure."""
        n_claims = len(claim_results)
        n_verified = sum(1 for c in claim_results if c["claim_verdict"] in ("verified", "mostly_verified"))
        n_contradicted = sum(1 for c in claim_results if c["claim_verdict"] in ("false", "mostly_false", "misleading"))
        n_mixed = sum(1 for c in claim_results if c["claim_verdict"] == "mixed")
        n_insufficient = sum(1 for c in claim_results if c["claim_verdict"] == "insufficient_evidence")
        source_count = len(sources_used)

        if n_verified and not n_contradicted:
            summary = (
                "Le fonti trovate supportano nel complesso il contenuto analizzato. "
                f"La verifica si basa su {source_count} fonti esaminate."
            )
        elif n_contradicted and not n_verified:
            summary = (
                "Le fonti trovate non confermano il contenuto analizzato e ne contraddicono parti rilevanti. "
                f"La verifica si basa su {source_count} fonti esaminate."
            )
        elif n_verified and n_contradicted:
            summary = (
                "Le fonti trovate confermano solo una parte del contenuto, mentre altre affermazioni risultano contestate. "
                f"La verifica si basa su {source_count} fonti esaminate."
            )
        elif n_mixed:
            summary = (
                "Le fonti trovate offrono un quadro misto: alcune informazioni sono coerenti, altre restano ambigue. "
                f"La verifica si basa su {source_count} fonti esaminate."
            )
        else:
            summary = (
                "Le fonti trovate non sono sufficienti per confermare con affidabilita il contenuto analizzato. "
                f"La verifica si basa su {source_count} fonti esaminate."
            )

        why_parts: list[str] = []
        if n_verified:
            why_parts.append(f"{n_verified} affermazioni trovano riscontro in evidenze pertinenti")
        if n_contradicted:
            why_parts.append(f"{n_contradicted} affermazioni risultano contraddette da fonti attendibili")
        if n_mixed:
            why_parts.append(f"{n_mixed} affermazioni hanno segnali contrastanti")
        if n_insufficient:
            why_parts.append(f"{n_insufficient} affermazioni non hanno copertura sufficiente")
        why_parts.append(f"sono state considerate {source_count} fonti nel ranking finale")
        why = ". ".join(part[:1].upper() + part[1:] for part in why_parts if part).strip()
        if why and not why.endswith("."):
            why += "."

        supporting: list[str] = []
        for cr in claim_results:
            if cr["claim_verdict"] in ("verified", "mostly_verified") and cr["supporting_excerpts"]:
                supporting.append(f'{cr["claim_text"]}: {cr["supporting_excerpts"][0]}')

        contradicting: list[str] = []
        for cr in claim_results:
            if cr["claim_verdict"] in ("false", "mostly_false", "misleading") and cr["contradicting_excerpts"]:
                contradicting.append(f'{cr["claim_text"]}: {cr["contradicting_excerpts"][0]}')

        evidence_map = {item["source_id"]: item for item in scored_evidence}
        source_analysis: list[str] = []
        for source in sources_used:
            evidence = evidence_map.get(source["source_id"], {})
            stance = str(evidence.get("stance", "neutral"))
            stance_label = {
                "supporting": "supporta parte del contenuto",
                "contradicting": "contraddice parte del contenuto",
                "neutral": "fornisce soprattutto contesto",
            }.get(stance, "fornisce soprattutto contesto")
            source_analysis.append(
                f'{source["source_name"]} (tier {source["tier"]}): {stance_label}; '
                f'affidabilita {(source["source_reliability_score"] * 100):.0f}%.'
            )

        temporal_context = ""
        if article_date:
            temporal_context = f"L'articolo analizzato riporta come data {article_date}."
        elif any(re.search(r"\b(19|20)\d{2}\b", cr["claim_text"]) for cr in claim_results):
            temporal_context = "La verifica include affermazioni con riferimenti temporali espliciti."

        caveats: list[str] = []
        tier_caveats = {
            "tier2": "Verificato solo tramite fonti locali/di settore. Non ancora corroborato da media internazionali di primo livello.",
            "mixed": "Parzialmente verificato da fonti primarie; alcune evidenze provengono da testate locali/di settore.",
        }
        if search_tier in tier_caveats:
            caveats.append(tier_caveats[search_tier])

        if n_insufficient > 0:
            caveats.append(
                f"{n_insufficient} affermazioni su {n_claims} non hanno trovato evidenza sufficiente sul web."
            )

        return {
            "summary": summary,
            "why": why,
            "supporting_evidence": supporting[:6],
            "contradicting_evidence": contradicting[:6],
            "source_analysis": source_analysis,
            "temporal_context": temporal_context,
            "caveats": caveats,
        }

    def _normalize_explanation(
        self,
        explanation: dict[str, Any] | None,
        *,
        search_tier: str,
        sources_used: list[dict[str, Any]],
        article_date: str = "",
    ) -> dict[str, Any]:
        base = explanation or {}
        normalized = {
            "summary": str(base.get("summary", "")).strip(),
            "why": str(base.get("why", "")).strip(),
            "supporting_evidence": _to_str_list(base.get("supporting_evidence", [])),
            "contradicting_evidence": _to_str_list(base.get("contradicting_evidence", [])),
            "source_analysis": _to_str_list(base.get("source_analysis", [])),
            "temporal_context": str(base.get("temporal_context", "")).strip(),
            "caveats": _to_str_list(base.get("caveats", [])),
        }

        if not normalized["summary"]:
            normalized["summary"] = (
                "Le fonti trovate offrono un quadro utile ma non sempre conclusivo sul contenuto analizzato."
            )
        if not normalized["why"]:
            normalized["why"] = (
                "Il giudizio finale combina le fonti recuperate, la loro pertinenza rispetto al contenuto e i limiti emersi durante il confronto."
            )
        if not normalized["source_analysis"]:
            for source in sources_used:
                normalized["source_analysis"].append(
                    f'{source["source_name"]} (tier {source["tier"]}): fonte inclusa nel confronto finale.'
                )
        if not normalized["temporal_context"] and article_date:
            normalized["temporal_context"] = f"L'articolo analizzato riporta come data {article_date}."

        tier_caveats = {
            "tier2": "Verificato soprattutto con fonti piu deboli o locali: la confidence resta limitata.",
            "mixed": "La verifica combina fonti di tier diversi: il risultato va letto con cautela.",
        }
        if search_tier in tier_caveats and tier_caveats[search_tier] not in normalized["caveats"]:
            normalized["caveats"].append(tier_caveats[search_tier])
        return normalized

    def _score_from_judgment_basis(
        self,
        analysis: dict[str, Any],
        *,
        search_tier: str,
    ) -> tuple[float, float, str]:
        basis = analysis.get("judgment_basis") or {}
        if not isinstance(basis, dict) or not basis:
            truth_score = max(0.0, min(100.0, float(analysis.get("truth_score", 0.0))))
            confidence = max(0.0, min(1.0, float(analysis.get("confidence_score", 0.0))))
            verdict = str(analysis.get("verdict", "insufficient_evidence") or "insufficient_evidence")
            return truth_score, confidence, verdict

        direct_support = LEVEL_POINTS.get(str(basis.get("direct_support_level", "none")), 0.0)
        contradiction = LEVEL_POINTS.get(str(basis.get("contradiction_level", "none")), 0.0)
        sufficiency = GRADE_POINTS.get(str(basis.get("evidence_sufficiency", "low")), 1.0)
        agreement = GRADE_POINTS.get(str(basis.get("source_agreement", "low")), 1.0)
        temporal = GRADE_POINTS.get(str(basis.get("temporal_alignment", "weak")), 1.0)
        main_claim_confirmed = bool(basis.get("main_claim_confirmed", False))
        subject_only_match = bool(basis.get("subject_only_match", False))

        truth_score = 50.0
        truth_score += direct_support * 10.0
        truth_score -= contradiction * 12.0
        truth_score += (sufficiency - 1.0) * 4.0
        truth_score += (agreement - 1.0) * 3.0
        truth_score += (temporal - 1.0) * 2.0
        truth_score += 8.0 if main_claim_confirmed else -6.0
        if subject_only_match:
            truth_score -= 18.0
        if sufficiency <= 1.0 and direct_support == 0.0:
            truth_score = min(truth_score, 55.0)
        if contradiction >= 2.0 and direct_support == 0.0:
            truth_score = min(truth_score, 35.0)
        truth_score = max(0.0, min(100.0, truth_score))

        confidence = 0.10
        confidence += 0.18 * (sufficiency / 3.0)
        confidence += 0.18 * (agreement / 3.0)
        confidence += 0.18 * (temporal / 3.0)
        confidence += 0.24 * (direct_support / 3.0)
        confidence += 0.12 if main_claim_confirmed else 0.0
        if subject_only_match:
            confidence -= 0.18
        if direct_support == 0.0:
            confidence = min(confidence, 0.45)
        if contradiction >= 2.0:
            confidence = min(confidence, 0.50)
        if sufficiency == 0.0:
            confidence = min(confidence, 0.25)
        if search_tier == "tier2":
            confidence = min(confidence, 0.65)
        elif search_tier == "mixed":
            confidence = min(confidence, 0.80)
        confidence = max(0.0, min(1.0, confidence))

        if direct_support == 0.0 and contradiction == 0.0:
            verdict = "insufficient_evidence"
        elif subject_only_match and direct_support == 0.0:
            verdict = "insufficient_evidence"
        elif contradiction >= 2.0 and direct_support <= 1.0:
            verdict = "false" if contradiction >= 3.0 and confidence >= 0.40 else "mostly_false"
        elif truth_score >= 80.0 and confidence >= 0.70 and direct_support >= 2.0:
            verdict = "verified"
        elif truth_score >= 65.0 and confidence >= 0.55 and direct_support >= 1.0:
            verdict = "mostly_verified"
        elif contradiction > 0.0 and direct_support > 0.0:
            verdict = "mixed"
        elif truth_score < 45.0 and contradiction > 0.0:
            verdict = "misleading"
        else:
            verdict = "insufficient_evidence"

        return round(truth_score, 1), round(confidence, 3), verdict

    def _restore_reader_facing_explanation(
        self,
        explanation: dict[str, Any],
        *,
        verdict: str,
        source_count: int,
    ) -> dict[str, Any]:
        restored = dict(explanation)
        if restored.get("summary") and restored.get("why"):
            return restored
        if verdict in {"verified", "mostly_verified"}:
            restored["summary"] = (
                "Le fonti trovate supportano nel complesso il contenuto analizzato. "
                f"La verifica si basa su {source_count} fonti esaminate."
            )
            restored["why"] = (
                "Le evidenze piu pertinenti confermano il fatto principale e risultano coerenti tra loro."
            )
        elif verdict in {"false", "mostly_false", "misleading"}:
            restored["summary"] = (
                "Le fonti trovate non confermano il contenuto analizzato e ne contraddicono parti rilevanti. "
                f"La verifica si basa su {source_count} fonti esaminate."
            )
            restored["why"] = (
                "Le evidenze piu solide smentiscono il punto centrale oppure non trovano riscontro sufficiente nelle fonti considerate."
            )
        elif verdict == "mixed":
            restored["summary"] = (
                "Le fonti trovate offrono un quadro misto: alcune informazioni sono coerenti, altre restano ambigue. "
                f"La verifica si basa su {source_count} fonti esaminate."
            )
            restored["why"] = (
                "Alcune evidenze supportano il contenuto, ma altre restano parziali o non confermano tutti i dettagli principali."
            )
        else:
            restored["summary"] = (
                "Le fonti trovate non sono sufficienti per confermare con affidabilita il contenuto analizzato. "
                f"La verifica si basa su {source_count} fonti esaminate."
            )
            restored["why"] = (
                "Le fonti recuperate parlano del tema, ma non forniscono riscontri diretti abbastanza forti sul fatto principale."
            )
        return restored

    def _apply_judgment_guardrails(
        self,
        analysis: dict[str, Any],
        *,
        search_tier: str,
        explanation: dict[str, Any] | None = None,
    ) -> tuple[float, float, str]:
        explanation_assessment = analysis.get("explanation_assessment")
        if isinstance(explanation_assessment, dict) and {"truth_score", "confidence_score", "verdict"}.issubset(explanation_assessment.keys()):
            truth_score = max(0.0, min(100.0, float(explanation_assessment.get("truth_score", 0.0))))
            confidence = max(0.0, min(1.0, float(explanation_assessment.get("confidence_score", 0.0))))
            verdict = str(explanation_assessment.get("verdict", "insufficient_evidence") or "insufficient_evidence")
        else:
            truth_score, confidence, verdict = self._score_from_judgment_basis(
                analysis,
                search_tier=search_tier,
            )

        per_source = analysis.get("per_source", []) or []
        supporting = 0
        contradicting = 0
        relevant = 0

        for item in per_source:
            stance = str(item.get("stance", "neutral"))
            relevance = max(0.0, min(1.0, float(item.get("relevance", 0.0))))
            if relevance >= 0.35:
                relevant += 1
            if stance == "supporting" and relevance >= 0.45:
                supporting += 1
            if stance == "contradicting" and relevance >= 0.55:
                contradicting += 1

        normalized_explanation = explanation or {}
        text_parts = [
            str(normalized_explanation.get("summary", "")),
            str(normalized_explanation.get("why", "")),
            str(normalized_explanation.get("temporal_context", "")),
            *[str(item) for item in normalized_explanation.get("supporting_evidence", [])],
            *[str(item) for item in normalized_explanation.get("contradicting_evidence", [])],
            *[str(item) for item in normalized_explanation.get("source_analysis", [])],
            *[str(item) for item in normalized_explanation.get("caveats", [])],
        ]
        explanation_text = " ".join(part.lower() for part in text_parts if part).strip()
        has_negative_marker = any(marker in explanation_text for marker in NEGATIVE_EXPLANATION_MARKERS)
        has_contradiction_marker = any(marker in explanation_text for marker in CONTRADICTION_MARKERS)

        if relevant == 0:
            truth_score = min(truth_score, 50.0)
            confidence = min(confidence, 0.25)
            verdict = "insufficient_evidence"

        if supporting == 0 and verdict in {"verified", "mostly_verified"}:
            verdict = "mixed" if contradicting > 0 else "insufficient_evidence"
            confidence = min(confidence, 0.45)
            truth_score = min(truth_score, 59.0)

        if contradicting > 0:
            confidence = min(confidence, 0.55)

        if has_negative_marker and verdict in {"verified", "mostly_verified", "mixed"} and supporting <= max(1, contradicting):
            verdict = "mostly_false" if has_contradiction_marker else "insufficient_evidence"
            confidence = min(confidence, 0.35)
            truth_score = min(truth_score, 35.0 if has_contradiction_marker else 59.0)

        if normalized_explanation.get("contradicting_evidence") and not normalized_explanation.get("supporting_evidence"):
            if verdict in {"verified", "mostly_verified"}:
                verdict = "mostly_false" if has_contradiction_marker else "mixed"
                confidence = min(confidence, 0.45)
                truth_score = min(truth_score, 40.0 if has_contradiction_marker else 55.0)

        if search_tier == "tier2":
            confidence = min(confidence, 0.65)
        elif search_tier == "mixed":
            confidence = min(confidence, 0.80)

        return round(truth_score, 1), round(confidence, 3), verdict

    # ------------------------------------------------------------------
    # Build PipelineState
    # ------------------------------------------------------------------

    def _build_state(
        self,
        state: PipelineState,
        results: list[dict[str, Any]],
        analysis: dict[str, Any],
        search_tier: str,
        effective_claims: list[dict[str, Any]],
    ) -> None:

        # Build source/evidence records for API
        (
            state.sources_used,
            state.scored_evidence,
            state.contradictions,
        ) = self.evidence_scoring.build_records(
            results=results,
            analysis=analysis,
            search_tier=search_tier,
        )

        state.explanation = self._normalize_explanation(
            analysis.get("explanation"),
            search_tier=search_tier,
            sources_used=state.sources_used,
            article_date=state.article_date,
        )
        state.consensus_signals = {"judgment_basis": analysis.get("judgment_basis", {})}

        state.truth_score, state.confidence_score, state.verdict = self._apply_judgment_guardrails(
            analysis,
            search_tier=search_tier,
            explanation=state.explanation,
        )

        logger.info(
            "%s verdict=%s score=%.1f confidence=%.2f tier=%s sources=%d",
            layer_tag("assembly"),
            state.verdict, state.truth_score, state.confidence_score,
            search_tier, len(state.sources_used),
        )

        if state.claims:
            default_partial = state.verdict if state.verdict not in {"verified", "mostly_verified"} else "insufficient_evidence"
            default_score = state.truth_score if state.verdict not in {"verified", "mostly_verified"} else 0.0
            for claim in state.claims:
                claim.setdefault("partial_verdict", default_partial)
                claim.setdefault("partial_score", default_score)
                if claim.get("partial_verdict") == "insufficient_evidence" and state.verdict not in {"verified", "mostly_verified"}:
                    claim["partial_verdict"] = default_partial
                if float(claim.get("partial_score", 0.0) or 0.0) == 0.0 and default_score:
                    claim["partial_score"] = default_score

        if not state.explanation.get("source_analysis") and state.sources_used:
            state.explanation["source_analysis"] = [
                f'{source["source_name"]} (tier {source["tier"]}): fonte inclusa nel giudizio finale.'
                for source in state.sources_used
            ]

        if state.verdict == "insufficient_evidence" and not state.explanation.get("caveats"):
            state.explanation["caveats"] = [
                "Le fonti recuperate non confermano in modo diretto e sufficiente il contenuto analizzato."
            ]

        if state.verdict in {"verified", "mostly_verified"} and not state.explanation.get("supporting_evidence"):
            state.explanation["supporting_evidence"] = [
                "Il giudizio positivo si basa sulle fonti piu pertinenti recuperate nel confronto finale."
            ]

        if state.verdict in {"mixed", "misleading", "mostly_false", "false"} and not state.explanation.get("contradicting_evidence"):
            state.explanation["contradicting_evidence"] = _to_str_list(
                state.explanation.get("contradicting_evidence", [])
            )

        state.explanation = self._restore_reader_facing_explanation(
            state.explanation,
            verdict=state.verdict,
            source_count=len(state.sources_used),
        )

        # Keep an Italian, reader-facing explanation while preserving the model output.
        state.explanation["summary"] = str(state.explanation.get("summary", "")).strip()
        state.explanation["why"] = str(state.explanation.get("why", "")).strip()

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
