"""Site forensics models – URL-input-only analysis of the source site."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SiteForensicsReport(BaseModel):
    """Complete site-trust analysis for a URL input."""

    domain: str = ""
    tld: str = ""
    https: bool = True
    site_age_signal: str = ""  # "established", "recent", "unknown"
    brand_mimicry_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    author_present: bool = False
    author_name: str = ""
    author_page_found: bool = False
    citation_count: int = 0
    primary_source_citations: int = 0
    secondary_source_citations: int = 0
    circular_sourcing_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    has_about_page: bool = False
    has_contact_page: bool = False
    has_editorial_policy: bool = False
    ownership_transparent: bool = False
    headline_body_mismatch: float = Field(default=0.0, ge=0.0, le=1.0)
    site_trust_score: float = Field(default=0.5, ge=0.0, le=1.0)

    # Linguistic risk (included here for URL inputs)
    linguistic_risk: LinguisticRisk = Field(default_factory=lambda: LinguisticRisk())


class LinguisticRisk(BaseModel):
    """Linguistic risk signals detected in the text."""

    sensationalism_score: float = Field(default=0.0, ge=0.0, le=1.0)
    emotional_tone_score: float = Field(default=0.0, ge=0.0, le=1.0)
    attribution_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty_score: float = Field(default=0.0, ge=0.0, le=1.0)
    manipulation_markers: list[str] = Field(default_factory=list)
