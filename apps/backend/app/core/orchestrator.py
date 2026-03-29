"""
Orchestrator – Tavily-First simplified pipeline.

Pipeline stages:
  1. Input Normalizer (URL fetch / text cleanup)
  2. Tavily-First Engine (query gen → search → LLM cross-check → verdict)
"""

from __future__ import annotations

import time
import uuid
import logging
from typing import Any

from app.config import Settings
from app.core.state import PipelineState
from app.agents.claim_decomposition_agent import ClaimDecompositionAgent
from app.agents.input_normalizer_agent import InputNormalizerAgent
from app.pipeline.tavily_first import TavilyFirstEngine
from app.utils.pipeline_trace import layer_tag

logger = logging.getLogger(__name__)


class Orchestrator:
    """Runs the Tavily-First verification pipeline and returns the final state."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.input_normalizer = InputNormalizerAgent(settings)
        self.claim_decomposition = ClaimDecompositionAgent(settings)
        self.tavily_engine = TavilyFirstEngine(settings)

    async def verify(
        self,
        content: str,
        input_type: str = "text",
        language: str = "auto",
        country: str = "",
        topic: str = "",
    ) -> PipelineState:
        """Execute the full pipeline and return the populated state."""
        state = PipelineState(
            request_id=uuid.uuid4().hex[:12],
            input_type=input_type,
            raw_content=content,
            language=language,
            country=country,
            topic=topic,
        )

        logger.info("")
        logger.info("=" * 60)
        logger.info("%s new_request id=%s", layer_tag("pipeline"), state.request_id)
        logger.info("  type=%s  lang=%s  topic=%s",
                     input_type, language, topic or "(none)")
        logger.info("  content: %.100s%s", content, "..." if len(content) > 100 else "")
        logger.info("=" * 60)

        steps: list[tuple[str, Any]] = [
            ("input_normalizer", self.input_normalizer),
            ("claim_decomposition", self.claim_decomposition),
            ("tavily_engine", self.tavily_engine),
        ]

        total_t0 = time.time()
        for step_name, agent in steps:
            order = {
                "input_normalizer": "1/3",
                "claim_decomposition": "2/3",
                "tavily_engine": "3/3",
            }.get(step_name, "?/?")
            logger.info("")
            logger.info("%s --- [%s] %s ---", layer_tag("pipeline"), order, step_name.upper())
            t0 = time.time()
            try:
                state = await agent.run(state)
                elapsed = round(time.time() - t0, 3)
                logger.info("%s step=%s completed_in=%.3fs", layer_tag("pipeline"), step_name, elapsed)
            except Exception as exc:
                elapsed = round(time.time() - t0, 3)
                logger.error("%s step=%s failed_in=%.3fs error=%s", layer_tag("pipeline"), step_name, elapsed, exc, exc_info=True)
                state.errors.append(f"{step_name}: {exc}")
            state.timings[step_name] = elapsed

        total_elapsed = round(time.time() - total_t0, 3)
        logger.info("")
        logger.info("=" * 60)
        logger.info("%s request_complete id=%s elapsed=%.3fs", layer_tag("pipeline"), state.request_id, total_elapsed)
        logger.info("  verdict:    %s", state.verdict)
        logger.info("  score:      %.1f / 100", state.truth_score)
        logger.info("  confidence: %.0f%%", state.confidence_score * 100)
        logger.info("  sources:    %d", len(state.sources_used))
        logger.info("  errors:     %d %s", len(state.errors), state.errors if state.errors else "")
        logger.info("  timings:    %s", state.timings)
        logger.info("=" * 60)

        return state
