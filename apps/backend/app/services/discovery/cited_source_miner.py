"""
Cited source miner – extracts and classifies sources cited by the input article.

Only used when the input is a URL.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Patterns that suggest primary vs secondary sources
_PRIMARY_PATTERNS = [
    ".gov", ".europa.eu", ".mil", ".int",
    "/investors", "/investor-relations", "/press",
    "/official", "/releases", "/statistics",
]


async def mine_cited_sources(
    cited_links: list[str],
    claim: dict[str, Any],
) -> list[dict[str, Any]]:
    """Classify cited links as possible primary/secondary evidence candidates.

    Returns evidence-like dicts with preliminary tier assignment.
    """
    results: list[dict[str, Any]] = []

    for link in cited_links[:20]:  # Cap processing
        parsed = urlparse(link)
        domain = parsed.netloc
        path = parsed.path.lower()
        full = domain + path

        is_primary = any(pat in full for pat in _PRIMARY_PATTERNS)
        tier = "A" if is_primary else "B"
        source_type = "official" if is_primary else "document"

        source_id = hashlib.md5(link.encode()).hexdigest()[:12]
        results.append({
            "source_id": f"cited_{source_id}",
            "source_name": domain,
            "source_type": source_type,
            "url": link,
            "tier": tier,
            "published_at": "",
            "stance": "neutral",
            "relevance_score": 0.6 if is_primary else 0.4,
            "trust_score": 0.7 if is_primary else 0.4,
            "excerpt": f"Cited source from input article: {domain}",
            "matched_claim_ids": [],
        })

    return results
