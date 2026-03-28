"""Brand mimicry detection – detects suspicious imitation of known publishers."""

from __future__ import annotations

from typing import Any

# Patterns of known brand domains to check for mimicry
_KNOWN_BRANDS = [
    "reuters", "bbc", "nytimes", "washingtonpost", "guardian",
    "apnews", "ansa", "corriere", "repubblica", "cnn", "foxnews",
]


def check_brand_mimicry(domain: str) -> dict[str, Any]:
    """Detect if a domain is suspiciously similar to a known brand.

    Returns: {"risk": 0.0 - 1.0, "similar_to": "brand_name" or ""}
    """
    if not domain:
        return {"risk": 0.0, "similar_to": ""}

    domain_lower = domain.lower()

    for brand in _KNOWN_BRANDS:
        # Exact match = not mimicry
        if brand in domain_lower and f"{brand}.com" == domain_lower:
            return {"risk": 0.0, "similar_to": ""}

        # Contains brand name but is a different domain = suspicious
        if brand in domain_lower and f"{brand}.com" != domain_lower:
            # Check if it's a legitimate subdomain or country variant
            if domain_lower.startswith(f"{brand}.") or f".{brand}." in domain_lower:
                return {"risk": 0.3, "similar_to": brand}
            # Likely mimicry
            return {"risk": 0.7, "similar_to": brand}

    return {"risk": 0.0, "similar_to": ""}
