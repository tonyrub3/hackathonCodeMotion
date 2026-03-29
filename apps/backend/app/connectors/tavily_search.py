"""Async Tavily Search connector (MVP stub with network support)."""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.connectors._resilience import CircuitBreaker, build_cache_key, cache_get, cache_set


TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_CACHE_TTL_SECONDS = int(os.getenv("TAVILY_CACHE_TTL_SECONDS", "7200"))
_TAVILY_BREAKER = CircuitBreaker(name="tavily-search")


async def tavily_search(
    *,
    query: str,
    search_depth: str = "advanced",
    max_results: int = 6,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    topic: str = "general",
    time_range: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    include_answer: bool | str = False,
    include_raw_content: bool | str = False,
    auto_parameters: bool = False,
    exact_match: bool = False,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    """Search Tavily and return raw results payload.

    Returns an empty successful payload when the API key is missing.
    """
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return {"results": []}

    if _TAVILY_BREAKER.is_open():
        return {"results": [], "degraded": True, "reason": "tavily_circuit_open"}

    payload: dict[str, Any] = {
        "api_key": api_key,
        "query": query,
        "search_depth": search_depth,
        "max_results": max_results,
        "topic": topic,
        "include_answer": include_answer,
        "include_raw_content": include_raw_content,
        "auto_parameters": auto_parameters,
        "include_domains": include_domains or [],
        "exclude_domains": exclude_domains or [],
        "time_range": time_range,
        "start_date": start_date,
        "end_date": end_date,
        "exact_match": exact_match,
    }

    cache_payload = {
        "query": query,
        "search_depth": search_depth,
        "max_results": max_results,
        "include_domains": include_domains or [],
        "exclude_domains": exclude_domains or [],
        "topic": topic,
        "time_range": time_range,
        "start_date": start_date,
        "end_date": end_date,
        "include_answer": include_answer,
        "include_raw_content": include_raw_content,
        "auto_parameters": auto_parameters,
        "exact_match": exact_match,
    }
    cache_key = build_cache_key("tavily-search", cache_payload)
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(TAVILY_SEARCH_URL, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception:
        _TAVILY_BREAKER.record_failure()
        return {"results": [], "degraded": True, "reason": "tavily_search_failed"}

    _TAVILY_BREAKER.record_success()

    data.setdefault("results", [])
    cache_set(cache_key, data, TAVILY_CACHE_TTL_SECONDS)
    return data
