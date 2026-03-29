"""Async Regolo.ai connector for LLM generation and embeddings."""

from __future__ import annotations

import os
from typing import Any

import httpx


class RegoloClient:
    """Single-provider client for LLM and embeddings through Regolo.ai."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        llm_model: str | None = None,
        embedding_model: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key or os.getenv("REGOLO_API_KEY", "")
        self.base_url = (base_url or os.getenv("REGOLO_BASE_URL", "https://api.regolo.ai/v1")).rstrip("/")
        self.llm_model = llm_model or os.getenv("REGOLO_LLM_MODEL") or os.getenv("REGOLO_MODEL", "")
        self.embedding_model = embedding_model or os.getenv("REGOLO_EMBEDDING_MODEL", "gte-Qwen2")
        self.timeout_seconds = timeout_seconds

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.1,
    ) -> str:
        """Generate text using a chat-completions compatible endpoint."""
        if not self.api_key or not self.llm_model:
            return ""

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.llm_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a batch of texts."""
        if not self.api_key or not self.embedding_model or not texts:
            return []

        payload = {
            "model": self.embedding_model,
            "input": texts,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        return [item.get("embedding", []) for item in data.get("data", [])]
