"""
FEVER benchmark routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["benchmark"])


@router.post("/fever/run")
async def fever_run(request: Request) -> dict:
    """Run FEVER benchmark evaluation (stub)."""
    # TODO: integrate fever_loader + pipeline_benchmark
    return {"status": "not_implemented", "message": "FEVER benchmark run not yet wired"}


@router.post("/fever/evaluate")
async def fever_evaluate(request: Request) -> dict:
    """Evaluate FEVER benchmark results (stub)."""
    return {"status": "not_implemented", "message": "FEVER evaluation not yet wired"}
