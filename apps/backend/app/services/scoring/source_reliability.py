"""
Source Reliability Score – multidimensional, deterministic scoring.

Formula (from spec §14):
  source_reliability_score =
    0.30 * authority +
    0.20 * expertise +
    0.20 * transparency +
    0.15 * independence +
    0.15 * recency

All components normalized to [0, 1].
"""

from __future__ import annotations

from typing import Any


def compute_source_reliability(evidence: dict[str, Any]) -> dict[str, Any]:
    """Compute the multidimensional source reliability score.

    Uses heuristics based on evidence metadata. In production, each
    dimension would be computed by dedicated sub-tools.

    Returns:
        {"total": float, "dimensions": {authority, expertise, transparency, independence, recency}}
    """
    source_type = evidence.get("source_type", "news")
    tier = evidence.get("tier", "C")
    url = evidence.get("url", "")
    published_at = evidence.get("published_at", "")

    # --- Authority ---
    authority = _compute_authority(source_type, tier)

    # --- Expertise ---
    expertise = _compute_expertise(source_type, tier)

    # --- Transparency ---
    transparency = _compute_transparency(source_type, url)

    # --- Independence ---
    independence = _compute_independence(source_type)

    # --- Recency ---
    recency = _compute_recency(published_at)

    # Weighted total
    total = (
        0.30 * authority
        + 0.20 * expertise
        + 0.20 * transparency
        + 0.15 * independence
        + 0.15 * recency
    )
    total = round(max(0.0, min(1.0, total)), 3)

    return {
        "total": total,
        "dimensions": {
            "authority": round(authority, 3),
            "expertise": round(expertise, 3),
            "transparency": round(transparency, 3),
            "independence": round(independence, 3),
            "recency": round(recency, 3),
        },
    }


def _compute_authority(source_type: str, tier: str) -> float:
    """Authority based on source type and tier."""
    type_scores = {
        "official": 0.95,
        "factcheck": 0.80,
        "news": 0.60,
        "document": 0.55,
        "social_official": 0.50,
    }
    tier_bonus = {"A": 0.05, "B": 0.0, "C": -0.15}
    base = type_scores.get(source_type, 0.4)
    return max(0.0, min(1.0, base + tier_bonus.get(tier, 0.0)))


def _compute_expertise(source_type: str, tier: str) -> float:
    """Expertise heuristic – official and factcheck sources score higher."""
    if source_type == "official":
        return 0.90
    if source_type == "factcheck":
        return 0.75
    if tier == "A":
        return 0.70
    if tier == "B":
        return 0.55
    return 0.35


def _compute_transparency(source_type: str, url: str) -> float:
    """Transparency based on source type and URL signals."""
    if source_type == "official":
        return 0.85
    if source_type == "factcheck":
        return 0.80
    if url and ("https://" in url):
        return 0.55
    return 0.35


def _compute_independence(source_type: str) -> float:
    """Independence heuristic."""
    if source_type == "official":
        return 0.70  # Official sources may be biased toward their own narrative
    if source_type == "factcheck":
        return 0.85
    if source_type == "news":
        return 0.65
    return 0.50


def _compute_recency(published_at: str) -> float:
    """Recency score. With actual dates, compute time delta.

    For MVP, binary: has date = 0.7, no date = 0.4.
    """
    if published_at:
        return 0.70
    return 0.40
