"""Tests for site forensics utilities."""

from app.services.site_forensics.domain_checks import check_domain_metadata
from app.services.site_forensics.brand_mimicry_checks import check_brand_mimicry
from app.services.site_forensics.citation_checks import check_citations
from app.services.scoring.site_trust_score import compute_site_trust_score


def test_domain_metadata():
    result = check_domain_metadata("https://www.example.gov/article")
    assert result["tld"] == "gov"
    assert result["https"] is True


def test_brand_mimicry_no_risk():
    result = check_brand_mimicry("example.com")
    assert result["risk"] == 0.0


def test_brand_mimicry_detected():
    result = check_brand_mimicry("reuters-news.com")
    assert result["risk"] > 0.0
    assert result["similar_to"] == "reuters"


def test_citations_empty():
    result = check_citations([])
    assert result["total"] == 0


def test_citations_with_primary():
    result = check_citations([
        "https://www.gov.it/statistics",
        "https://blog.example.com/post",
    ])
    assert result["primary"] >= 1
    assert result["total"] == 2


def test_site_trust_score_range():
    forensics = {
        "https": True,
        "site_age_signal": "established",
        "brand_mimicry_risk": 0.0,
        "author_present": True,
        "author_page_found": False,
        "primary_source_citations": 3,
        "circular_sourcing_risk": 0.0,
        "has_about_page": True,
        "has_contact_page": True,
        "has_editorial_policy": True,
        "ownership_transparent": True,
        "headline_body_mismatch": 0.1,
    }
    score = compute_site_trust_score(forensics)
    assert 0 <= score <= 1
    assert score > 0.7
