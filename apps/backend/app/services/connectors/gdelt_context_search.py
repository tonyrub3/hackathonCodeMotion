"""
GDELT Context 2.0 connector.

Used for quote / context retrieval around a claim.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def search_gdelt_context(
    query: str,
    api_url: str = "https://api.gdeltproject.org/api/v2/context/context",
    max_results: int = 5,
) -> list[dict[str, Any]]:
    """Search GDELT Context 2.0.

    Returns a list of evidence-like dicts with contextual passages.
    """
    params = {
        "query": query,
        "mode": "ContextSearch",
        "maxrecords": str(max_results),
        "format": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(api_url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("GDELT Context search error: %s", exc)
        return []

    results: list[dict[str, Any]] = []
    for item in data.get("results", data.get("articles", [])):
        url = item.get("url", "")
        source_id = hashlib.md5(url.encode()).hexdigest()[:12]

        results.append({
            "source_id": f"gdelt_ctx_{source_id}",
            "source_name": item.get("source", ""),
            "source_type": "news",
            "url": url,
            "tier": "B",
            "published_at": item.get("seendate", ""),
            "stance": "neutral",
            "relevance_score": 0.55,
            "trust_score": 0.5,
            "excerpt": item.get("context", item.get("title", "")),
            "matched_claim_ids": [],
        })

    return results
