"""Async Tavily Extract connector (MVP stub with network support)."""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.connectors._resilience import CircuitBreaker, build_cache_key, cache_get, cache_set


TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"
TAVILY_EXTRACT_CACHE_TTL_SECONDS = int(os.getenv("TAVILY_EXTRACT_CACHE_TTL_SECONDS", "7200"))
_TAVILY_EXTRACT_BREAKER = CircuitBreaker(name="tavily-extract")


async def tavily_extract(
    *,
    urls: list[str],
    query: str,
    chunks_per_source: int = 3,
    extract_depth: str = "advanced",
    output_format: str = "text",
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Extract content from selected URLs using Tavily.

    Raises on configuration or network errors.
    """
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not urls:
        return {"results": []}
    if not api_key:
        raise RuntimeError("Tavily extract is not configured with an API key")

    payload: dict[str, Any] = {
        "api_key": api_key,
        "urls": urls,
        "query": query,
        "chunks_per_source": chunks_per_source,
        "extract_depth": extract_depth,
        "format": output_format,
    }

    cache_payload = {
        "urls": sorted(urls),
        "query": query,
        "chunks_per_source": chunks_per_source,
        "extract_depth": extract_depth,
        "format": output_format,
    }
    cache_key = build_cache_key("tavily-extract", cache_payload)
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(TAVILY_EXTRACT_URL, json=payload)
        response.raise_for_status()
        data = response.json()

    _TAVILY_EXTRACT_BREAKER.record_success()

    data.setdefault("results", [])
    cache_set(cache_key, data, TAVILY_EXTRACT_CACHE_TTL_SECONDS)
    return data
