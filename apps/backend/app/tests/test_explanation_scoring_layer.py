"""Tests for LLM-based explanation scoring."""

from __future__ import annotations

import pytest

from app.services.analysis.explanation_scoring import ExplanationScoringLayer


class DummyLLM:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def generate_text(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.mark.asyncio
async def test_explanation_scoring_layer_parses_llm_json() -> None:
    llm = DummyLLM('{"truth_score": 28, "confidence_score": 0.34, "verdict": "insufficient_evidence", "reasoning": "L\'explanation dice che le fonti non confermano il claim."}')
    layer = ExplanationScoringLayer(llm)

    result = await layer.run(
        {
            "summary": "Le fonti non confermano il claim principale.",
            "why": "Le fonti parlano del soggetto ma non del fatto.",
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "source_analysis": [],
            "temporal_context": "",
            "caveats": ["Evidenza insufficiente."],
        },
        search_tier="tier1",
    )

    assert result["verdict"] == "insufficient_evidence"
    assert result["truth_score"] == 28
    assert result["confidence_score"] == 0.34
    assert "SUMMARY" in str(llm.calls[0]["prompt"])


@pytest.mark.asyncio
async def test_explanation_scoring_layer_raises_on_failure() -> None:
    layer = ExplanationScoringLayer(DummyLLM(RuntimeError("boom")))

    with pytest.raises(RuntimeError):
        await layer.run({"summary": "x", "why": "y"}, search_tier="tier1")
