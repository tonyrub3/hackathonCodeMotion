"""Conflict merger – aggregates individual conflict detectors."""

from __future__ import annotations

from typing import Any


def merge_conflicts(
    number_conflicts: list[dict[str, Any]],
    date_conflicts: list[dict[str, Any]],
    entity_conflicts: list[dict[str, Any]],
    quote_conflicts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge all conflict types into a single list, deduplicated."""
    all_conflicts = number_conflicts + date_conflicts + entity_conflicts + quote_conflicts
    # Deduplicate by claim_id + type
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for c in all_conflicts:
        key = f"{c.get('claim_id')}_{c.get('type')}"
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique
