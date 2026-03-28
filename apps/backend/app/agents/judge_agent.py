"""
Agent 6 – Judge / Report.

Responsibilities:
  - Combine all structured outputs
  - Compute deterministic truth score
  - Map score to nuanced verdict
  - Assign confidence
  - Generate structured explanation
  - Produce claim-by-claim partial verdicts
  - Return all sources used

Tools used:
  - truth_score_calculator
  - verdict_mapper
  - partial_verdict_builder
  - explanation_builder
  - source_summary_builder
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.core.state import PipelineState
from app.services.scoring.truth_score import compute_truth_score
from app.services.scoring.verdict_mapping import map_verdict
from app.services.scoring.confidence_score import compute_confidence
from app.services.reporting.explanation_builder import build_explanation
from app.services.reporting.source_summary_builder import build_source_summary

logger = logging.getLogger(__name__)


class JudgeAgent:
    """Produce the final verdict, scores, and explanation."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, state: PipelineState) -> PipelineState:
        """
        Input contract:  state.scored_evidence, state.sources_used,
                         state.claims, state.contradictions,
                         state.consensus_signals, state.site_forensics
        Output contract: state.truth_score, state.confidence_score,
                         state.verdict, state.partial_verdicts,
                         state.explanation, state.linguistic_risk
        """
        # 1. Compute partial verdicts per claim
        partial_verdicts = self._compute_partial_verdicts(state)
        state.partial_verdicts = partial_verdicts
        for pv in partial_verdicts:
            logger.info("    PARTIAL [%s] %s (score=%.1f): %s",
                         pv["id"], pv["partial_verdict"],
                         pv["partial_score"], pv["claim"][:60])

        # 2. Linguistic risk (lightweight)
        state.linguistic_risk = self._assess_linguistic_risk(state.normalized_text, state.language)
        if state.linguistic_risk.get("manipulation_markers"):
            logger.info("    linguistic risk markers: %s", state.linguistic_risk["manipulation_markers"])

        # 3. Compute global truth score
        truth_score = compute_truth_score(
            scored_evidence=state.scored_evidence,
            consensus_signals=state.consensus_signals,
            claims=state.claims,
            contradictions=state.contradictions,
            site_forensics=state.site_forensics,
            linguistic_risk=state.linguistic_risk,
        )
        state.truth_score = truth_score
        logger.info("    truth_score = %.1f", truth_score)

        # 4. Compute confidence
        state.confidence_score = compute_confidence(
            evidence_count=len(state.scored_evidence),
            source_count=len(state.sources_used),
            avg_source_reliability=self._avg_reliability(state.sources_used),
            has_contradictions=len(state.contradictions) > 0,
        )
        logger.info("    confidence = %.2f", state.confidence_score)

        # 5. Map to verdict
        state.verdict = map_verdict(
            truth_score=truth_score,
            confidence=state.confidence_score,
            evidence_count=len(state.scored_evidence),
            contradictions=state.contradictions,
        )

        logger.info("    VERDICT = %s", state.verdict)

        # 6. Build explanation
        state.explanation = build_explanation(
            verdict=state.verdict,
            truth_score=truth_score,
            claims=state.claims,
            scored_evidence=state.scored_evidence,
            contradictions=state.contradictions,
            sources_used=state.sources_used,
            source_summary=build_source_summary(state.sources_used, language=state.language),
            site_forensics=state.site_forensics,
            language=state.language,
        )

        return state

    def _compute_partial_verdicts(self, state: PipelineState) -> list[dict[str, Any]]:
        """Compute a verdict for each individual claim."""
        results: list[dict[str, Any]] = []
        for claim in state.claims:
            cid = claim["id"]
            relevant_ev = [
                e for e in state.scored_evidence
                if cid in e.get("matched_claim_ids", [])
            ]

            if not relevant_ev:
                results.append({
                    "id": cid,
                    "claim": claim["claim"],
                    "type": claim.get("type", "event"),
                    "partial_verdict": "insufficient_evidence",
                    "partial_score": 0.0,
                    "checkability_score": claim.get("checkability_score", 0.5),
                })
                continue

            # Partial truth score from evidence for this claim
            support_strength = sum(
                e["evidence_score"] for e in relevant_ev if e["stance"] == "supporting"
            )
            contra_strength = sum(
                e["evidence_score"] for e in relevant_ev if e["stance"] == "contradicting"
            )
            total = max(len(relevant_ev), 1)

            partial_score = ((support_strength / total) * 100) - ((contra_strength / total) * 30)
            partial_score = max(0.0, min(100.0, partial_score))

            partial_verdict = map_verdict(
                truth_score=partial_score,
                confidence=0.5,
                evidence_count=len(relevant_ev),
                contradictions=[
                    c for c in state.contradictions if c.get("claim_id") == cid
                ],
            )

            results.append({
                "id": cid,
                "claim": claim["claim"],
                "type": claim.get("type", "event"),
                "partial_verdict": partial_verdict,
                "partial_score": round(partial_score, 1),
                "checkability_score": claim.get("checkability_score", 0.5),
            })

        return results

    def _avg_reliability(self, sources: list[dict[str, Any]]) -> float:
        """Average source reliability across all sources."""
        if not sources:
            return 0.0
        return sum(s.get("source_reliability_score", 0.5) for s in sources) / len(sources)

    def _assess_linguistic_risk(self, text: str, language: str = "en") -> dict[str, Any]:
        """Lightweight linguistic risk assessment from surface patterns."""
        if not text:
            return {}

        text_lower = self._normalize_for_match(text)

        # Sensationalism
        sensational_words = [
            "shocking", "explosive", "bombshell", "devastating", "incredible",
            "unbelievable", "breaking", "urgent", "exclusive", "scandal",
            "scioccante", "esplosivo", "clamoroso", "devastante", "incredibile",
            "allarmante", "urgente", "esclusivo", "scandalo",
        ]
        sens_count = sum(1 for w in sensational_words if w in text_lower)
        sensationalism = min(1.0, sens_count * 0.15)

        # Attribution risk
        vague_attr = [
            "according to some", "sources say", "it is believed",
            "reportedly", "allegedly", "some experts",
            "secondo alcuni", "fonti dicono", "si crede", "si ritiene",
            "pare", "presumibilmente", "sarebbe", "alcuni esperti", "si dice", "circola",
        ]
        attr_count = sum(1 for phrase in vague_attr if phrase in text_lower)
        attribution_risk = min(1.0, attr_count * 0.2)

        # Uncertainty markers
        uncertainty = [
            "might", "could", "possibly", "perhaps", "unclear",
            "unconfirmed", "rumor", "speculation",
            "potrebbe", "potrebbero", "forse", "probabilmente",
            "non confermato", "voci", "speculazione", "incerto",
        ]
        unc_count = sum(1 for w in uncertainty if w in text_lower)
        uncertainty_score = min(1.0, unc_count * 0.15)

        # Manipulation markers (collect actual phrases found)
        manipulation_markers: list[str] = []
        for phrase in vague_attr + sensational_words:
            if phrase in text_lower:
                manipulation_markers.append(phrase)

        return {
            "sensationalism_score": round(sensationalism, 2),
            "emotional_tone_score": round(sensationalism * 0.8, 2),
            "attribution_risk": round(attribution_risk, 2),
            "uncertainty_score": round(uncertainty_score, 2),
            "manipulation_markers": manipulation_markers,
        }

    def _normalize_for_match(self, text: str) -> str:
        """Lowercase and strip accents for robust marker matching."""
        import unicodedata

        normalized = unicodedata.normalize("NFKD", text or "")
        stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return stripped.casefold()
