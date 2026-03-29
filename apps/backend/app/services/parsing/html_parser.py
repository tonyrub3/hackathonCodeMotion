"""HTML fetcher – downloads a URL and returns raw HTML."""

from __future__ import annotations

import httpx

async def fetch_url(url: str, timeout: int | None = 30) -> str:
    """Fetch a URL and return the HTML body as a string.

    Raises on network failures.
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        resp = await client.get(url, headers={"User-Agent": "TruthEngine/0.1"})
        resp.raise_for_status()
        return resp.text
