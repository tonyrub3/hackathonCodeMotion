"""Entity conflict detection heuristics."""

from __future__ import annotations

from typing import Any

from app.services.contradiction.utils import claim_lookup, extract_entities, group_evidence_by_claim, normalize_text


def detect_entity_conflicts(
    evidence: list[dict[str, Any]],
    claims: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Detect contradictions in named entities across evidence."""
    conflicts: list[dict[str, Any]] = []
    grouped = group_evidence_by_claim(evidence)
    claim_map = claim_lookup(claims or [])

    for claim_id, items in grouped.items():
        if claim_id == "__unmatched__" or len(items) < 2:
            continue

        claim_entities = _claim_entities(claim_map.get(claim_id, {}))
        supporting = [item for item in items if item.get("stance") == "supporting"]
        contradicting = [item for item in items if item.get("stance") == "contradicting"]
        if not supporting or not contradicting:
            continue

        for ev_a in supporting:
            for ev_b in contradicting:
                entities_a = _primary_entities(ev_a.get("excerpt", ""))
                entities_b = _primary_entities(ev_b.get("excerpt", ""))
                if not entities_a or not entities_b:
                    continue

                if _shares_claim_entity(entities_a, claim_entities) and _shares_claim_entity(entities_b, claim_entities):
                    continue

                if _entity_sets_overlap(entities_a, entities_b):
                    continue

                conflicts.append(
                    {
                        "claim_id": claim_id,
                        "type": "entity",
                        "description": (
                            f"Sources disagree on the entity focus: {entities_a[0]} vs {entities_b[0]}."
                        ),
                        "evidence_a_id": ev_a.get("source_id", ""),
                        "evidence_b_id": ev_b.get("source_id", ""),
                        "severity": 0.45 if claim_entities else 0.35,
                    }
                )

    return conflicts


def _claim_entities(claim: dict[str, Any]) -> list[str]:
    """Collect entity hints from the claim text and structured fields."""
    if not claim:
        return []
    parts = [
        str(claim.get("claim", "")),
        str(claim.get("subject", "")),
        str(claim.get("object", "")),
        str(claim.get("resolved_subject", "")),
    ]
    return _primary_entities(" ".join(part for part in parts if part))


def _primary_entities(text: str) -> list[str]:
    """Return the main entity mentions from a text snippet."""
    entities = extract_entities(text)
    if not entities:
        return []
    return entities[:3]


def _entity_sets_overlap(left: list[str], right: list[str]) -> bool:
    """Check if two entity lists share any normalized entity."""
    left_norm = {normalize_text(item) for item in left}
    right_norm = {normalize_text(item) for item in right}
    return bool(left_norm & right_norm)


def _shares_claim_entity(entities: list[str], claim_entities: list[str]) -> bool:
    """Return True when evidence entities overlap with the claim entities."""
    if not claim_entities:
        return False
    entity_norm = {normalize_text(item) for item in entities}
    claim_norm = {normalize_text(item) for item in claim_entities}
    return bool(entity_norm & claim_norm)
