"""AI-assisted query planning for retrieval-first fact-checking."""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.connectors.regolo_client import RegoloClient
from app.core.state import PipelineState
from app.services.analysis.json_utils import parse_llm_json

logger = logging.getLogger(__name__)


QUERY_GEN_SYSTEM = """\
You are a search-query optimizer for fact-checking.
You will receive a text (short statement OR full article).
Your job: identify the 3 most important *verifiable facts* in the text and turn each into a concise search query.

Rules:
- Focus on concrete facts: names, numbers, dates, events, locations.
- Skip opinions, adjectives, and vague assertions.
- One query in ENGLISH, one in the original language, one mixed/alternate angle.
- Return ONLY a JSON array of 3 strings. No markdown, no explanation."""


class QueryPlanningAgent:
    """Generate search queries using Regolo, with deterministic fallback."""

    def __init__(self, settings: Settings, llm_client: RegoloClient | None = None) -> None:
        self.settings = settings
        self.llm = llm_client or RegoloClient(
            api_key=settings.regolo_api_key,
            base_url=settings.regolo_base_url,
            llm_model=settings.regolo_model,
        )

    async def run(self, state: PipelineState) -> PipelineState:
        text = state.normalized_text or state.raw_content
        state.generated_queries = await self.generate_queries(text)
        logger.info("    generated_queries=%d", len(state.generated_queries))
        return state

    async def generate_queries(self, text: str) -> list[str]:
        snippet = text[:3000]
        try:
            raw = await self.llm.generate_text(
                prompt=f'Text to fact-check:\n"""\n{snippet}\n"""',
                system_prompt=QUERY_GEN_SYSTEM,
                max_tokens=300,
                temperature=0.2,
            )
            parsed = parse_llm_json(raw)
            if isinstance(parsed, list) and parsed:
                queries: list[str] = []
                for item in parsed[:3]:
                    if isinstance(item, str):
                        queries.append(item)
                    elif isinstance(item, dict):
                        queries.append(str(next(iter(item.values()))))
                    else:
                        queries.append(str(item))
                if queries:
                    return queries
        except Exception as exc:
            logger.warning("    query gen failed: %s", exc)

        return self.fallback_queries(text)

    def fallback_queries(self, text: str) -> list[str]:
        cleaned = " ".join((text or "").split())
        if not cleaned:
            return []
        snippet = cleaned[:300]
        return [snippet]
