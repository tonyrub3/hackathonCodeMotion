"""
GDELT DOC 2.0 connector.

Used as an early-warning / global retrieval layer for live news coverage.
Does NOT decide the final verdict.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def search_gdelt_docs(
    queries: list[str],
    api_url: str = "https://api.gdeltproject.org/api/v2/doc/doc",
    max_results: int = 5,
) -> list[dict[str, Any]]:
    """Search GDELT DOC 2.0 for matching articles.

    Returns a list of evidence-like dicts.
    """
    results: list[dict[str, Any]] = []

    for query in queries[:3]:  # Limit queries to avoid rate-limiting
        params = {
            "query": query,
            "mode": "ArtList",
            "maxrecords": str(max_results),
            "format": "json",
            "sort": "DateDesc",
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(api_url, params=params)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                if "json" not in content_type.lower():
                    logger.warning("GDELT DOC non-JSON response for query '%s'", query)
                    continue
                data = resp.json()
        except Exception as exc:
            logger.warning("GDELT DOC search error for query '%s': %s", query, exc)
            continue

        for article in data.get("articles", []):
            url = article.get("url", "")
            source_id = hashlib.md5(url.encode()).hexdigest()[:12]

            results.append({
                "source_id": f"gdelt_{source_id}",
                "source_name": article.get("source", ""),
                "source_type": "news",
                "url": url,
                "tier": "B",
                "published_at": article.get("seendate", ""),
                "stance": "neutral",  # Stance classified later by Evidence Analysis
                "relevance_score": 0.6,
                "trust_score": 0.5,
                "excerpt": article.get("title", ""),
                "matched_claim_ids": [],
            })

    return results
