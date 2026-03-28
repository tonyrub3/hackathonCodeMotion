"""Evidence models – individual evidence items linked to claims and sources."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


Stance = Literal["supporting", "contradicting", "neutral"]


class EvidenceItem(BaseModel):
    """A single piece of evidence retrieved for one or more claims."""

    source_id: str
    source_name: str = ""
    source_type: str = "news"
    url: str = ""
    tier: str = "C"
    published_at: str = ""
    stance: Stance = "neutral"
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    trust_score: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    excerpt: str = ""
    matched_claim_ids: list[str] = Field(default_factory=list)


class Contradiction(BaseModel):
    """A detected contradiction between evidence items."""

    claim_id: str
    type: str = ""  # number, date, entity, quote
    description: str = ""
    evidence_a_id: str = ""
    evidence_b_id: str = ""
    severity: float = Field(default=0.5, ge=0.0, le=1.0)
