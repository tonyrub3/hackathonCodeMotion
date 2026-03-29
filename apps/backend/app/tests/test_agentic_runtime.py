"""Tests for the new agentic Tavily-first runtime."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.core.state import PipelineState
from app.pipeline.tavily_first import TavilyFirstEngine
from app.agents.verdict_consistency_agent import VerdictConsistencyAgent


@pytest.mark.asyncio
async def test_no_direct_evidence_blocks_high_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_search(**_: object) -> dict:
        return {
            "answer": "The current Pope is Leo XIV.",
            "results": [
                {
                    "url": "https://example.com/a",
                    "title": "Pope Leo visits Monaco",
                    "content": "Pope Leo XIV visited Monaco this week.",
                    "raw_content": "Pope Leo XIV visited Monaco this week.",
                    "score": 0.92,
                }
            ],
        }

    async def fake_extract(**_: object) -> dict:
        return {"results": []}

    monkeypatch.setattr("app.agents.discovery_agent.tavily_search", fake_search)
    monkeypatch.setattr("app.agents.discovery_agent.tavily_extract", fake_extract)

    engine = TavilyFirstEngine(Settings())
    state = PipelineState(normalized_text="Il Papa attuale è Bergoglio.", language="it")
    state = await engine.run(state)

    assert state.verdict not in {"verified", "mostly_verified"}
    assert state.confidence_score <= 0.35
    assert state.all_sources_found


@pytest.mark.asyncio
async def test_source_list_complete_and_forensics_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_search(**_: object) -> dict:
        return {
            "answer": "Auxiliary hint.",
            "results": [
                {"url": "https://source-a.example/article", "title": "A", "content": "Alpha beta claim.", "raw_content": "Alpha beta claim.", "score": 0.81},
                {"url": "https://source-b.example/article", "title": "B", "content": "Alpha beta extra.", "raw_content": "Alpha beta extra.", "score": 0.71},
                {"url": "https://source-c.example/article", "title": "C", "content": "Alpha beta overflow.", "raw_content": "Alpha beta overflow.", "score": 0.61},
            ],
        }

    async def fake_extract(**_: object) -> dict:
        return {"results": []}

    monkeypatch.setattr("app.agents.discovery_agent.tavily_search", fake_search)
    monkeypatch.setattr("app.agents.discovery_agent.tavily_extract", fake_extract)

    engine = TavilyFirstEngine(Settings())
    state = PipelineState(normalized_text="Alpha beta happened in Rome.", language="en")
    state = await engine.run(state)

    assert len(state.all_sources_found) >= 3
    assert state.selected_sources
    assert state.source_forensics
    assert all("forensic_score" in item for item in state.source_forensics)


@pytest.mark.asyncio
async def test_false_positive_high_confidence_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_search(**_: object) -> dict:
        return {
            "results": [
                {
                    "url": "https://source-a.example/article",
                    "title": "Pope Leo is current Pope",
                    "content": "Pope Leo XIV is the current Pope according to multiple reports.",
                    "raw_content": "Pope Leo XIV is the current Pope according to multiple reports.",
                    "score": 0.95,
                }
            ]
        }

    async def fake_extract(**_: object) -> dict:
        return {"results": []}

    monkeypatch.setattr("app.agents.discovery_agent.tavily_search", fake_search)
    monkeypatch.setattr("app.agents.discovery_agent.tavily_extract", fake_extract)

    engine = TavilyFirstEngine(Settings())
    state = PipelineState(normalized_text="Bergoglio è il Papa attuale.", language="it")
    state = await engine.run(state)

    assert state.confidence_score < 0.7
    assert state.verdict in {"insufficient_evidence", "mostly_false", "false", "mixed"}


def test_explanation_mismatch_gets_blocked() -> None:
    agent = VerdictConsistencyAgent(Settings())
    state = PipelineState(
        verdict="mostly_verified",
        confidence_score=0.8,
        explanation={"summary": "Sources do not confirm the claim.", "why": "Insufficient evidence."},
        layer_outputs={},
    )
    reasons = agent.validate_explanation_alignment(state)
    assert reasons
    assert state.verdict == "insufficient_evidence"
    assert state.confidence_score <= 0.35
