"""Agent 7 - deterministic claim-level scoring."""

from __future__ import annotations

import logging

from app.config import Settings
from app.core.state import PipelineState

logger = logging.getLogger(__name__)


class ClaimScoringAgent:
    """Aggregate linked evidence into per-claim scores."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, state: PipelineState) -> PipelineState:
        claim_scores: list[dict[str, object]] = []
        contradictions: list[dict[str, object]] = []

        for claim in state.claims:
            relevant = [item for item in state.evidence_items if item.get("claim_id") == claim["id"]]
            direct_support = [item for item in relevant if item.get("evidence_type") == "direct" and item.get("stance") == "supporting"]
            direct_contra = [item for item in relevant if item.get("evidence_type") == "direct" and item.get("stance") == "contradicting"]
            usable = [item for item in relevant if item.get("evidence_type") in {"direct", "indirect", "context"}]
            direct_count = len(direct_support) + len(direct_contra)
            support_score = round(sum(float(item.get("evidence_score", 0.0)) for item in direct_support) / max(len(direct_support), 1), 3) if direct_support else 0.0
            contradiction_score = round(sum(float(item.get("evidence_score", 0.0)) for item in direct_contra) / max(len(direct_contra), 1), 3) if direct_contra else 0.0
            claim_coverage = round(min(1.0, 0.5 * min(direct_count, 2) / 2.0 + 0.5 * min(len(usable), 3) / 3.0), 3)
            source_diversity = round(min(1.0, len({item.get('source_id') for item in usable}) / 3.0), 3)
            temporal_alignment = round(
                sum(float(item.get("temporal_alignment", 0.0)) for item in usable) / len(usable),
                3,
            ) if usable else 0.25
            forensic_support = round(
                sum(float(item.get("forensic_score", 0.5)) for item in usable) / len(usable),
                3,
            ) if usable else 0.25

            confidence = min(
                1.0,
                0.35 * claim_coverage
                + 0.20 * source_diversity
                + 0.20 * forensic_support
                + 0.15 * temporal_alignment
                + 0.10 * min(len(usable), 4) / 4.0,
            )
            if direct_count == 0:
                confidence = min(confidence, 0.35)
            if contradiction_score >= 0.55:
                confidence = min(confidence, 0.55)
            if claim.get("time_sensitive") and claim_coverage < 0.45:
                confidence = min(confidence, 0.40)

            partial_score = max(
                0.0,
                min(
                    100.0,
                    100.0
                    * (
                        0.48 * support_score
                        - 0.55 * contradiction_score
                        + 0.15 * claim_coverage
                        + 0.10 * source_diversity
                        + 0.12 * forensic_support
                        + 0.10 * temporal_alignment
                    ),
                ),
            )

            if direct_count == 0:
                partial_verdict = "insufficient_evidence"
            elif contradiction_score >= 0.65 and support_score < 0.35:
                partial_verdict = "false"
            elif contradiction_score >= 0.45 and support_score < 0.40:
                partial_verdict = "mostly_false"
            elif support_score >= 0.60 and confidence >= 0.70 and direct_count >= 2:
                partial_verdict = "verified"
            elif support_score >= 0.48 and confidence >= 0.50 and direct_support:
                partial_verdict = "mostly_verified"
            elif direct_support and direct_contra:
                partial_verdict = "mixed"
            else:
                partial_verdict = "insufficient_evidence"

            score = {
                "claim_id": claim["id"],
                "claim": claim["claim"],
                "support_score": support_score,
                "contradiction_score": contradiction_score,
                "claim_coverage": claim_coverage,
                "source_diversity": source_diversity,
                "temporal_alignment": temporal_alignment,
                "forensic_support": forensic_support,
                "confidence_score": round(confidence, 3),
                "partial_score": round(partial_score, 1),
                "partial_verdict": partial_verdict,
                "direct_supporting_evidence": len(direct_support),
                "direct_contradicting_evidence": len(direct_contra),
                "direct_evidence_count": direct_count,
            }
            claim_scores.append(score)

            if direct_contra:
                contradictions.append(
                    {
                        "claim_id": claim["id"],
                        "type": "direct_contradiction",
                        "description": f"{len(direct_contra)} direct contradicting source(s) for this claim.",
                        "severity": contradiction_score,
                    }
                )

        state.claim_scores = claim_scores
        state.contradictions = contradictions
        state.scored_evidence = state.evidence_items
        for claim in state.claims:
            score = next((item for item in claim_scores if item["claim_id"] == claim["id"]), None)
            if score:
                claim["partial_verdict"] = score["partial_verdict"]
                claim["partial_score"] = score["partial_score"]
                claim["checkability_score"] = score["claim_coverage"]
        state.layer_outputs["claim_scoring"] = {"claim_scores": claim_scores}
        logger.info("    claim scores computed: %d", len(claim_scores))
        return state
