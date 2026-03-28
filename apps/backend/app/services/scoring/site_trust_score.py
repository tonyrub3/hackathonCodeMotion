"""
Site Trust Score – composite score from site forensics signals.

Used only for URL inputs, and only as a secondary signal
(it affects confidence, not the core factual analysis).
"""

from __future__ import annotations

from typing import Any


def compute_site_trust_score(forensics: dict[str, Any]) -> float:
    """Compute a composite site trust score in [0, 1] from forensics data."""
    score = 0.5  # Start neutral

    # HTTPS
    if forensics.get("https"):
        score += 0.05

    # Site age
    age = forensics.get("site_age_signal", "unknown")
    if age == "established":
        score += 0.15
    elif age == "recent":
        score -= 0.15

    # Brand mimicry
    mimicry = forensics.get("brand_mimicry_risk", 0.0)
    score -= mimicry * 0.2

    # Author presence
    if forensics.get("author_present"):
        score += 0.1
    if forensics.get("author_page_found"):
        score += 0.05

    # Citations
    primary = forensics.get("primary_source_citations", 0)
    if primary >= 2:
        score += 0.1
    elif primary == 0:
        score -= 0.05

    circular = forensics.get("circular_sourcing_risk", 0.0)
    score -= circular * 0.1

    # Transparency
    transparency_score = forensics.get("transparency_score")
    if isinstance(transparency_score, (int, float)):
        score += max(0.0, min(1.0, float(transparency_score))) * 0.1
    if forensics.get("has_about_page"):
        score += 0.05
    if forensics.get("has_contact_page"):
        score += 0.03
    if forensics.get("has_editorial_policy"):
        score += 0.07
    if forensics.get("has_author_pages"):
        score += 0.03
    if forensics.get("has_ownership_page"):
        score += 0.03
    if forensics.get("ownership_transparent"):
        score += 0.05

    # Headline/body mismatch
    mismatch = forensics.get("headline_body_mismatch", 0.0)
    score -= mismatch * 0.1

    # URL structure
    path_depth = forensics.get("path_depth", 0)
    if path_depth >= 5:
        score -= 0.04
    elif path_depth <= 1:
        score += 0.02

    if forensics.get("has_subdomain") and not str(forensics.get("domain", "")).endswith((".gov", ".edu", ".int")):
        score -= 0.02

    return round(max(0.0, min(1.0, score)), 3)
