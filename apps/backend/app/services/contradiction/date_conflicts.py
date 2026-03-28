"""Date conflict detection heuristics."""

from __future__ import annotations

from typing import Any

from app.services.contradiction.utils import extract_dates, group_evidence_by_claim, pairwise


def detect_date_conflicts(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect contradictions in dates across evidence."""
    conflicts: list[dict[str, Any]] = []
    grouped = group_evidence_by_claim(evidence)

    for claim_id, items in grouped.items():
        if claim_id == "__unmatched__" or len(items) < 2:
            continue

        for ev_a, ev_b in pairwise(items):
            dates_a = extract_dates(ev_a.get("excerpt", ""))
            dates_b = extract_dates(ev_b.get("excerpt", ""))
            if not dates_a or not dates_b:
                continue

            if _date_sets_overlap(dates_a, dates_b):
                continue

            best_a = dates_a[0]
            best_b = dates_b[0]
            conflicts.append(
                {
                    "claim_id": claim_id,
                    "type": "temporal",
                    "description": (
                        f"Evidence items mention different dates: {best_a['raw']} vs {best_b['raw']}."
                    ),
                    "evidence_a_id": ev_a.get("source_id", ""),
                    "evidence_b_id": ev_b.get("source_id", ""),
                    "severity": _temporal_severity(best_a["value"], best_b["value"]),
                }
            )

    return conflicts


def _date_sets_overlap(left_dates: list[dict[str, Any]], right_dates: list[dict[str, Any]]) -> bool:
    """Return True when two evidence items share at least one normalized date."""
    left_values = {item["value"] for item in left_dates}
    right_values = {item["value"] for item in right_dates}
    if left_values & right_values:
        return True

    left_years = _years_from_dates(left_dates)
    right_years = _years_from_dates(right_dates)
    return bool(left_years & right_years)


def _temporal_severity(left_value: str, right_value: str) -> float:
    """Compute severity for a date disagreement."""
    left_year = _extract_year(left_value)
    right_year = _extract_year(right_value)
    if left_year and right_year:
        diff = abs(left_year - right_year)
        return round(min(1.0, max(0.25, diff / 10.0)), 2)
    return 0.45


def _extract_year(value: str) -> int:
    """Extract a year from a normalized date string."""
    if not value:
        return 0
    try:
        return int(value[:4])
    except ValueError:
        return 0


def _years_from_dates(dates: list[dict[str, Any]]) -> set[int]:
    """Collect year buckets from a list of date objects."""
    years: set[int] = set()
    for item in dates:
        year = _extract_year(str(item.get("value", "")))
        if year:
            years.add(year)
    return years
