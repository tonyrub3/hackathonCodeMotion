"""
Benchmark pipeline – runs FEVER claims through the engine and collects results.
"""

from __future__ import annotations

from app.config import Settings
from app.core.orchestrator import Orchestrator
from app.core.state import PipelineState


async def run_benchmark_claim(
    claim_text: str,
    settings: Settings,
) -> PipelineState:
    """Run a single FEVER claim through the pipeline in benchmark mode."""
    orchestrator = Orchestrator(settings)
    return await orchestrator.verify(
        content=claim_text,
        input_type="text",
        mode="benchmark",
    )
