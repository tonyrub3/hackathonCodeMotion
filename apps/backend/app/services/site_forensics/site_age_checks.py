"""Site age heuristics – estimate whether a domain appears established or recent."""

from __future__ import annotations

import re
from typing import Any

# Well-known TLDs that are commonly associated with established entities
_ESTABLISHED_TLDS = {"gov", "edu", "mil", "int", "org"}

# Patterns that suggest established sites (heuristic only)
_ESTABLISHED_PATTERNS = [
    "reuters.com", "apnews.com", "bbc.co.uk", "bbc.com",
    "nytimes.com", "washingtonpost.com", "theguardian.com",
    "ansa.it", "corriere.it", "repubblica.it",
]

_SUSPICIOUS_RECENT_TLDS = {
    "xyz",
    "top",
    "click",
    "site",
    "online",
    "today",
    "news",
    "live",
    "press",
    "info",
    "biz",
    "icu",
}


def check_site_age(domain: str) -> dict[str, Any]:
    """Estimate site age signal using heuristics.

    Returns: {"signal": "established" | "recent" | "unknown"}

    In production, use WHOIS lookups or domain-age databases.
    """
    if not domain:
        return {"signal": "unknown", "reason": "missing_domain"}

    tld = domain.split(".")[-1]
    normalized = domain.lower()

    # Government / educational domains are generally established
    if tld in _ESTABLISHED_TLDS:
        return {"signal": "established", "reason": "trusted_tld"}

    # Check against known patterns (not a whitelist for truth – just an age signal)
    for pattern in _ESTABLISHED_PATTERNS:
        if normalized.endswith(pattern):
            return {"signal": "established", "reason": "known_established_domain"}

    if normalized.startswith("xn--") or any(label.startswith("xn--") for label in normalized.split(".")):
        return {"signal": "recent", "reason": "punycode_domain"}

    hyphen_count = normalized.count("-")
    digit_count = sum(1 for ch in normalized if ch.isdigit())
    if hyphen_count >= 3 or digit_count >= 4:
        return {"signal": "recent", "reason": "many_hyphens_or_digits"}

    if tld in _SUSPICIOUS_RECENT_TLDS:
        return {"signal": "recent", "reason": "uncommon_tld"}

    if re.search(r"(news|press|update|live|daily|today)\d{2,}", normalized):
        return {"signal": "recent", "reason": "template_like_domain"}

    # Heuristic: very short or unusual domains may be newer
    # TODO: integrate with WHOIS API or domain-age service
    return {"signal": "unknown", "reason": "no_strong_signal"}
