"""FEVER retrieval evaluation – measures evidence retrieval quality."""

from __future__ import annotations

from typing import Any


def evaluate_retrieval(
    predictions: list[dict[str, Any]],
    gold: list[dict[str, Any]],
) -> dict[str, float]:
    """Evaluate retrieval quality against FEVER gold evidence.

    Args:
        predictions: List of {"claim_id": int, "retrieved_pages": [str]}
        gold: List of {"claim_id": int, "evidence_pages": [str]}

    Returns:
        {"recall": float, "precision": float, "partial_hit_rate": float}
    """
    total_recall = 0.0
    total_precision = 0.0
    hits = 0
    n = len(gold)

    if n == 0:
        return {"recall": 0.0, "precision": 0.0, "partial_hit_rate": 0.0}

    gold_map = {g["claim_id"]: set(g.get("evidence_pages", [])) for g in gold}

    for pred in predictions:
        cid = pred["claim_id"]
        retrieved = set(pred.get("retrieved_pages", []))
        expected = gold_map.get(cid, set())

        if not expected:
            continue

        overlap = retrieved & expected
        recall = len(overlap) / len(expected) if expected else 0.0
        precision = len(overlap) / len(retrieved) if retrieved else 0.0

        total_recall += recall
        total_precision += precision
        if overlap:
            hits += 1

    return {
        "recall": round(total_recall / n, 4),
        "precision": round(total_precision / max(len(predictions), 1), 4),
        "partial_hit_rate": round(hits / n, 4),
    }
