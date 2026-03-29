"""Tests for the AI-assisted query planning agent."""

from __future__ import annotations

import pytest

from app.agents.query_planning_agent import QueryPlanningAgent
from app.config import Settings
from app.core.state import PipelineState


class DummyLLM:
    def __init__(self, response: str | Exception) -> None:
        self.response = response

    async def generate_text(self, **_: object) -> str:
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
async def test_query_planning_agent_falls_back_to_snippet() -> None:
    agent = QueryPlanningAgent(Settings(), llm_client=DummyLLM(RuntimeError("boom")))

    queries = await agent.generate_queries("A short factual text for fallback.")

    assert queries == ["A short factual text for fallback."]
