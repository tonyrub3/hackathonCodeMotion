"""Tests for source reliability scoring."""

from app.services.scoring.source_reliability import compute_source_reliability


def test_official_source_high_reliability():
    """Official tier-A sources should score high."""
    result = compute_source_reliability({
        "source_type": "official",
        "tier": "A",
        "url": "https://gov.example.com/stats",
        "published_at": "2026-01-01",
    })
    assert result["total"] > 0.7
    assert result["dimensions"]["authority"] > 0.8


def test_weak_source_low_reliability():
    """Tier-C unknown sources should score low."""
    result = compute_source_reliability({
        "source_type": "news",
        "tier": "C",
        "url": "",
        "published_at": "",
    })
    assert result["total"] < 0.5


def test_dimensions_sum_to_weights():
    """Dimensions should be correctly weighted."""
    result = compute_source_reliability({
        "source_type": "factcheck",
        "tier": "B",
        "url": "https://factcheck.org/check",
        "published_at": "2026-03-01",
    })
    dims = result["dimensions"]
    manual = (
        0.30 * dims["authority"]
        + 0.20 * dims["expertise"]
        + 0.20 * dims["transparency"]
        + 0.15 * dims["independence"]
        + 0.15 * dims["recency"]
    )
    assert abs(manual - result["total"]) < 0.01
