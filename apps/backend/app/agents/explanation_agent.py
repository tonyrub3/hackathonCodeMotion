"""Agent 9 - build explanation text strictly from structured signals."""

from __future__ import annotations

import logging

from app.config import Settings
from app.core.state import PipelineState

logger = logging.getLogger(__name__)


class ExplanationAgent:
    """Generate deterministic explanations from scored signals only."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, state: PipelineState) -> PipelineState:
        supporting = [item for item in state.scored_evidence if item.get("stance") == "supporting" and item.get("evidence_type") == "direct"]
        contradicting = [item for item in state.scored_evidence if item.get("stance") == "contradicting" and item.get("evidence_type") == "direct"]

        if state.verdict == "verified":
            summary = "Direct evidence from multiple sources supports the main claims."
        elif state.verdict == "mostly_verified":
            summary = "Most of the main claims are supported by direct evidence, with some caveats."
        elif state.verdict in {"false", "mostly_false"}:
            summary = "The main claims are contradicted or not supported by the strongest direct evidence."
        elif state.verdict == "mixed":
            summary = "Some claims are supported while others remain contradicted or only partially covered."
        else:
            summary = "There is not enough direct evidence to confirm the main claims."

        why = (
            f"{len(state.claim_scores)} claim(s) analyzed, "
            f"{len(state.all_sources_found)} source(s) found, "
            f"{len(state.selected_sources)} selected for scoring, "
            f"{len(state.rejected_sources)} rejected. "
            f"Direct supporting evidence: {len(supporting)}. "
            f"Direct contradicting evidence: {len(contradicting)}."
        )
        source_analysis = [
            f"{source.get('source_name') or source.get('domain')}: Tavily {float(source.get('score', 0.0)):.2f}, forensic {float(source.get('forensic_score', 0.0)):.2f}."
            for source in state.selected_sources[:6]
        ]
        caveats = []
        if state.rejected_sources:
            caveats.append(f"{len(state.rejected_sources)} discovered source(s) were not selected for evidence scoring.")
        if any(score.get("direct_evidence_count", 0) == 0 for score in state.claim_scores):
            caveats.append("At least one claim has no direct evidence and was capped to insufficient evidence.")

        state.explanation = {
            "summary": summary,
            "why": why,
            "supporting_evidence": [str(item.get("excerpt", ""))[:220] for item in supporting[:3]],
            "contradicting_evidence": [str(item.get("excerpt", ""))[:220] for item in contradicting[:3]],
            "source_analysis": source_analysis,
            "temporal_context": f"Temporal alignment considered across {len(state.claim_scores)} claim(s).",
            "caveats": caveats,
        }
        state.layer_outputs["explanation"] = state.explanation
        logger.info("    explanation generated")
        return state
