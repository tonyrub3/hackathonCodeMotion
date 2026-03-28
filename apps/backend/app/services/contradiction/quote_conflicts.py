"""Quote conflict detection heuristics."""

from __future__ import annotations

from typing import Any

from app.services.contradiction.utils import extract_quotes, group_evidence_by_claim, normalize_text, pairwise


def detect_quote_conflicts(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect contradictions in quoted text across evidence."""
    conflicts: list[dict[str, Any]] = []
    grouped = group_evidence_by_claim(evidence)

    for claim_id, items in grouped.items():
        if claim_id == "__unmatched__" or len(items) < 2:
            continue

        claim_type = _claim_type_for_items(items)
        supporting = [item for item in items if item.get("stance") == "supporting"]
        contradicting = [item for item in items if item.get("stance") == "contradicting"]
        if claim_type != "quote" and (not supporting or not contradicting):
            continue

        for ev_a, ev_b in pairwise(items):
            quotes_a = extract_quotes(ev_a.get("excerpt", ""))
            quotes_b = extract_quotes(ev_b.get("excerpt", ""))
            if not quotes_a or not quotes_b:
                continue

            if _quote_sets_overlap(quotes_a, quotes_b):
                continue

            conflicts.append(
                {
                    "claim_id": claim_id,
                    "type": "quote",
                    "description": (
                        f"Quoted passages differ between sources: {quotes_a[0]!r} vs {quotes_b[0]!r}."
                    ),
                    "evidence_a_id": ev_a.get("source_id", ""),
                    "evidence_b_id": ev_b.get("source_id", ""),
                    "severity": 0.55 if claim_type == "quote" else 0.4,
                }
            )

    return conflicts


def _quote_sets_overlap(left: list[str], right: list[str]) -> bool:
    """Return True when two quote lists share the same normalized fragment."""
    left_norm = {normalize_text(item) for item in left}
    right_norm = {normalize_text(item) for item in right}
    return bool(left_norm & right_norm)


def _claim_type_for_items(items: list[dict[str, Any]]) -> str:
    """Infer the claim type from the attached evidence items."""
    for item in items:
        claim_type = str(item.get("claim_type", "")).strip().lower()
        if claim_type:
            return claim_type
    return ""
