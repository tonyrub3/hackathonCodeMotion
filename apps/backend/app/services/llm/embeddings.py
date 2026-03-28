"""Embedding utilities – thin wrapper around RegoloClient.embed()."""

from __future__ import annotations

from app.services.llm.regolo_client import RegoloClient
from app.config import Settings


async def get_embeddings(texts: list[str], settings: Settings) -> list[list[float]]:
    """Get embeddings for a list of texts."""
    client = RegoloClient(settings)
    return await client.embed(texts)
