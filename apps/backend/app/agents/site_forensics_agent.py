"""
Agent 5 – Site Forensics (URL input only).

Responsibilities:
  - Inspect domain, TLD, HTTPS
  - Check site age signals
  - Detect brand mimicry
  - Check author metadata
  - Inspect cited sources in the article
  - Check transparency signals
  - Detect headline/body mismatch
  - Output a site forensics report

Tools used:
  - domain_metadata_checker
  - site_age_checker
  - brand_mimicry_checker
  - author_presence_checker
  - citation_checker
  - transparency_checker
  - headline_body_mismatch_checker
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from app.config import Settings
from app.core.state import PipelineState
from app.services.site_forensics.domain_checks import check_domain_metadata
from app.services.site_forensics.site_age_checks import check_site_age
from app.services.site_forensics.brand_mimicry_checks import check_brand_mimicry
from app.services.site_forensics.author_checks import check_author_presence
from app.services.site_forensics.citation_checks import check_citations
from app.services.site_forensics.transparency_checks import check_transparency
from app.services.scoring.site_trust_score import compute_site_trust_score

logger = logging.getLogger(__name__)


class SiteForensicsAgent:
    """Perform forensic analysis of the source website (URL input only)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, state: PipelineState) -> PipelineState:
        """
        Input contract:  state.source_url, state.normalized_text,
                         state.article_title, state.article_metadata, state.cited_links
        Output contract: state.site_forensics (dict)
        """
        if state.input_type != "url" or not state.source_url:
            return state

        url = state.source_url
        parsed = urlparse(url)
        domain = parsed.netloc
        tld = domain.split(".")[-1] if "." in domain else ""

        # Run forensic checks
        domain_meta = check_domain_metadata(url)
        age_signal = check_site_age(domain)
        mimicry = check_brand_mimicry(domain)
        author = check_author_presence(
            state.article_author,
            state.article_metadata,
        )
        citations = check_citations(state.cited_links)
        transparency = check_transparency(state.article_metadata)

        # Headline/body mismatch (simple heuristic)
        headline_mismatch = self._check_headline_body_mismatch(
            state.article_title, state.normalized_text
        )

        report: dict[str, Any] = {
            "domain": domain,
            "tld": tld,
            "https": parsed.scheme == "https",
            "site_age_signal": age_signal.get("signal", "unknown"),
            "brand_mimicry_risk": mimicry.get("risk", 0.0),
            "author_present": author.get("present", False),
            "author_name": author.get("name", ""),
            "author_page_found": author.get("page_found", False),
            "citation_count": citations.get("total", 0),
            "primary_source_citations": citations.get("primary", 0),
            "secondary_source_citations": citations.get("secondary", 0),
            "circular_sourcing_risk": citations.get("circular_risk", 0.0),
            "has_about_page": transparency.get("has_about", False),
            "has_contact_page": transparency.get("has_contact", False),
            "has_editorial_policy": transparency.get("has_editorial", False),
            "ownership_transparent": transparency.get("ownership_transparent", False),
            "headline_body_mismatch": headline_mismatch,
        }

        # Compute composite site trust score
        report["site_trust_score"] = compute_site_trust_score(report)

        state.site_forensics = report
        return state

    def _check_headline_body_mismatch(self, title: str, body: str) -> float:
        """Simple heuristic: check if key title words appear in body."""
        if not title or not body:
            return 0.0
        title_words = set(title.lower().split())
        # Remove very common words
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "and", "or"}
        title_words -= stopwords
        if not title_words:
            return 0.0
        body_lower = body.lower()
        matches = sum(1 for w in title_words if w in body_lower)
        coverage = matches / len(title_words)
        # High coverage = low mismatch
        return round(max(0.0, 1.0 - coverage), 2)
