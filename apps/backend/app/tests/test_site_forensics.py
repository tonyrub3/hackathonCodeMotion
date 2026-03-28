"""Tests for site forensics utilities."""

from app.services.parsing.metadata_extractor import extract_metadata
from app.services.site_forensics.author_checks import check_author_presence
from app.services.site_forensics.brand_mimicry_checks import check_brand_mimicry
from app.services.site_forensics.citation_checks import check_citations
from app.services.site_forensics.domain_checks import check_domain_metadata
from app.services.site_forensics.site_age_checks import check_site_age
from app.services.site_forensics.transparency_checks import check_transparency
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


def test_brand_mimicry_detects_typosquatting():
    result = check_brand_mimicry("reuterz.com")
    assert result["risk"] >= 0.7
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


def test_metadata_extractor_collects_transparency_hints():
    html = """
    <html lang="it">
      <head>
        <meta property="og:site_name" content="Example News">
      </head>
      <body>
        <a href="/about-us">Chi siamo</a>
        <a href="/contatti">Contatti</a>
        <a href="/editorial-policy">Editorial policy</a>
        <a href="/author/mario-rossi">Mario Rossi</a>
      </body>
    </html>
    """
    meta = extract_metadata(html, "https://example.com/articolo")
    assert meta["site_name"] == "Example News"
    assert meta["page_hints"]["about"]
    assert meta["page_hints"]["contact"]
    assert meta["page_hints"]["editorial"]
    assert meta["page_hints"]["author"]
    assert meta["internal_links"]


def test_author_and_transparency_checks_use_metadata_hints():
    metadata = {
        "domain": "example.com",
        "canonical_url": "https://example.com/articolo",
        "byline": "Mario Rossi",
        "site_name": "Example News",
        "internal_links": [
            "https://example.com/about-us",
            "https://example.com/author/mario-rossi",
            "https://example.com/contact",
        ],
        "page_hints": {
            "about": ["https://example.com/about-us"],
            "contact": ["https://example.com/contact"],
            "editorial": ["https://example.com/editorial-policy"],
            "author": ["https://example.com/author/mario-rossi"],
            "ownership": ["https://example.com/about-us"],
        },
        "outgoing_domains": ["istat.it", "ecb.europa.eu"],
    }

    author = check_author_presence("Mario Rossi", metadata)
    transparency = check_transparency(metadata)

    assert author["present"] is True
    assert author["page_found"] is True
    assert transparency["has_about"] is True
    assert transparency["has_contact"] is True
    assert transparency["has_editorial"] is True
    assert transparency["ownership_transparent"] is True
    assert transparency["score"] >= 0.45


def test_site_age_detects_recent_pattern():
    result = check_site_age("news2024-press.info")
    assert result["signal"] == "recent"


def test_site_trust_score_range():
    forensics = {
        "https": True,
        "site_age_signal": "established",
        "brand_mimicry_risk": 0.0,
        "author_present": True,
        "author_page_found": False,
        "has_author_pages": True,
        "has_ownership_page": True,
        "primary_source_citations": 3,
        "circular_sourcing_risk": 0.0,
        "has_about_page": True,
        "has_contact_page": True,
        "has_editorial_policy": True,
        "ownership_transparent": True,
        "transparency_score": 0.8,
        "headline_body_mismatch": 0.1,
    }
    score = compute_site_trust_score(forensics)
    assert 0 <= score <= 1
    assert score > 0.7
