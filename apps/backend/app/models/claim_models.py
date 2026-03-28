"""Claim models – output of the Claim Decomposition Agent."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


ClaimType = Literal[
    "statistical",
    "event",
    "quote",
    "institutional",
    "regulatory",
    "causal",
    "historical",
    "technical",
]


class AtomicClaim(BaseModel):
    """A single, independently verifiable claim."""

    id: str = Field(..., description="Unique claim identifier, e.g. 'c1'.")
    claim: str = Field(..., description="Human-readable claim text.")
    type: ClaimType = Field(default="event", description="Claim category.")
    subject: str = ""
    predicate: str = ""
    object: str = ""
    time_scope: str = ""
    geo_scope: str = ""
    checkability_score: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="How verifiable this claim is (0=impossible, 1=trivially checkable).",
    )
    dependency_type: str = Field(
        default="standalone",
        description="'standalone' or reference to parent claim id.",
    )
    requires_evidence_type: list[str] = Field(default_factory=list)
    original_sentence_index: int = 0
