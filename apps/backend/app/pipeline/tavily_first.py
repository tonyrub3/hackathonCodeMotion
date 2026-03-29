"""Agentic Tavily-first runtime built on the current implementation."""

from __future__ import annotations

import logging
import time

from app.agents.claim_decomposition_agent import ClaimDecompositionAgent
from app.agents.claim_scoring_agent import ClaimScoringAgent
from app.agents.discovery_agent import DiscoveryAgent
from app.agents.evidence_linking_agent import EvidenceLinkingAgent
from app.agents.explanation_agent import ExplanationAgent
from app.agents.query_planning_agent import QueryPlanningAgent
from app.agents.source_forensics_agent import SourceForensicsAgent
from app.agents.verdict_consistency_agent import VerdictConsistencyAgent
from app.config import Settings
from app.core.state import PipelineState

logger = logging.getLogger(__name__)


class TavilyFirstEngine:
    """Compatibility wrapper that now runs a claim-centric agent pipeline."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.claim_decomposition = ClaimDecompositionAgent(settings)
        self.query_planning = QueryPlanningAgent(settings)
        self.discovery = DiscoveryAgent(settings)
        self.source_forensics = SourceForensicsAgent(settings)
        self.evidence_linking = EvidenceLinkingAgent(settings)
        self.claim_scoring = ClaimScoringAgent(settings)
        self.verdict_consistency = VerdictConsistencyAgent(settings)
        self.explanation = ExplanationAgent(settings)

    async def run(self, state: PipelineState) -> PipelineState:
        text = state.normalized_text or state.raw_content
        if not text.strip():
            state.verdict = "insufficient_evidence"
            state.errors.append("agentic_tavily: empty input")
            return state

        steps = [
            ("claim_decomposition", self.claim_decomposition),
            ("query_planning", self.query_planning),
            ("discovery", self.discovery),
            ("source_forensics", self.source_forensics),
            ("evidence_linking", self.evidence_linking),
            ("claim_scoring", self.claim_scoring),
            ("verdict_consistency", self.verdict_consistency),
            ("explanation", self.explanation),
        ]

        total_t0 = time.time()
        for step_name, agent in steps:
            t0 = time.time()
            state = await agent.run(state)
            state.timings[step_name] = round(time.time() - t0, 3)

        alignment_rules = self.verdict_consistency.validate_explanation_alignment(state)
        if alignment_rules:
            state.explanation.setdefault("caveats", []).extend(alignment_rules)

        state.timings["agentic_runtime_total"] = round(time.time() - total_t0, 3)
        state.sources_used = [
            {
                "source_id": source.get("source_id", ""),
                "source_name": source.get("source_name") or source.get("domain", ""),
                "source_type": "web",
                "url": source.get("url", ""),
                "tier": "A" if float(source.get("forensic_score", 0.0)) >= 0.75 else "B" if float(source.get("forensic_score", 0.0)) >= 0.5 else "C",
                "source_reliability_score": float(source.get("forensic_score", 0.0)),
                "dimensions": source.get("dimensions", {}),
            }
            for source in state.selected_sources
        ]
        state.linguistic_risk = self._linguistic_risk(text)
        return state

    def _linguistic_risk(self, text: str) -> dict[str, object]:
        low = (text or "").lower()
        markers = [marker for marker in ("shock", "breaking", "incredibile", "assurdo", "bomba", "urgent") if marker in low]
        return {
            "sensationalism_score": min(1.0, len(markers) * 0.2),
            "emotional_tone_score": min(1.0, len(markers) * 0.15),
            "attribution_risk": 0.0,
            "uncertainty_score": 0.0,
            "manipulation_markers": markers,
        }
