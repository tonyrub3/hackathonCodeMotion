"""Reranking utilities – rerank passages by relevance to a query."""

from __future__ import annotations

from typing import Any

from app.services.llm.regolo_client import RegoloClient
from app.config import Settings


async def rerank_passages(
    query: str,
    passages: list[str],
    settings: Settings,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Rerank passages by relevance to query.

    TODO: Use a dedicated reranking endpoint when available.
    For MVP, uses a simple LLM scoring approach.
    """
    if not passages:
        return []

    # For MVP, return passages in original order with default scores
    # TODO: implement proper reranking via Regolo rerank API
    return [
        {"index": i, "passage": p, "score": 1.0 - (i * 0.1)}
        for i, p in enumerate(passages[:top_k])
    ]
