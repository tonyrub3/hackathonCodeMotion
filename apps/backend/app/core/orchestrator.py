"""
Orchestrator – drives the linear verification pipeline.

Pipeline stages:
  1. Input Normalizer
  2. Claim Decomposition
  3. Source Discovery
  4. Evidence & Source Analysis
  5. Site Forensics (URL only)
  6. Judge / Report
"""

from __future__ import annotations

import time
import uuid
import logging
from typing import Any

from app.config import Settings
from app.core.state import PipelineState
from app.agents.input_normalizer_agent import InputNormalizerAgent
from app.agents.claim_decomposition_agent import ClaimDecompositionAgent
from app.agents.source_discovery_agent import SourceDiscoveryAgent
from app.agents.evidence_analysis_agent import EvidenceAnalysisAgent
from app.agents.site_forensics_agent import SiteForensicsAgent
from app.agents.judge_agent import JudgeAgent

logger = logging.getLogger(__name__)

STEP_ICONS = {
    "input_normalizer": "1/6",
    "claim_decomposition": "2/6",
    "source_discovery": "3/6",
    "evidence_analysis": "4/6",
    "site_forensics": "5/6",
    "judge": "6/6",
}


class Orchestrator:
    """Runs the full verification pipeline and returns the final state."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.input_normalizer = InputNormalizerAgent(settings)
        self.claim_decomposer = ClaimDecompositionAgent(settings)
        self.source_discoverer = SourceDiscoveryAgent(settings)
        self.evidence_analyzer = EvidenceAnalysisAgent(settings)
        self.site_forensics = SiteForensicsAgent(settings)
        self.judge = JudgeAgent(settings)

    async def verify(
        self,
        content: str,
        input_type: str = "text",
        language: str = "auto",
        country: str = "",
        topic: str = "",
        mode: str = "live",
    ) -> PipelineState:
        """Execute the full pipeline and return the populated state."""
        state = PipelineState(
            request_id=uuid.uuid4().hex[:12],
            input_type=input_type,
            raw_content=content,
            language=language,
            country=country,
            topic=topic,
            mode=mode,
        )

        logger.info("")
        logger.info("=" * 60)
        logger.info("NEW REQUEST [%s]", state.request_id)
        logger.info("  type=%s  mode=%s  lang=%s  topic=%s",
                     input_type, mode, language, topic or "(none)")
        logger.info("  content: %.100s%s", content, "..." if len(content) > 100 else "")
        logger.info("=" * 60)

        steps: list[tuple[str, Any]] = [
            ("input_normalizer", self.input_normalizer),
            ("claim_decomposition", self.claim_decomposer),
            ("source_discovery", self.source_discoverer),
            ("evidence_analysis", self.evidence_analyzer),
        ]

        if input_type == "url":
            steps.append(("site_forensics", self.site_forensics))

        steps.append(("judge", self.judge))

        total_t0 = time.time()
        for step_name, agent in steps:
            icon = STEP_ICONS.get(step_name, "?/?")
            logger.info("")
            logger.info("--- [%s] %s ---", icon, step_name.upper())
            t0 = time.time()
            try:
                state = await agent.run(state)
                elapsed = round(time.time() - t0, 3)
                logger.info("    completed in %.3fs", elapsed)
            except Exception as exc:
                elapsed = round(time.time() - t0, 3)
                logger.error("    FAILED in %.3fs: %s", elapsed, exc, exc_info=True)
                state.errors.append(f"{step_name}: {exc}")
            state.timings[step_name] = elapsed

        total_elapsed = round(time.time() - total_t0, 3)
        logger.info("")
        logger.info("=" * 60)
        logger.info("REQUEST COMPLETE [%s] in %.3fs", state.request_id, total_elapsed)
        logger.info("  verdict:    %s", state.verdict)
        logger.info("  score:      %.1f / 100", state.truth_score)
        logger.info("  confidence: %.0f%%", state.confidence_score * 100)
        logger.info("  claims:     %d", len(state.claims))
        logger.info("  evidence:   %d", len(state.scored_evidence))
        logger.info("  sources:    %d", len(state.sources_used))
        logger.info("  errors:     %d %s", len(state.errors), state.errors if state.errors else "")
        logger.info("  timings:    %s", state.timings)
        logger.info("=" * 60)

        return state
