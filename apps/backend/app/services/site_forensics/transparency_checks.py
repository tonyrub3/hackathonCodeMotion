"""Transparency checks – editorial policy, about page, contact, ownership."""

from __future__ import annotations

from typing import Any


def check_transparency(article_metadata: dict[str, Any]) -> dict[str, Any]:
    """Check transparency signals from article metadata.

    In production, this would actually fetch /about, /contact, etc.
    For the MVP, we check what metadata we have.
    """
    page_hints = article_metadata.get("page_hints", {}) or {}
    outgoing_domains = article_metadata.get("outgoing_domains", []) or []
    internal_links = article_metadata.get("internal_links", []) or []

    has_about = bool(page_hints.get("about"))
    has_contact = bool(page_hints.get("contact"))
    has_editorial = bool(page_hints.get("editorial"))
    has_author_pages = bool(page_hints.get("author"))
    has_ownership_page = bool(page_hints.get("ownership"))
    has_byline = bool((article_metadata.get("byline") or "").strip())
    has_site_name = bool((article_metadata.get("site_name") or "").strip())
    has_outgoing = len(outgoing_domains) >= 3

    transparency_score = 0.0
    transparency_score += 0.25 if has_about else 0.0
    transparency_score += 0.20 if has_contact else 0.0
    transparency_score += 0.25 if has_editorial else 0.0
    transparency_score += 0.10 if has_author_pages else 0.0
    transparency_score += 0.10 if has_ownership_page else 0.0
    transparency_score += 0.05 if has_byline else 0.0
    transparency_score += 0.05 if has_site_name else 0.0
    transparency_score += 0.05 if has_outgoing else 0.0
    if internal_links:
        transparency_score += 0.05

    return {
        "has_about": has_about,
        "has_contact": has_contact,
        "has_editorial": has_editorial,
        "has_author_pages": has_author_pages,
        "has_ownership_page": has_ownership_page,
        "ownership_transparent": transparency_score >= 0.45,
        "score": round(min(1.0, transparency_score), 2),
        "signals": {
            "byline": has_byline,
            "site_name": has_site_name,
            "internal_links": len(internal_links),
            "outgoing_domains": len(outgoing_domains),
        },
    }
