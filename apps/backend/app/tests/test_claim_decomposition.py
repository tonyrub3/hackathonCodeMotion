"""Tests for claim decomposition utilities."""

from unittest.mock import patch

import pytest

from app.agents.claim_decomposition_agent import ClaimDecompositionAgent
from app.config import Settings
from app.core.state import PipelineState
from app.services.parsing.sentence_splitter import split_sentences


def test_split_simple_sentences():
    text = "The sky is blue. Water is wet. Fire is hot."
    result = split_sentences(text)
    assert len(result) == 3


def test_split_handles_abbreviations():
    text = "Dr. Smith said the rate is 2.5%. Mr. Jones agreed."
    result = split_sentences(text)
    assert len(result) == 2


def test_split_empty_text():
    assert split_sentences("") == []


def test_split_single_sentence():
    text = "Inflation in Italy rose to 2 percent."
    result = split_sentences(text)
    assert len(result) == 1
    assert "Inflation" in result[0]


def test_split_handles_italian_abbreviations():
    text = "Dott. Rossi ha detto che l'inflazione è al 2%. Il governo ha reagito."
    result = split_sentences(text)
    assert len(result) == 2
    assert result[0].startswith("Dott.")


def test_classify_type_handles_italian_keywords():
    agent = ClaimDecompositionAgent(Settings(regolo_api_key="dummy"))

    assert agent._classify_type("Il PIL italiano è cresciuto nel 2026.") == "statistical"
    assert agent._classify_type("Il ministro ha dichiarato che il piano è pronto.") == "quote"
    assert agent._classify_type("Il Parlamento ha approvato una legge sul clima.") == "regulatory"
    assert agent._classify_type("Il governo ha annunciato misure perché i prezzi sono saliti.") == "causal"


@pytest.mark.asyncio
async def test_italian_causal_sentence_triggers_llm_and_keeps_original_text():
    settings = Settings(regolo_api_key="dummy", regolo_model="test-model")
    agent = ClaimDecompositionAgent(settings)
    captured: dict[str, str] = {}

    async def fake_complete_json(self, prompt, max_tokens=1024):
        captured["prompt"] = prompt
        return [
            {
                "claim": "dummy",
                "type": "causal",
                "subject": "",
                "predicate": "",
                "object": "",
                "time_scope": "",
                "geo_scope": "",
                "checkability_score": 0.5,
                "dependency_type": "standalone",
                "requires_evidence_type": ["general"],
            }
        ]

    with patch("app.services.llm.regolo_client.RegoloClient.complete_json", new=fake_complete_json):
        state = PipelineState(
            normalized_text="L'inflazione è aumentata perché i prezzi dell'energia sono saliti.",
            language="it",
        )
        await agent.run(state)

    assert "L'inflazione è aumentata perché i prezzi dell'energia sono saliti." in captured["prompt"]
    assert "Do not translate it" in captured["prompt"]
    assert state.claims[0]["type"] == "causal"


@pytest.mark.asyncio
async def test_simple_italian_pronoun_sentence_resolves_previous_context():
    agent = ClaimDecompositionAgent(Settings())
    state = PipelineState(
        normalized_text="Il governo ha approvato il piano. Questo porterà a nuovi investimenti.",
        language="it",
    )

    await agent.run(state)

    assert len(state.claims) == 2
    assert state.claims[0]["subject"].lower().startswith("il governo")
    assert "piano" in state.claims[0]["object"].lower()
    assert state.claims[1]["dependency_type"] == "c1"
    assert state.claims[1]["coreference_resolved"] is True
    assert "piano" in state.claims[1]["subject"].lower()
