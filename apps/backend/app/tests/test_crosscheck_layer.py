"""Tests for the LLM cross-check analysis layer."""

from __future__ import annotations

import pytest

from app.services.analysis.crosscheck import CrossCheckAnalysisLayer


class DummyLLM:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def generate_text(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class SequenceLLM:
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    async def generate_text(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.mark.asyncio
async def test_crosscheck_layer_parses_global_judgment_json() -> None:
    llm = DummyLLM(
        """
        {
          "judgment_basis": {
            "main_claim_confirmed": true,
            "direct_support_level": "moderate",
            "contradiction_level": "none",
            "subject_only_match": false,
            "evidence_sufficiency": "high",
            "source_agreement": "high",
            "temporal_alignment": "strong"
          },
          "truth_score": 76,
          "confidence_score": 0.68,
          "verdict": "mostly_verified",
          "explanation": {
            "summary": "Le fonti convergono su gran parte del contenuto.",
            "why": "Le fonti piu pertinenti confermano il fatto centrale.",
            "supporting_evidence": ["Reuters conferma il fatto centrale."],
            "contradicting_evidence": [],
            "source_analysis": ["Reuters: fonte autorevole e pertinente."],
            "temporal_context": "I fatti riguardano il 2026.",
            "caveats": ["La verifica resta limitata al materiale disponibile."]
          },
          "per_source": [
            {
              "source_index": 0,
              "stance": "supporting",
              "relevance": 0.85,
              "key_excerpt": "confirmed by sources"
            }
          ]
        }
        """
    )
    layer = CrossCheckAnalysisLayer(llm)

    result = await layer.run(
        "Example claim",
        [{"url": "https://example.com/story", "title": "Title", "content": "Body", "score": 0.8}],
        "tier1",
    )

    assert result["truth_score"] == 76
    assert result["confidence_score"] == 0.68
    assert result["verdict"] == "mostly_verified"
    assert result["judgment_basis"]["direct_support_level"] == "moderate"
    assert len(result["per_source"]) == 1
    assert result["per_source"][0]["stance"] == "supporting"


@pytest.mark.asyncio
async def test_crosscheck_layer_sends_claims_in_prompt() -> None:
    llm = DummyLLM(
        '{"truth_score": 50, "confidence_score": 0.4, "verdict": "mixed", "explanation": {"summary": "ok", "why": "ok", "supporting_evidence": [], "contradicting_evidence": [], "source_analysis": [], "temporal_context": "", "caveats": []}, "per_source": []}'
    )
    layer = CrossCheckAnalysisLayer(llm)

    claims = [
        {"id": "c1", "claim": "Il Papa ha visitato Roma", "type": "event", "checkability_score": 0.9},
        {"id": "c2", "claim": "L'incontro e durato 2 ore", "type": "event", "checkability_score": 0.7},
    ]

    await layer.run(
        "Full article text",
        [{"url": "https://reuters.com/story", "title": "Title", "content": "Body", "score": 0.8}],
        "tier1",
        claims=claims,
    )

    prompt = str(llm.calls[0]["prompt"])
    assert "c1" in prompt
    assert "c2" in prompt
    assert "Il Papa ha visitato Roma" in prompt
    assert "CLAIM ESTRATTI" in prompt


@pytest.mark.asyncio
async def test_crosscheck_layer_raises_when_llm_fails() -> None:
    layer = CrossCheckAnalysisLayer(DummyLLM(RuntimeError("boom")))

    claims = [
        {"id": "c1", "claim": "Test claim one", "type": "event", "checkability_score": 0.8},
    ]

    with pytest.raises(RuntimeError):
        await layer.run(
            "Example claim",
            [
                {"url": "https://reuters.com/story", "title": "Title", "content": "Body", "score": 0.8},
                {"url": "https://example.com/story", "title": "Title 2", "content": "Body 2", "score": 0.6},
            ],
            "tier1",
            claims=claims,
        )


@pytest.mark.asyncio
async def test_crosscheck_layer_repairs_non_json_output_with_second_llm_pass() -> None:
    llm = SequenceLLM(
        [
            "Le fonti principali non concordano del tutto. Verdict: mixed.",
            """
            {
              "judgment_basis": {
                "main_claim_confirmed": false,
                "direct_support_level": "weak",
                "contradiction_level": "weak",
                "subject_only_match": true,
                "evidence_sufficiency": "low",
                "source_agreement": "low",
                "temporal_alignment": "medium"
              },
              "truth_score": 34,
              "confidence_score": 0.42,
              "verdict": "insufficient_evidence",
              "explanation": {
                "summary": "Le fonti non confermano in modo sufficiente il claim.",
                "why": "Le fonti parlano del contesto ma non provano il fatto centrale.",
                "supporting_evidence": [],
                "contradicting_evidence": [],
                "source_analysis": ["Reuters: fonte pertinente ma non conclusiva."],
                "temporal_context": "",
                "caveats": ["Evidenza limitata."]
              },
              "per_source": []
            }
            """,
        ]
    )
    layer = CrossCheckAnalysisLayer(llm)

    result = await layer.run(
        "Example claim",
        [{"url": "https://reuters.com/story", "title": "Title", "content": "Body", "score": 0.8}],
        "tier1",
    )

    assert result["verdict"] == "insufficient_evidence"
    assert result["truth_score"] == 34
    assert len(llm.calls) == 2
