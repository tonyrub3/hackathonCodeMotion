"""Transparency checks – editorial policy, about page, contact, ownership."""

from __future__ import annotations

from typing import Any


def check_transparency(article_metadata: dict[str, Any]) -> dict[str, Any]:
    """Check transparency signals from article metadata.

    In production, this would actually fetch /about, /contact, etc.
    For the MVP, we check what metadata we have.
    """
    # TODO: actually fetch and check these pages
    # For now, use metadata hints

    domain = article_metadata.get("domain", "")
    outgoing_domains = article_metadata.get("outgoing_domains", [])

    # Heuristic: sites with many outgoing links tend to be more transparent
    has_outgoing = len(outgoing_domains) > 3

    return {
        "has_about": False,  # TODO: fetch /about
        "has_contact": False,  # TODO: fetch /contact
        "has_editorial": False,  # TODO: fetch /editorial-policy
        "ownership_transparent": has_outgoing,  # Weak signal
    }
