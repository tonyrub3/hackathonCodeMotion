"""Conflict merger – aggregates individual conflict detectors."""

from __future__ import annotations

from typing import Any


def merge_conflicts(
    stance_conflicts: list[dict[str, Any]] | None = None,
    number_conflicts: list[dict[str, Any]] | None = None,
    date_conflicts: list[dict[str, Any]] | None = None,
    entity_conflicts: list[dict[str, Any]] | None = None,
    quote_conflicts: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Merge all conflict types into a single list, deduplicated."""
    all_conflicts = (
        (stance_conflicts or [])
        + (number_conflicts or [])
        + (date_conflicts or [])
        + (entity_conflicts or [])
        + (quote_conflicts or [])
    )
    # Deduplicate by claim_id + type + evidence pair so different disagreements survive.
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for c in all_conflicts:
        pair = tuple(sorted(
            str(item)
            for item in (
                c.get("evidence_a_id", ""),
                c.get("evidence_b_id", ""),
            )
        ))
        key = f"{c.get('claim_id')}_{c.get('type')}_{pair[0]}_{pair[1]}"
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return sorted(unique, key=lambda item: item.get("severity", 0.0), reverse=True)
