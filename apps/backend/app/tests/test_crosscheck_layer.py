"""Tests for the LLM cross-check analysis layer."""

from __future__ import annotations

import pytest

from app.services.analysis.crosscheck import CrossCheckAnalysisLayer


class DummyLLM:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def generate_text(self, **_: object) -> str:
        self.calls.append(_)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.mark.asyncio
async def test_crosscheck_layer_parses_valid_json() -> None:
    llm = DummyLLM(
        """
        {
          "truth_score": 77,
          "confidence_score": 0.64,
          "verdict": "mostly_verified",
          "explanation": {
            "summary": "ok",
            "why": "ok",
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "source_analysis": [],
            "temporal_context": "",
            "caveats": []
          },
          "per_source": []
        }
        """
    )
    layer = CrossCheckAnalysisLayer(llm)

    result = await layer.run(
        "Example claim",
        [{"url": "https://example.com/story", "title": "Title", "content": "Body", "score": 0.8}],
        "tier1",
    )

    assert result["truth_score"] == 77
    assert result["verdict"] == "mostly_verified"
    assert 'Write every field inside "explanation" in Italian.' in str(llm.calls[0]["system_prompt"])


@pytest.mark.asyncio
async def test_crosscheck_layer_falls_back_when_llm_fails() -> None:
    layer = CrossCheckAnalysisLayer(DummyLLM(RuntimeError("boom")))

    result = await layer.run(
        "Example claim",
        [
            {"url": "https://reuters.com/story", "title": "Title", "content": "Body", "score": 0.8},
            {"url": "https://example.com/story", "title": "Title 2", "content": "Body 2", "score": 0.6},
        ],
        "tier1",
    )

    assert result["verdict"] in {"mostly_verified", "mixed"}
    assert len(result["explanation"]["source_analysis"]) == 2
    assert len(result["per_source"]) == 2
    assert result["explanation"]["summary"].startswith("Analisi di fallback")
