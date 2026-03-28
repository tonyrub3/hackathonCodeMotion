"""Citation checks – inspect outgoing references in the article."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

_PRIMARY_INDICATORS = [".gov", ".europa.eu", ".mil", ".int", "/statistics", "/data", "/official"]


def check_citations(cited_links: list[str]) -> dict[str, Any]:
    """Analyze cited links: count primary vs secondary, detect circular sourcing."""
    if not cited_links:
        return {
            "total": 0,
            "primary": 0,
            "secondary": 0,
            "circular_risk": 0.0,
        }

    primary = 0
    secondary = 0
    domains_seen: list[str] = []

    for link in cited_links:
        parsed = urlparse(link)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()
        full = domain + path

        is_primary = any(ind in full for ind in _PRIMARY_INDICATORS)
        if is_primary:
            primary += 1
        else:
            secondary += 1

        domains_seen.append(domain)

    # Circular sourcing risk: many links to the same domain
    unique_domains = set(domains_seen)
    circular_risk = 0.0
    if len(domains_seen) > 2 and len(unique_domains) == 1:
        circular_risk = 0.8  # All citations point to same domain
    elif len(domains_seen) > 3 and len(unique_domains) <= 2:
        circular_risk = 0.5

    return {
        "total": len(cited_links),
        "primary": primary,
        "secondary": secondary,
        "circular_risk": round(circular_risk, 2),
    }
