"""
Live pipeline – thin wrapper that delegates to the orchestrator.
Exists so that route handlers stay slim and testable.
"""

from __future__ import annotations

from app.config import Settings
from app.core.orchestrator import Orchestrator
from app.core.state import PipelineState


async def run_live_pipeline(
    content: str,
    input_type: str,
    settings: Settings,
    language: str = "en",
    country: str = "",
    topic: str = "",
) -> PipelineState:
    """Convenience entry point for live verification."""
    orchestrator = Orchestrator(settings)
    return await orchestrator.verify(
        content=content,
        input_type=input_type,
        language=language,
        country=country,
        topic=topic,
        mode="live",
    )
