"""
Debug routes – expose pipeline internals during development.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["debug"])


@router.get("/config")
async def debug_config() -> dict:
    """Return non-secret config values for debugging."""
    return {"status": "ok", "note": "Debug endpoint – disable in production"}
