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
from app.agents.input_normalizer_agent import InputNormalizerAgent
from app.pipeline.tavily_first import TavilyFirstEngine

logger = logging.getLogger(__name__)


class Orchestrator:
    """Runs the Tavily-First verification pipeline and returns the final state."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.input_normalizer = InputNormalizerAgent(settings)
        self.tavily_engine = TavilyFirstEngine(settings)

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
            ("tavily_engine", self.tavily_engine),
        ]

        total_t0 = time.time()
        for step_name, agent in steps:
            icon = "1/2" if step_name == "input_normalizer" else "2/2"
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
        logger.info("  sources:    %d", len(state.sources_used))
        logger.info("  errors:     %d %s", len(state.errors), state.errors if state.errors else "")
        logger.info("  timings:    %s", state.timings)
        logger.info("=" * 60)

        return state
