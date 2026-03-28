"""
Official source discovery – heuristic-based discovery of primary/official sources.

Uses patterns from discovery_policies to identify likely official sources
from claim entities, NOT a static whitelist of approved domains.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Load official patterns at import time
_PATTERNS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "..", "data", "discovery_policies", "official_patterns.json"
)
_OFFICIAL_PATTERNS: dict[str, Any] = {}
try:
    with open(_PATTERNS_PATH) as f:
        _OFFICIAL_PATTERNS = json.load(f)
except FileNotFoundError:
    logger.info("official_patterns.json not found – official source discovery will use built-in defaults")


# Built-in fallback patterns
_DEFAULT_TLD_PATTERNS = [".gov", ".gov.*", ".europa.eu", ".mil", ".edu", ".int"]
_DEFAULT_PATH_PATTERNS = [
    "/investors", "/investor-relations", "/press", "/media",
    "/newsroom", "/press-releases", "/official-statements",
]


async def discover_official_sources(
    claim: dict[str, Any],
    topic: str = "",
) -> list[dict[str, Any]]:
    """Discover likely official sources from claim entities and type.

    This is a heuristic-based stub. In production, it would query search
    engines or domain indexes to find real URLs matching the patterns.

    Returns evidence-like dicts.
    """
    results: list[dict[str, Any]] = []

    claim_type = claim.get("type", "")
    subject = claim.get("subject", "")
    claim_text = claim.get("claim", "")

    # Determine which patterns to try based on claim type
    patterns = _OFFICIAL_PATTERNS.get("tld_patterns", _DEFAULT_TLD_PATTERNS)
    path_patterns = _OFFICIAL_PATTERNS.get("path_patterns", _DEFAULT_PATH_PATTERNS)

    # For statistical claims, suggest statistics office sources
    if claim_type == "statistical":
        results.append(_make_placeholder_source(
            name="National Statistics Office",
            source_type="official",
            tier="A",
            relevance=0.8,
            note=f"Expected official statistics source for: {subject or claim_text[:60]}",
        ))

    # For regulatory claims, suggest legal/regulatory sources
    if claim_type == "regulatory":
        results.append(_make_placeholder_source(
            name="Official Legal/Regulatory Database",
            source_type="official",
            tier="A",
            relevance=0.85,
            note=f"Expected regulatory source for: {subject or claim_text[:60]}",
        ))

    # For institutional claims, suggest government/institutional pages
    if claim_type == "institutional":
        results.append(_make_placeholder_source(
            name="Official Government/Institution Page",
            source_type="official",
            tier="A",
            relevance=0.8,
            note=f"Expected official page for: {subject or claim_text[:60]}",
        ))

    # TODO: In production, use a search engine API or domain index
    # to actually resolve these patterns to real URLs.
    # For now, these serve as discovery hints that downstream processing
    # can attempt to resolve.

    return results


def _make_placeholder_source(
    name: str,
    source_type: str = "official",
    tier: str = "A",
    relevance: float = 0.7,
    note: str = "",
) -> dict[str, Any]:
    """Create a placeholder evidence entry for a discovered source type."""
    source_id = hashlib.md5(name.encode()).hexdigest()[:12]
    return {
        "source_id": f"off_{source_id}",
        "source_name": name,
        "source_type": source_type,
        "url": "",
        "tier": tier,
        "published_at": "",
        "stance": "neutral",
        "relevance_score": relevance,
        "trust_score": 0.7,
        "excerpt": note,
        "matched_claim_ids": [],
    }
