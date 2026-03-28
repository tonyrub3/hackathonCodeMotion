"""Site age heuristics – estimate whether a domain appears established or recent."""

from __future__ import annotations

from typing import Any

# Well-known TLDs that are commonly associated with established entities
_ESTABLISHED_TLDS = {"gov", "edu", "mil", "int", "org"}

# Patterns that suggest established sites (heuristic only)
_ESTABLISHED_PATTERNS = [
    "reuters.com", "apnews.com", "bbc.co.uk", "bbc.com",
    "nytimes.com", "washingtonpost.com", "theguardian.com",
    "ansa.it", "corriere.it", "repubblica.it",
]


def check_site_age(domain: str) -> dict[str, Any]:
    """Estimate site age signal using heuristics.

    Returns: {"signal": "established" | "recent" | "unknown"}

    In production, use WHOIS lookups or domain-age databases.
    """
    if not domain:
        return {"signal": "unknown"}

    tld = domain.split(".")[-1]

    # Government / educational domains are generally established
    if tld in _ESTABLISHED_TLDS:
        return {"signal": "established"}

    # Check against known patterns (not a whitelist for truth – just an age signal)
    for pattern in _ESTABLISHED_PATTERNS:
        if domain.endswith(pattern):
            return {"signal": "established"}

    # Heuristic: very short or unusual domains may be newer
    # TODO: integrate with WHOIS API or domain-age service
    return {"signal": "unknown"}
