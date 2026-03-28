"""FEVER verdict evaluation – measures verdict classification quality."""

from __future__ import annotations

from typing import Any

from app.services.benchmark.fever_mapper import verdict_to_fever_label

FEVER_LABELS = ["SUPPORTS", "REFUTES", "NOT ENOUGH INFO"]


def evaluate_verdicts(
    predictions: list[dict[str, Any]],
    gold: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate verdict predictions against FEVER gold labels.

    Args:
        predictions: List of {"claim_id": int, "verdict": str}
        gold: List of {"claim_id": int, "label": str}

    Returns:
        {"accuracy": float, "confusion_matrix": {label: {label: count}}}
    """
    gold_map = {g["claim_id"]: g["label"] for g in gold}

    # Initialize confusion matrix
    matrix: dict[str, dict[str, int]] = {
        label: {l: 0 for l in FEVER_LABELS} for label in FEVER_LABELS
    }

    correct = 0
    total = 0

    for pred in predictions:
        cid = pred["claim_id"]
        predicted_verdict = pred.get("verdict", "insufficient_evidence")
        predicted_fever = verdict_to_fever_label(predicted_verdict)

        actual_fever = gold_map.get(cid)
        if actual_fever is None:
            continue

        total += 1
        if predicted_fever == actual_fever:
            correct += 1

        if actual_fever in matrix and predicted_fever in matrix[actual_fever]:
            matrix[actual_fever][predicted_fever] += 1

    accuracy = correct / total if total > 0 else 0.0

    return {
        "accuracy": round(accuracy, 4),
        "total": total,
        "correct": correct,
        "confusion_matrix": matrix,
    }
