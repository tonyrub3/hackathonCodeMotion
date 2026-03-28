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
        language: str = "en",
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

        steps: list[tuple[str, Any]] = [
            ("input_normalizer", self.input_normalizer),
            ("claim_decomposition", self.claim_decomposer),
            ("source_discovery", self.source_discoverer),
            ("evidence_analysis", self.evidence_analyzer),
        ]

        # Site forensics only for URL input
        if input_type == "url":
            steps.append(("site_forensics", self.site_forensics))

        steps.append(("judge", self.judge))

        for step_name, agent in steps:
            t0 = time.time()
            try:
                logger.info("Running step: %s (request=%s)", step_name, state.request_id)
                state = await agent.run(state)
            except Exception as exc:
                logger.exception("Step %s failed: %s", step_name, exc)
                state.errors.append(f"{step_name}: {exc}")
            state.timings[step_name] = round(time.time() - t0, 3)

        return state
