"""Brand mimicry detection – detects suspicious imitation of known publishers."""

from __future__ import annotations

import difflib
import re
import unicodedata
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

    domain_lower = _normalize_domain(domain)
    domain_tokens = [token for token in re.split(r"[.\-]", domain_lower) if token]

    for brand in _KNOWN_BRANDS:
        brand_norm = _normalize_token(brand)
        # Exact match = not mimicry
        if domain_lower == f"{brand_norm}.com" or domain_lower == brand_norm:
            return {"risk": 0.0, "similar_to": ""}

        if brand_norm in domain_tokens:
            if any(token in {"news", "press", "official", "support", "update", "watch"} for token in domain_tokens):
                return {"risk": 0.7, "similar_to": brand}
            if len(domain_tokens) <= 3:
                return {"risk": 0.25, "similar_to": brand}
            return {"risk": 0.5, "similar_to": brand}

        similarity = difflib.SequenceMatcher(None, domain_tokens[0] if domain_tokens else domain_lower, brand_norm).ratio()
        compact_similarity = difflib.SequenceMatcher(
            None,
            domain_lower.replace(".", "").replace("-", ""),
            brand_norm,
        ).ratio()
        if max(similarity, compact_similarity) >= 0.84:
            return {"risk": 0.75, "similar_to": brand}

    return {"risk": 0.0, "similar_to": ""}


def _normalize_token(text: str) -> str:
    """Lowercase and strip accents from a token."""
    normalized = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.casefold()


def _normalize_domain(domain: str) -> str:
    """Normalize the full domain string for comparison."""
    normalized = _normalize_token(domain)
    if normalized.startswith("www."):
        return normalized[4:]
    return normalized
