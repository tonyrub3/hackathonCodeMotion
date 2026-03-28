"""Source models – metadata and reliability dimensions for each source."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


SourceTier = Literal["A", "B", "C"]
SourceType = Literal["official", "news", "document", "social_official", "factcheck"]


class SourceReliabilityDimensions(BaseModel):
    """Multidimensional reliability breakdown."""

    authority: float = Field(default=0.5, ge=0.0, le=1.0)
    expertise: float = Field(default=0.5, ge=0.0, le=1.0)
    transparency: float = Field(default=0.5, ge=0.0, le=1.0)
    independence: float = Field(default=0.5, ge=0.0, le=1.0)
    recency: float = Field(default=0.5, ge=0.0, le=1.0)


class SourceInfo(BaseModel):
    """A single source used during verification."""

    source_id: str
    source_name: str = ""
    source_type: SourceType = "news"
    url: str = ""
    tier: SourceTier = "C"
    source_reliability_score: float = Field(default=0.5, ge=0.0, le=1.0)
    dimensions: SourceReliabilityDimensions = Field(
        default_factory=SourceReliabilityDimensions,
    )
    published_at: str = ""
