"""
Agent 3 – Source Discovery.

Responsibilities:
  - Generate retrieval queries from each claim
  - Discover evidence sources automatically (no manual whitelist)
  - Query Google Fact Check, GDELT, official-source heuristics
  - Mine cited sources from input article (URL mode)
  - Collect candidate evidence items

Tools used:
  - query_builder
  - google_factcheck_search
  - gdelt_doc_search
  - gdelt_context_search
  - official_source_discovery
  - news_source_discovery
  - cited_source_miner
  - official_social_discovery
  - passage_selector
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.core.state import PipelineState
from app.services.discovery.query_builder import build_queries
from app.services.connectors.google_factcheck_search import search_google_factcheck
from app.services.connectors.gdelt_doc_search import search_gdelt_docs
from app.services.connectors.gdelt_context_search import search_gdelt_context
from app.services.discovery.official_source_discovery import discover_official_sources
from app.services.discovery.news_source_discovery import discover_news_sources
from app.services.discovery.cited_source_miner import mine_cited_sources
from app.services.discovery.official_social_discovery import discover_official_social

logger = logging.getLogger(__name__)


class SourceDiscoveryAgent:
    """Discover and collect evidence sources for each claim."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, state: PipelineState) -> PipelineState:
        """
        Input contract:  state.claims, state.cited_links, state.topic
        Output contract: state.evidence_items, state.sources_used
        """
        all_evidence: list[dict[str, Any]] = []
        all_sources: dict[str, dict[str, Any]] = {}

        for claim in state.claims:
            queries = build_queries(claim, state.topic)
            logger.info("    [%s] queries: %s", claim["id"], queries)

            evidence_batch: list[dict[str, Any]] = []

            # 1. Google Fact Check
            try:
                fc_results = await search_google_factcheck(
                    claim["claim"],
                    api_key=self.settings.google_factcheck_api_key,
                    language=state.language,
                )
                evidence_batch.extend(fc_results)
                logger.info("    [%s] Google FactCheck: %d results", claim["id"], len(fc_results))
            except Exception as exc:
                logger.warning("    [%s] Google FactCheck FAILED: %s", claim["id"], exc)

            # 2. GDELT DOC
            try:
                gdelt_results = await search_gdelt_docs(
                    queries,
                    api_url=self.settings.gdelt_doc_api_url,
                )
                evidence_batch.extend(gdelt_results)
                logger.info("    [%s] GDELT DOC: %d results", claim["id"], len(gdelt_results))
            except Exception as exc:
                logger.warning("    [%s] GDELT DOC FAILED: %s", claim["id"], exc)

            # 3. GDELT Context
            try:
                ctx_results = await search_gdelt_context(
                    claim["claim"],
                    api_url=self.settings.gdelt_context_api_url,
                )
                evidence_batch.extend(ctx_results)
                logger.info("    [%s] GDELT Context: %d results", claim["id"], len(ctx_results))
            except Exception as exc:
                logger.warning("    [%s] GDELT Context FAILED: %s", claim["id"], exc)

            # 4. Official source discovery
            try:
                off_results = await discover_official_sources(claim, state.topic)
                evidence_batch.extend(off_results)
                logger.info("    [%s] Official sources: %d results", claim["id"], len(off_results))
            except Exception as exc:
                logger.warning("    [%s] Official sources FAILED: %s", claim["id"], exc)

            # 5. News source discovery
            try:
                news_results = await discover_news_sources(queries)
                evidence_batch.extend(news_results)
                logger.info("    [%s] News sources: %d results", claim["id"], len(news_results))
            except Exception as exc:
                logger.warning("    [%s] News sources FAILED: %s", claim["id"], exc)

            # 6. Cited source mining (URL input)
            if state.cited_links:
                try:
                    cited_results = await mine_cited_sources(state.cited_links, claim)
                    evidence_batch.extend(cited_results)
                    logger.info("    [%s] Cited sources: %d results", claim["id"], len(cited_results))
                except Exception as exc:
                    logger.warning("    [%s] Cited sources FAILED: %s", claim["id"], exc)

            # 7. Official social discovery
            try:
                social_results = await discover_official_social(claim)
                evidence_batch.extend(social_results)
            except Exception as exc:
                logger.warning("    [%s] Social FAILED: %s", claim["id"], exc)

            logger.info("    [%s] TOTAL evidence for claim: %d items", claim["id"], len(evidence_batch))

            # Tag evidence with claim id
            for ev in evidence_batch:
                ev.setdefault("matched_claim_ids", [])
                if claim["id"] not in ev["matched_claim_ids"]:
                    ev["matched_claim_ids"].append(claim["id"])

            all_evidence.extend(evidence_batch)

            # Track unique sources
            for ev in evidence_batch:
                sid = ev.get("source_id", "")
                if sid and sid not in all_sources:
                    all_sources[sid] = {
                        "source_id": sid,
                        "source_name": ev.get("source_name", ""),
                        "source_type": ev.get("source_type", "news"),
                        "url": ev.get("url", ""),
                        "tier": ev.get("tier", "C"),
                        "published_at": ev.get("published_at", ""),
                    }

        # Cap evidence per claim
        state.evidence_items = all_evidence[: self.settings.max_evidence_per_claim * len(state.claims)]
        state.sources_used = list(all_sources.values())
        return state
