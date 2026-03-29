"""Post-crosscheck evidence/source aggregation."""

from __future__ import annotations

from typing import Any

from .source_scoring import domain_from_url, domain_reliability, source_tier, SourceScoringLayer


class EvidenceScoringLayer:
    """Build source and evidence records from retrieved results plus cross-check output."""

    def __init__(self) -> None:
        self.source_scoring = SourceScoringLayer()

    def build_records(
        self,
        results: list[dict[str, Any]],
        analysis: dict[str, Any],
        search_tier: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        per_source = {ps.get("source_index", -1): ps for ps in analysis.get("per_source", [])}
        sources_used: list[dict[str, Any]] = []
        scored_evidence: list[dict[str, Any]] = []
        contradictions: list[dict[str, Any]] = []

        for i, result in enumerate(results):
            url = result.get("url", "")
            domain = domain_from_url(url)
            domain_trust = float(result.get("_domain_trust", domain_reliability(domain)))
            content_trust = float(result.get("_content_trust", self.source_scoring.content_trust_score(self.source_scoring.source_body(result))))
            source_reliability = float(result.get("_source_reliability", self.source_scoring.combine_source_trust(domain_trust, content_trust)))
            tier = source_tier(source_reliability)
            sid = f"s{i+1}"
            is_primary = result.get("_tier") != "tier2" and search_tier != "tier2"

            per_source_row = per_source.get(i, {})
            llm_relevance = float(per_source_row.get("relevance", result.get("_local_relevance", result.get("score", 0.5))))
            local_relevance = float(result.get("_local_relevance", 0.0))
            claim_relevance = round(min(1.0, 0.65 * llm_relevance + 0.35 * local_relevance), 3)

            sources_used.append(
                {
                    "source_id": sid,
                    "source_name": domain,
                    "source_type": "primary_media" if is_primary else "local_media",
                    "url": url,
                    "tier": tier,
                    "source_reliability_score": source_reliability,
                    "dimensions": {
                        "domain_trust": round(domain_trust, 3),
                        "content_trust": round(content_trust, 3),
                        "claim_relevance": claim_relevance,
                        "local_relevance": round(local_relevance, 3),
                        "tavily_score": round(float(result.get("score", 0.5)), 3),
                        "is_primary": 1.0 if is_primary else 0.0,
                    },
                }
            )

            stance = per_source_row.get("stance", "neutral")
            excerpt = per_source_row.get("key_excerpt", "") or (result.get("content") or "")[:300]
            scored_evidence.append(
                {
                    "source_id": sid,
                    "stance": stance,
                    "evidence_score": round(0.45 * claim_relevance + 0.35 * source_reliability + 0.20 * float(result.get("score", 0.5)), 3),
                    "excerpt": excerpt[:400],
                }
            )

            if stance == "contradicting":
                contradictions.append(
                    {
                        "claim_id": "",
                        "type": "source_conflict",
                        "description": f"{domain}: {excerpt[:200]}",
                        "severity": round(claim_relevance * source_reliability, 2),
                    }
                )

        return sources_used, scored_evidence, contradictions
