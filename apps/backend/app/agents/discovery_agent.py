"""Agent 4 - full source discovery using Tavily as the recall engine."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from app.config import Settings
from app.connectors.tavily_extract import tavily_extract
from app.connectors.tavily_search import tavily_search
from app.core.state import PipelineState

from ._agent_utils import canonicalize_url, domain_from_url, stable_id

logger = logging.getLogger(__name__)


BLACKLIST_DOMAINS = {
    "reddit.com",
    "quora.com",
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
    "youtube.com",
}


class DiscoveryAgent:
    """Collect all discovered sources before any trust filtering."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, state: PipelineState) -> PipelineState:
        discovered: dict[str, dict[str, Any]] = {}
        rejected: list[dict[str, Any]] = []
        answer_hints: list[dict[str, Any]] = []

        for plan in state.query_plan:
            claim_id = str(plan["claim_id"])
            queries = plan.get("queries", []) or []
            for position, query in enumerate(queries):
                data = await tavily_search(
                    query=str(query),
                    search_depth="advanced",
                    max_results=8,
                    include_answer="basic",
                    include_raw_content=True,
                    auto_parameters=True,
                    topic="news",
                    exclude_domains=sorted(BLACKLIST_DOMAINS),
                )
                answer = data.get("answer")
                if answer:
                    answer_hints.append({"claim_id": claim_id, "query": query, "answer": answer})
                for rank, result in enumerate(data.get("results", []), start=1):
                    url = canonicalize_url(result.get("url", ""))
                    if not url:
                        rejected.append({"url": result.get("url", ""), "reason": "missing_url", "claim_id": claim_id})
                        continue
                    current = discovered.get(url)
                    score = float(result.get("score", 0.0))
                    if current is None:
                        discovered[url] = {
                            "source_id": stable_id("src", url),
                            "url": url,
                            "source_name": result.get("title") or domain_from_url(url),
                            "title": result.get("title", ""),
                            "snippet": result.get("content", ""),
                            "raw_content": result.get("raw_content", ""),
                            "score": score,
                            "query_hits": [{"claim_id": claim_id, "query": str(query), "rank": rank, "position": position}],
                            "claim_ids": [claim_id],
                            "answer_hints": [answer] if answer else [],
                            "domain": domain_from_url(url),
                        }
                    else:
                        current["score"] = max(float(current.get("score", 0.0)), score)
                        current["query_hits"].append({"claim_id": claim_id, "query": str(query), "rank": rank, "position": position})
                        if claim_id not in current["claim_ids"]:
                            current["claim_ids"].append(claim_id)
                        if answer:
                            current["answer_hints"].append(answer)

        ranked = sorted(
            discovered.values(),
            key=lambda item: (len(item.get("claim_ids", [])), float(item.get("score", 0.0))),
            reverse=True,
        )
        selected: list[dict[str, Any]] = []
        domain_counts: defaultdict[str, int] = defaultdict(int)
        for item in ranked:
            domain = item.get("domain", "")
            if len(selected) >= 10:
                rejected.append({"source_id": item["source_id"], "url": item["url"], "reason": "selection_cutoff"})
                continue
            if domain_counts[domain] >= 2 and len(item.get("claim_ids", [])) <= 1:
                rejected.append({"source_id": item["source_id"], "url": item["url"], "reason": "domain_overrepresented"})
                continue
            domain_counts[domain] += 1
            item["selection_reason"] = "high_recall_rank"
            selected.append(item)

        await self._enrich_selected(selected, state)

        state.all_sources_found = ranked
        state.selected_sources = selected
        state.rejected_sources = rejected
        state.sources_used = list(selected)
        state.layer_outputs["discovery"] = {
            "all_sources_found": ranked,
            "selected_sources": selected,
            "rejected_sources": rejected,
            "answer_hints": answer_hints,
        }
        logger.info("    discovery found=%d selected=%d rejected=%d", len(ranked), len(selected), len(rejected))
        return state

    async def _enrich_selected(self, selected: list[dict[str, Any]], state: PipelineState) -> None:
        urls = [
            item["url"]
            for item in selected
            if len(item.get("raw_content", "")) < 200
        ]
        if not urls:
            return
        query = " ".join(plan.get("claim", "") for plan in state.query_plan)[:500]
        extract = await tavily_extract(
            urls=urls[:10],
            query=query,
            chunks_per_source=4,
            extract_depth="advanced",
        )
        by_url = {canonicalize_url(item.get("url", "")): item for item in extract.get("results", [])}
        for item in selected:
            enriched = by_url.get(item["url"])
            if not enriched:
                continue
            chunks = enriched.get("chunks", [])
            if chunks and not item.get("raw_content"):
                item["raw_content"] = "\n".join(str(chunk) for chunk in chunks[:4])
            if enriched.get("content") and not item.get("snippet"):
                item["snippet"] = str(enriched["content"])[:500]
            if enriched.get("published_at"):
                item["published_at"] = enriched["published_at"]
