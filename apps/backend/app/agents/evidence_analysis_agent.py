"""
Agent 4 – Evidence & Source Analysis.

Responsibilities:
  - Classify stance of each evidence item (supporting / contradicting / neutral)
  - Compute source reliability scores
  - Compute evidence scores
  - Detect contradictions
  - Aggregate consensus / conflict signals
  - Detect temporal mismatches

Tools used:
  - stance_classifier
  - source_reliability_scorer
  - evidence_scorer
  - consensus_builder
  - conflict_detector
  - temporal_validator
  - independence_checker
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.core.state import PipelineState
from app.services.scoring.source_reliability import compute_source_reliability
from app.services.scoring.evidence_score import compute_evidence_score
from app.services.llm.regolo_client import RegoloClient

logger = logging.getLogger(__name__)


class EvidenceAnalysisAgent:
    """Score evidence, compute source reliability, detect contradictions."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = RegoloClient(settings)

    async def run(self, state: PipelineState) -> PipelineState:
        """
        Input contract:  state.evidence_items, state.sources_used, state.claims
        Output contract: state.scored_evidence, state.sources_used (enriched),
                         state.contradictions, state.consensus_signals
        """
        scored: list[dict[str, Any]] = []
        source_scores: dict[str, dict[str, Any]] = {}

        for ev in state.evidence_items:
            # 1. Classify stance
            ev["stance"] = await self._classify_stance(ev, state.claims)

            # 2. Compute source reliability
            sid = ev.get("source_id", "")
            if sid not in source_scores:
                reliability = compute_source_reliability(ev)
                source_scores[sid] = reliability
            else:
                reliability = source_scores[sid]

            ev["source_reliability_score"] = reliability["total"]
            ev["dimensions"] = reliability["dimensions"]

            # 3. Compute evidence score
            ev["evidence_score"] = compute_evidence_score(
                source_reliability=reliability["total"],
                relevance=ev.get("relevance_score", 0.5),
                directness=self._estimate_directness(ev),
                specificity=self._estimate_specificity(ev),
                temporal_fit=self._estimate_temporal_fit(ev),
                geographic_fit=0.5,
            )

            scored.append(ev)

        state.scored_evidence = scored

        # Enrich sources_used with reliability data
        for src in state.sources_used:
            sid = src.get("source_id", "")
            if sid in source_scores:
                src["source_reliability_score"] = source_scores[sid]["total"]
                src["dimensions"] = source_scores[sid]["dimensions"]

        # Detect contradictions
        state.contradictions = self._detect_contradictions(scored, state.claims)

        # Build consensus signals
        state.consensus_signals = self._build_consensus(scored, state.claims)

        return state

    async def _classify_stance(
        self, evidence: dict[str, Any], claims: list[dict[str, Any]]
    ) -> str:
        """Classify evidence stance relative to matched claims."""
        excerpt = evidence.get("excerpt", "")
        if not excerpt:
            return "neutral"

        matched_ids = evidence.get("matched_claim_ids", [])
        claim_texts = [c["claim"] for c in claims if c["id"] in matched_ids]
        if not claim_texts:
            return "neutral"

        # Try LLM classification
        prompt = (
            "Given the claim and evidence excerpt below, classify the evidence stance as "
            "exactly one of: supporting, contradicting, neutral.\n\n"
            f"Claim: {claim_texts[0]}\n"
            f"Evidence: {excerpt}\n\n"
            "Stance:"
        )
        try:
            response = await self.llm.complete_text(prompt, max_tokens=20)
            response = response.strip().lower()
            if "supporting" in response:
                return "supporting"
            if "contradict" in response:
                return "contradicting"
            return "neutral"
        except Exception:
            return "neutral"

    def _estimate_directness(self, evidence: dict[str, Any]) -> float:
        """Heuristic directness score based on evidence properties."""
        score = 0.5
        if evidence.get("source_type") in ("official", "factcheck"):
            score += 0.2
        if evidence.get("tier") == "A":
            score += 0.15
        if len(evidence.get("excerpt", "")) > 100:
            score += 0.1
        return min(1.0, score)

    def _estimate_specificity(self, evidence: dict[str, Any]) -> float:
        """Heuristic specificity score."""
        excerpt = evidence.get("excerpt", "")
        score = 0.4
        # Contains numbers → more specific
        if any(c.isdigit() for c in excerpt):
            score += 0.2
        # Contains quotes
        if '"' in excerpt or "'" in excerpt:
            score += 0.1
        if len(excerpt) > 200:
            score += 0.15
        return min(1.0, score)

    def _estimate_temporal_fit(self, evidence: dict[str, Any]) -> float:
        """Heuristic temporal fit. In production, compare dates properly."""
        if evidence.get("published_at"):
            return 0.7  # Has a date → moderate trust
        return 0.4

    def _detect_contradictions(
        self, scored: list[dict[str, Any]], claims: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect explicit contradictions between evidence items for the same claim."""
        contradictions: list[dict[str, Any]] = []
        by_claim: dict[str, list[dict[str, Any]]] = {}
        for ev in scored:
            for cid in ev.get("matched_claim_ids", []):
                by_claim.setdefault(cid, []).append(ev)

        for cid, evs in by_claim.items():
            supporting = [e for e in evs if e["stance"] == "supporting"]
            contradicting = [e for e in evs if e["stance"] == "contradicting"]
            if supporting and contradicting:
                contradictions.append({
                    "claim_id": cid,
                    "type": "stance_conflict",
                    "description": (
                        f"{len(supporting)} source(s) support and "
                        f"{len(contradicting)} source(s) contradict this claim."
                    ),
                    "evidence_a_id": supporting[0].get("source_id", ""),
                    "evidence_b_id": contradicting[0].get("source_id", ""),
                    "severity": min(1.0, len(contradicting) / max(len(supporting), 1)),
                })
        return contradictions

    def _build_consensus(
        self, scored: list[dict[str, Any]], claims: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Build per-claim consensus signals."""
        consensus: dict[str, Any] = {}
        for claim in claims:
            cid = claim["id"]
            relevant = [e for e in scored if cid in e.get("matched_claim_ids", [])]
            supporting = sum(1 for e in relevant if e["stance"] == "supporting")
            contradicting = sum(1 for e in relevant if e["stance"] == "contradicting")
            total = max(len(relevant), 1)
            consensus[cid] = {
                "total_evidence": len(relevant),
                "supporting": supporting,
                "contradicting": contradicting,
                "neutral": total - supporting - contradicting,
                "consensus_ratio": supporting / total,
                "conflict_ratio": contradicting / total,
            }
        return consensus
