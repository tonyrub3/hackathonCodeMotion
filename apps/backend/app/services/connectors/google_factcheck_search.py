"""
Google Fact Check Tools API connector.

Used as a claim-matching layer – returns previously verified fact-checks.
Does NOT decide the final verdict.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GOOGLE_FC_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


async def search_google_factcheck(
    query: str,
    api_key: str = "",
    language: str = "en",
    max_results: int = 5,
) -> list[dict[str, Any]]:
    """Search Google Fact Check Tools API for matching fact-checks.

    Returns a list of evidence-like dicts.
    """
    if not api_key:
        logger.debug("Google Fact Check API key not set – skipping")
        return []

    params = {
        "query": query,
        "key": api_key,
        "languageCode": language,
        "pageSize": max_results,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(GOOGLE_FC_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Google Fact Check API error: %s", exc)
        return []

    results: list[dict[str, Any]] = []
    for item in data.get("claims", []):
        for review in item.get("claimReview", []):
            source_id = hashlib.md5(
                review.get("url", "").encode()
            ).hexdigest()[:12]

            # Map textual rating to stance
            rating = review.get("textualRating", "").lower()
            stance = _rating_to_stance(rating)

            results.append({
                "source_id": f"gfc_{source_id}",
                "source_name": review.get("publisher", {}).get("name", "Fact Check"),
                "source_type": "factcheck",
                "url": review.get("url", ""),
                "tier": "B",
                "published_at": review.get("reviewDate", ""),
                "stance": stance,
                "relevance_score": 0.75,
                "trust_score": 0.70,
                "excerpt": (
                    f"Claim: {item.get('text', '')}. "
                    f"Rating: {review.get('textualRating', 'unknown')}."
                ),
                "matched_claim_ids": [],
            })

    return results


def _rating_to_stance(rating: str) -> str:
    """Map a fact-check textual rating to a stance label."""
    positive = ["true", "correct", "accurate", "verified", "mostly true"]
    negative = ["false", "incorrect", "pants on fire", "mostly false", "misleading"]

    for kw in positive:
        if kw in rating:
            return "supporting"
    for kw in negative:
        if kw in rating:
            return "contradicting"
    return "neutral"
