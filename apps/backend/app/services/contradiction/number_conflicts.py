"""Number conflict detection heuristics."""

from __future__ import annotations

from typing import Any

from app.services.contradiction.utils import extract_numbers, group_evidence_by_claim, pairwise


def detect_number_conflicts(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect contradictions in numeric values across evidence."""
    conflicts: list[dict[str, Any]] = []
    grouped = group_evidence_by_claim(evidence)

    for claim_id, items in grouped.items():
        if claim_id == "__unmatched__" or len(items) < 2:
            continue

        for ev_a, ev_b in pairwise(items):
            numbers_a = extract_numbers(ev_a.get("excerpt", ""))
            numbers_b = extract_numbers(ev_b.get("excerpt", ""))
            best_pair = _best_number_pair(numbers_a, numbers_b)
            if not best_pair:
                continue

            left, right = best_pair
            if not _numbers_conflict(left, right):
                continue

            conflicts.append(
                {
                    "claim_id": claim_id,
                    "type": "number",
                    "description": (
                        f"Numeric values differ between sources: {left['raw']} vs {right['raw']}."
                    ),
                    "evidence_a_id": ev_a.get("source_id", ""),
                    "evidence_b_id": ev_b.get("source_id", ""),
                    "severity": _severity_for_numbers(left["value"], right["value"], left["unit"], right["unit"]),
                }
            )

    return conflicts


def _best_number_pair(
    left_numbers: list[dict[str, Any]],
    right_numbers: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Pick the most comparable numeric pair between two excerpts."""
    best: tuple[dict[str, Any], dict[str, Any]] | None = None
    best_distance = float("inf")

    for left in left_numbers:
        for right in right_numbers:
            if not _units_compatible(left.get("unit", ""), right.get("unit", "")):
                continue
            distance = abs(float(left["value"]) - float(right["value"]))
            if distance < best_distance:
                best_distance = distance
                best = (left, right)

    if best is None and left_numbers and right_numbers:
        # Fallback: compare the closest numeric values even if units are absent.
        for left in left_numbers:
            for right in right_numbers:
                distance = abs(float(left["value"]) - float(right["value"]))
                if distance < best_distance:
                    best_distance = distance
                    best = (left, right)

    return best


def _numbers_conflict(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Decide whether two numbers are actually in conflict."""
    left_value = float(left["value"])
    right_value = float(right["value"])
    if left_value == right_value:
        return False

    left_unit = str(left.get("unit", "") or "").strip()
    right_unit = str(right.get("unit", "") or "").strip()
    if left_unit and right_unit and not _units_compatible(left_unit, right_unit):
        return False

    diff = abs(left_value - right_value)
    scale = max(abs(left_value), abs(right_value), 1.0)
    relative_diff = diff / scale

    if left_unit in {"%", "percent", "percento", "per cento"} or right_unit in {"%", "percent", "percento", "per cento"}:
        return relative_diff >= 0.05

    if scale < 10:
        return diff >= 1.0

    return relative_diff >= 0.15


def _units_compatible(left_unit: str, right_unit: str) -> bool:
    """Return True if two numeric units are broadly compatible."""
    left_norm = _normalize_unit(left_unit)
    right_norm = _normalize_unit(right_unit)
    if not left_norm or not right_norm:
        return True
    if left_norm == right_norm:
        return True
    compatible_groups = [
        {"%", "percent", "percento", "per cento"},
        {"euro", "eur", "€"},
        {"usd", "dollar", "$"},
        {"million", "millions", "mila", "thousand", "billion", "billions"},
    ]
    return any(left_norm in group and right_norm in group for group in compatible_groups)


def _normalize_unit(unit: str) -> str:
    """Normalize a unit token for comparison."""
    return unit.casefold().strip()


def _severity_for_numbers(left_value: float, right_value: float, left_unit: str, right_unit: str) -> float:
    """Compute a conflict severity for numeric disagreements."""
    diff = abs(left_value - right_value)
    scale = max(abs(left_value), abs(right_value), 1.0)
    severity = diff / scale
    if _normalize_unit(left_unit) != _normalize_unit(right_unit) and left_unit and right_unit:
        severity += 0.1
    return round(min(1.0, max(0.2, severity)), 2)
