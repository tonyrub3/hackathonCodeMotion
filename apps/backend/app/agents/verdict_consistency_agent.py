"""Agent 8 - aggregate claims and enforce deterministic verdict constraints."""

from __future__ import annotations

import logging

from app.config import Settings
from app.core.state import PipelineState

logger = logging.getLogger(__name__)


class VerdictConsistencyAgent:
    """Produce the final verdict and apply hard consistency rules."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, state: PipelineState) -> PipelineState:
        if not state.claim_scores:
            state.verdict = "insufficient_evidence"
            state.truth_score = 0.0
            state.confidence_score = 0.0
            return state

        support = sum(float(item.get("support_score", 0.0)) for item in state.claim_scores) / len(state.claim_scores)
        contradiction = sum(float(item.get("contradiction_score", 0.0)) for item in state.claim_scores) / len(state.claim_scores)
        coverage = sum(float(item.get("claim_coverage", 0.0)) for item in state.claim_scores) / len(state.claim_scores)
        confidence = sum(float(item.get("confidence_score", 0.0)) for item in state.claim_scores) / len(state.claim_scores)
        direct_support_count = sum(int(item.get("direct_supporting_evidence", 0)) for item in state.claim_scores)
        direct_contra_count = sum(int(item.get("direct_contradicting_evidence", 0)) for item in state.claim_scores)

        truth_score = max(
            0.0,
            min(
                100.0,
                100.0
                * (
                    0.52 * support
                    - 0.60 * contradiction
                    + 0.18 * coverage
                    + 0.15 * min(1.0, len(state.selected_sources) / 5.0)
                    + 0.15 * min(1.0, len(state.source_forensics) / 5.0)
                ),
            ),
        )

        applied_rules: list[str] = []
        verdict = "mixed"
        if direct_support_count == 0:
            applied_rules.append("blocked_high_verdict_without_direct_support")
            confidence = min(confidence, 0.35)
        if contradiction >= 0.55:
            applied_rules.append("capped_confidence_due_to_strong_contradictions")
            confidence = min(confidence, 0.55)
        if any(item.get("direct_evidence_count", 0) == 0 and item.get("claim_coverage", 0.0) < 0.45 for item in state.claim_scores):
            applied_rules.append("insufficient_recent_or_low_coverage_claim_present")

        if direct_support_count == 0 and direct_contra_count == 0:
            verdict = "insufficient_evidence"
        elif contradiction >= 0.65 and support < 0.35:
            verdict = "false"
        elif contradiction >= 0.45 and support < 0.40:
            verdict = "mostly_false"
        elif support >= 0.58 and confidence >= 0.70 and direct_support_count >= 2:
            verdict = "verified"
        elif support >= 0.45 and confidence >= 0.50 and direct_support_count >= 1:
            verdict = "mostly_verified"
        elif direct_support_count > 0 and direct_contra_count > 0:
            verdict = "mixed"
        else:
            verdict = "insufficient_evidence"

        if direct_support_count == 0 and verdict in {"verified", "mostly_verified"}:
            verdict = "insufficient_evidence"
            confidence = min(confidence, 0.35)
            applied_rules.append("downgraded_because_direct_support_is_zero")

        state.truth_score = round(truth_score, 1)
        state.confidence_score = round(confidence, 3)
        state.verdict = verdict
        state.layer_outputs["verdict_consistency"] = {
            "support": round(support, 3),
            "contradiction": round(contradiction, 3),
            "coverage": round(coverage, 3),
            "applied_rules": applied_rules,
            "verdict": verdict,
            "truth_score": state.truth_score,
            "confidence_score": state.confidence_score,
        }
        logger.info("    final verdict=%s truth=%.1f confidence=%.2f", verdict, state.truth_score, state.confidence_score)
        return state

    def validate_explanation_alignment(self, state: PipelineState) -> list[str]:
        """Downgrade if the explanation contradicts structured signals."""
        summary = str(state.explanation.get("summary", "")).lower()
        why = str(state.explanation.get("why", "")).lower()
        text = f"{summary} {why}"
        reasons: list[str] = []

        if state.verdict in {"verified", "mostly_verified"} and any(
            marker in text for marker in ("not confirm", "non conferma", "insufficient", "prove insufficienti")
        ):
            state.verdict = "insufficient_evidence"
            state.confidence_score = min(state.confidence_score, 0.35)
            reasons.append("explanation_conflicted_with_positive_verdict")

        if state.verdict in {"false", "mostly_false"} and any(
            marker in text for marker in ("supported", "conferma", "confirmed")
        ):
            state.verdict = "mixed"
            state.confidence_score = min(state.confidence_score, 0.5)
            reasons.append("explanation_conflicted_with_negative_verdict")

        if reasons:
            report = state.layer_outputs.setdefault("verdict_consistency", {})
            report["explanation_alignment_rules"] = reasons
        return reasons
