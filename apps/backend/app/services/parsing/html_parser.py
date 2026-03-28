"""HTML fetcher – downloads a URL and returns raw HTML."""

from __future__ import annotations

import logging
import httpx

logger = logging.getLogger(__name__)


async def fetch_url(url: str, timeout: int = 30) -> str:
    """Fetch a URL and return the HTML body as a string.

    Returns empty string on failure.
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            resp = await client.get(url, headers={"User-Agent": "TruthEngine/0.1"})
            resp.raise_for_status()
            return resp.text
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return ""
