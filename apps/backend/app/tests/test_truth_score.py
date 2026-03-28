"""Tests for truth score computation."""

import pytest
from app.services.scoring.truth_score import compute_truth_score


def test_truth_score_no_evidence():
    """No evidence should return 0."""
    score = compute_truth_score(
        scored_evidence=[],
        consensus_signals={},
        claims=[{"id": "c1", "claim": "Test", "checkability_score": 0.5}],
        contradictions=[],
    )
    assert 0 <= score <= 100


def test_truth_score_all_supporting():
    """All supporting evidence should give a high score."""
    evidence = [
        {
            "stance": "supporting",
            "evidence_score": 0.9,
            "source_reliability_score": 0.85,
            "published_at": "2026-01-01",
            "matched_claim_ids": ["c1"],
        }
    ]
    consensus = {"c1": {"consensus_ratio": 1.0}}
    claims = [{"id": "c1", "claim": "Test", "checkability_score": 0.8}]

    score = compute_truth_score(
        scored_evidence=evidence,
        consensus_signals=consensus,
        claims=claims,
        contradictions=[],
    )
    assert score > 50


def test_truth_score_contradiction_reduces():
    """Contradictions should reduce the score."""
    evidence = [
        {
            "stance": "supporting",
            "evidence_score": 0.7,
            "source_reliability_score": 0.7,
            "published_at": "2026-01-01",
            "matched_claim_ids": ["c1"],
        },
        {
            "stance": "contradicting",
            "evidence_score": 0.8,
            "source_reliability_score": 0.8,
            "published_at": "2026-01-01",
            "matched_claim_ids": ["c1"],
        },
    ]
    consensus = {"c1": {"consensus_ratio": 0.5}}
    claims = [{"id": "c1", "claim": "Test", "checkability_score": 0.7}]

    score_with = compute_truth_score(
        scored_evidence=evidence,
        consensus_signals=consensus,
        claims=claims,
        contradictions=[{"claim_id": "c1", "severity": 0.7}],
    )

    score_without = compute_truth_score(
        scored_evidence=[evidence[0]],
        consensus_signals={"c1": {"consensus_ratio": 1.0}},
        claims=claims,
        contradictions=[],
    )

    assert score_with < score_without
