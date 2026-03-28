"""Tests for the judge/report agent."""

from unittest.mock import patch

import pytest

from app.agents.judge_agent import JudgeAgent
from app.config import Settings
from app.core.state import PipelineState


@pytest.mark.asyncio
async def test_judge_passes_linguistic_risk_and_localizes_report():
    agent = JudgeAgent(Settings())
    state = PipelineState(
        normalized_text="Questo testo e scioccante e allarmante.",
        language="it",
        claims=[{"id": "c1", "claim": "Il PIL cresce", "checkability_score": 0.5, "type": "statistical"}],
        sources_used=[],
        scored_evidence=[],
        contradictions=[],
        consensus_signals={},
    )
    captured: dict[str, object] = {}

    def fake_compute_truth_score(*args, **kwargs):
        captured["linguistic_risk"] = kwargs.get("linguistic_risk")
        return 42.0

    with patch("app.agents.judge_agent.compute_truth_score", side_effect=fake_compute_truth_score):
        await agent.run(state)

    assert state.truth_score == 42.0
    assert isinstance(captured["linguistic_risk"], dict)
    assert captured["linguistic_risk"]["sensationalism_score"] > 0
    assert "scioccante" in captured["linguistic_risk"]["manipulation_markers"]
    assert state.explanation["summary"].startswith("Non ci sono prove sufficienti")
