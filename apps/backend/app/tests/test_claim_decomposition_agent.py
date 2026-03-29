"""Tests for the URL claim decomposition agent."""

from __future__ import annotations

import pytest

from app.agents.claim_decomposition_agent import ClaimDecompositionAgent
from app.config import Settings
from app.core.state import PipelineState


class DummyLLM:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.last_prompt: str = ""

    async def generate_text(self, **kwargs: object) -> str:
        self.last_prompt = str(kwargs.get("prompt", ""))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.mark.asyncio
async def test_claim_decomposition_extracts_claims_with_search_queries() -> None:
    agent = ClaimDecompositionAgent(
        Settings(),
        llm_client=DummyLLM(
            """
            [
              {
                "claim": "Il governo italiano ha annunciato un nuovo decreto energia nel 2026.",
                "search_query": "decreto energia Italia 2026 governo",
                "type": "policy",
                "checkability_score": 0.92
              },
              {
                "claim": "Il decreto prevede nuovi incentivi per le imprese energivore.",
                "search_query": "incentivi imprese energivore decreto energia Italia",
                "type": "institutional",
                "checkability_score": 0.81
              }
            ]
            """
        ),
    )
    state = PipelineState(input_type="url", normalized_text="Test article body")

    state = await agent.run(state)

    assert len(state.claims) == 2
    assert state.claims[0]["id"] == "c1"
    assert state.claims[0]["search_query"] == "decreto energia Italia 2026 governo"
    assert state.claims[1]["search_query"] == "incentivi imprese energivore decreto energia Italia"
    assert state.claims[0]["checkability_score"] == 0.92


@pytest.mark.asyncio
async def test_claim_decomposition_includes_article_metadata_in_prompt() -> None:
    llm = DummyLLM('[{"claim": "Test claim with enough characters for validation.", "search_query": "test query", "type": "event", "checkability_score": 0.8}]')
    agent = ClaimDecompositionAgent(Settings(), llm_client=llm)
    state = PipelineState(
        input_type="url",
        normalized_text="Article body",
        article_title="Decreto Energia 2026",
        article_date="2026-03-15",
        article_author="Mario Rossi",
        source_url="https://example.com/article",
    )

    await agent.run(state)

    assert "Decreto Energia 2026" in llm.last_prompt
    assert "2026-03-15" in llm.last_prompt
    assert "Mario Rossi" in llm.last_prompt


@pytest.mark.asyncio
async def test_claim_decomposition_accepts_up_to_10_claims() -> None:
    claims_json = ",\n".join(
        f'{{"claim": "Affermazione numero {i+1} con dettagli verificabili importanti.", '
        f'"search_query": "query {i+1} keywords", '
        f'"type": "event", "checkability_score": 0.8}}'
        for i in range(10)
    )
    agent = ClaimDecompositionAgent(
        Settings(),
        llm_client=DummyLLM(f"[{claims_json}]"),
    )
    state = PipelineState(input_type="url", normalized_text="Long article")

    state = await agent.run(state)

    assert len(state.claims) == 10
    assert state.claims[9]["id"] == "c10"
    assert all(c.get("search_query") for c in state.claims)


@pytest.mark.asyncio
async def test_claim_decomposition_raises_when_llm_fails() -> None:
    agent = ClaimDecompositionAgent(Settings(), llm_client=DummyLLM(RuntimeError("boom")))
    state = PipelineState(
        input_type="url",
        normalized_text=(
            "Il presidente Macron ha visitato Monaco nel 2026 durante una missione diplomatica ufficiale. "
            "L'incontro ha coinvolto rappresentanti del governo locale e dell'Unione Europea. "
            "Il portavoce ha dichiarato che i colloqui sono stati produttivi e costruttivi. "
            "Le delegazioni hanno discusso di cooperazione economica e sicurezza regionale. "
            "Il presidente ha confermato nuovi accordi bilaterali per il commercio estero. "
            "La visita si concludera con una conferenza stampa congiunta prevista per domani. "
            "Secondo fonti diplomatiche, l'accordo include anche clausole sulla sicurezza energetica."
        ),
    )

    with pytest.raises(RuntimeError):
        await agent.run(state)


@pytest.mark.asyncio
async def test_claim_decomposition_fallback_query_extracts_keywords() -> None:
    """When LLM doesn't provide search_query, the fallback should extract keywords."""
    agent = ClaimDecompositionAgent(
        Settings(),
        llm_client=DummyLLM(
            """
            [
              {
                "claim": "Il Papa Francesco ha visitato Monaco il 15 marzo 2026 per un incontro diplomatico.",
                "type": "event",
                "checkability_score": 0.9
              }
            ]
            """
        ),
    )
    state = PipelineState(input_type="url", normalized_text="Test")

    state = await agent.run(state)

    query = state.claims[0]["search_query"]
    assert query  # Not empty
    # Should contain key entities
    assert "Papa" in query or "Francesco" in query
    assert "Monaco" in query
    assert "2026" in query
