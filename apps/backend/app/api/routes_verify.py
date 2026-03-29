"""
/verify endpoint – accepts text or URL, returns full verification response.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.models.request_models import VerifyRequest
from app.models.response_models import VerifyResponse, build_response_from_state
from app.core.orchestrator import Orchestrator

router = APIRouter(tags=["verify"])


@router.post("/verify", response_model=VerifyResponse)
async def verify(body: VerifyRequest, request: Request) -> VerifyResponse:
    """Run the full verification pipeline."""
    settings = request.app.state.settings
    orchestrator = Orchestrator(settings)

    state = await orchestrator.verify(
        content=body.content,
        input_type=body.input_type,
        language=body.language,
        country=body.country,
        topic=body.topic,
    )

    return build_response_from_state(state)
