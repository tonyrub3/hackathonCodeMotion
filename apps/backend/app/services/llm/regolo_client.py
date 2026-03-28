"""
Regolo LLM client – handles completions, JSON extraction, embeddings, and reranking.

Used for:
  - Semantic claim decomposition
  - Stance classification
  - Semantic normalization
  - Embeddings for deduplication
  - Passage reranking
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class RegoloClient:
    """Client for Regolo (OpenAI-compatible) API."""

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.regolo_api_key
        self.base_url = settings.regolo_base_url.rstrip("/")
        self.model = settings.regolo_model
        self.embedding_api_key = settings.regolo_embedding_api_key or settings.regolo_api_key
        self.embedding_model = settings.regolo_embedding_model

    async def complete_text(
        self,
        prompt: str,
        max_tokens: int = 512,
        timeout_seconds: int = 20,
    ) -> str:
        """Get a text completion from the LLM."""
        if not self.api_key:
            logger.warning("LLM: API key not set – skipping")
            return ""

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.1,
        }

        logger.info("    LLM CALL model=%s tokens=%d prompt=%.80s...", self.model, max_tokens, prompt.replace("\n", " "))
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                message = data["choices"][0].get("message", {})
                # Some models may populate reasoning_content while keeping content null.
                result = message.get("content") or message.get("reasoning_content") or ""
                logger.info("    LLM RESPONSE (%d chars): %.120s%s",
                             len(result), result.replace("\n", " "),
                             "..." if len(result) > 120 else "")
                return result
        except Exception as exc:
            logger.error("    LLM FAILED: %s", exc)
            return ""

    async def complete_json(self, prompt: str, max_tokens: int = 1024) -> Any:
        """Get a JSON-parsed completion from the LLM."""
        raw = await self.complete_text(prompt, max_tokens)
        if not raw:
            return []

        # Try to extract JSON from the response
        # Handle markdown code blocks
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if json_match:
            raw = json_match.group(1)

        # Try direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Try to find array/object
            for start, end in [("[", "]"), ("{", "}")]:
                idx_start = raw.find(start)
                idx_end = raw.rfind(end)
                if idx_start != -1 and idx_end > idx_start:
                    try:
                        return json.loads(raw[idx_start : idx_end + 1])
                    except json.JSONDecodeError:
                        continue
            logger.warning("Could not parse JSON from LLM response")
            return []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for a list of texts."""
        if not self.embedding_api_key:
            return []

        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.embedding_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.embedding_model,
            "input": texts,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return [item["embedding"] for item in data["data"]]
        except Exception as exc:
            logger.warning("Regolo embedding failed: %s", exc)
            return []
