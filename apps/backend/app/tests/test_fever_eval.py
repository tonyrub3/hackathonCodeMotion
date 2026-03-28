"""Tests for FEVER evaluation utilities."""

from app.services.benchmark.fever_mapper import fever_label_to_verdict, verdict_to_fever_label
from app.services.benchmark.fever_verdict_eval import evaluate_verdicts


def test_fever_label_mapping():
    assert fever_label_to_verdict("SUPPORTS") == "verified"
    assert fever_label_to_verdict("REFUTES") == "disputed"
    assert fever_label_to_verdict("NOT ENOUGH INFO") == "insufficient_evidence"


def test_verdict_to_fever():
    assert verdict_to_fever_label("verified") == "SUPPORTS"
    assert verdict_to_fever_label("false") == "REFUTES"
    assert verdict_to_fever_label("mixed") == "NOT ENOUGH INFO"


def test_evaluate_verdicts_perfect():
    preds = [
        {"claim_id": 1, "verdict": "verified"},
        {"claim_id": 2, "verdict": "false"},
    ]
    gold = [
        {"claim_id": 1, "label": "SUPPORTS"},
        {"claim_id": 2, "label": "REFUTES"},
    ]
    result = evaluate_verdicts(preds, gold)
    assert result["accuracy"] == 1.0


def test_evaluate_verdicts_empty():
    result = evaluate_verdicts([], [])
    assert result["accuracy"] == 0.0
