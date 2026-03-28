"""Tests for contradiction detection heuristics."""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.evidence_analysis_agent import EvidenceAnalysisAgent
from app.config import Settings
from app.core.state import PipelineState
from app.services.contradiction.date_conflicts import detect_date_conflicts
from app.services.contradiction.entity_conflicts import detect_entity_conflicts
from app.services.contradiction.number_conflicts import detect_number_conflicts
from app.services.contradiction.quote_conflicts import detect_quote_conflicts


def test_detect_number_conflicts():
    evidence = [
        {"source_id": "a", "excerpt": "The inflation rate is 2%.", "matched_claim_ids": ["c1"]},
        {"source_id": "b", "excerpt": "The inflation rate is 3%.", "matched_claim_ids": ["c1"]},
    ]

    conflicts = detect_number_conflicts(evidence)

    assert any(item["type"] == "number" for item in conflicts)
    assert conflicts[0]["claim_id"] == "c1"


def test_detect_date_conflicts():
    evidence = [
        {"source_id": "a", "excerpt": "The event happened in 2024.", "matched_claim_ids": ["c1"]},
        {"source_id": "b", "excerpt": "The event happened in 2025.", "matched_claim_ids": ["c1"]},
    ]

    conflicts = detect_date_conflicts(evidence)

    assert any(item["type"] == "temporal" for item in conflicts)


def test_detect_entity_conflicts():
    evidence = [
        {"source_id": "a", "excerpt": "Apple said the product is ready.", "matched_claim_ids": ["c1"], "stance": "supporting"},
        {"source_id": "b", "excerpt": "Samsung said the product is not ready.", "matched_claim_ids": ["c1"], "stance": "contradicting"},
    ]
    claims = [{"id": "c1", "claim": "Apple has released the product", "subject": "Apple"}]

    conflicts = detect_entity_conflicts(evidence, claims)

    assert any(item["type"] == "entity" for item in conflicts)


def test_detect_quote_conflicts():
    evidence = [
        {
            "source_id": "a",
            "excerpt": 'The minister said "We will invest more".',
            "matched_claim_ids": ["c1"],
            "claim_type": "quote",
            "stance": "supporting",
        },
        {
            "source_id": "b",
            "excerpt": 'The minister said "We will cut spending".',
            "matched_claim_ids": ["c1"],
            "claim_type": "quote",
            "stance": "contradicting",
        },
    ]

    conflicts = detect_quote_conflicts(evidence)

    assert any(item["type"] == "quote" for item in conflicts)


@pytest.mark.asyncio
async def test_evidence_analysis_agent_merges_explicit_conflicts():
    agent = EvidenceAnalysisAgent(Settings())
    state = PipelineState(
        claims=[{"id": "c1", "claim": "The inflation rate is 2%.", "type": "statistical"}],
        evidence_items=[
            {
                "source_id": "a",
                "source_name": "Source A",
                "source_type": "news",
                "tier": "B",
                "url": "https://example.com/a",
                "published_at": "2026-01-01",
                "excerpt": "The inflation rate is 2%.",
                "matched_claim_ids": ["c1"],
            },
            {
                "source_id": "b",
                "source_name": "Source B",
                "source_type": "news",
                "tier": "B",
                "url": "https://example.com/b",
                "published_at": "2026-01-02",
                "excerpt": "The inflation rate is 3%.",
                "matched_claim_ids": ["c1"],
            },
        ],
        sources_used=[],
    )

    with patch.object(
        EvidenceAnalysisAgent,
        "_classify_stance",
        new=AsyncMock(side_effect=["supporting", "contradicting"]),
    ):
        await agent.run(state)

    assert any(item["type"] == "number" for item in state.contradictions)
    assert state.consensus_signals["c1"]["supporting"] >= 1
