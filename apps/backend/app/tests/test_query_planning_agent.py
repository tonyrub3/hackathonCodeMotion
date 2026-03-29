"""Tests for the AI-assisted query planning agent."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.agents.query_planning_agent import QueryPlanningAgent
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
async def test_query_planning_agent_uses_llm_json_output() -> None:
    agent = QueryPlanningAgent(
        Settings(),
        llm_client=DummyLLM('["query one", {"it": "query due"}, "query three"]'),
    )
    state = PipelineState(normalized_text="Example text")

    state = await agent.run(state)

    assert state.generated_queries == ["query one", "query due", "query three"]


@pytest.mark.asyncio
async def test_query_planning_agent_raises_when_llm_fails() -> None:
    agent = QueryPlanningAgent(Settings(), llm_client=DummyLLM(RuntimeError("boom")))

    with pytest.raises(RuntimeError):
        await agent.generate_queries("A short factual text for fallback.")


@pytest.mark.asyncio
async def test_query_planning_agent_raises_for_claim_queries_when_llm_fails() -> None:
    agent = QueryPlanningAgent(Settings(), llm_client=DummyLLM(RuntimeError("boom")))

    with pytest.raises(RuntimeError):
        await agent.generate_queries(
            "Long article text that should not be used directly.",
            claims=[
                {
                    "claim": "Il governo ha approvato un nuovo piano industriale nel 2026.",
                    "search_query": "piano industriale Italia 2026 approvazione governo",
                },
                {
                    "claim": "Il piano include investimenti aggiuntivi nel settore energia.",
                    "search_query": "investimenti energia piano industriale Italia",
                },
            ],
        )


@pytest.mark.asyncio
async def test_query_planning_agent_uses_claim_context_and_metadata_in_prompt() -> None:
    llm = DummyLLM('["query uno", "query due"]')
    agent = QueryPlanningAgent(Settings(), llm_client=llm)
    state = PipelineState(
        article_title="Vertice energia Italia 2026",
        article_date="2026-03-15",
        country="IT",
    )

    queries = await agent.generate_queries(
        "Testo articolo",
        claims=[
            {"claim": "Il governo italiano ha approvato il decreto energia nel 2026.", "search_query": "decreto energia Italia 2026"},
            {"claim": "Il decreto prevede incentivi per le imprese energivore.", "search_query": "incentivi imprese energivore decreto energia"},
        ],
        state=state,
    )

    assert queries == ["query uno", "query due"]
    assert "Vertice energia Italia 2026" in llm.last_prompt
    assert "2026-03-15" in llm.last_prompt
    assert "seed_query=decreto energia Italia 2026" in llm.last_prompt


@pytest.mark.asyncio
async def test_query_planning_agent_includes_current_date_for_relative_time() -> None:
    llm = DummyLLM('["donald trump death 2025"]')
    agent = QueryPlanningAgent(Settings(), llm_client=llm)

    await agent.generate_queries("donald trump è stato ucciso l'anno scorso")

    assert "CURRENT DATE" in llm.last_prompt
    assert str(datetime.now(timezone.utc).year) in llm.last_prompt


def test_query_planning_fallback_resolves_last_year_from_current_date() -> None:
    agent = QueryPlanningAgent(Settings(), llm_client=DummyLLM(RuntimeError("boom")))
    state = PipelineState()

    year = agent._extract_year("donald trump è stato ucciso l'anno scorso", state=state)

    assert year == str(datetime.now(timezone.utc).year - 1)
