"""Claim annotation builder – annotates original text with claim-level verdicts."""

from __future__ import annotations

from typing import Any


def build_claim_annotations(
    original_text: str,
    claims: list[dict[str, Any]],
    partial_verdicts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Map partial verdicts back to original text positions.

    Returns a list of annotations that a frontend can use
    to highlight claims in the original text.
    """
    verdict_map = {pv["id"]: pv for pv in partial_verdicts}
    annotations: list[dict[str, Any]] = []

    for claim in claims:
        cid = claim["id"]
        pv = verdict_map.get(cid, {})
        claim_text = claim.get("claim", "")

        # Find position in original text (simple substring search)
        start = original_text.find(claim_text)

        annotations.append({
            "claim_id": cid,
            "claim_text": claim_text,
            "start": start if start >= 0 else -1,
            "end": (start + len(claim_text)) if start >= 0 else -1,
            "verdict": pv.get("partial_verdict", "insufficient_evidence"),
            "score": pv.get("partial_score", 0.0),
            "type": claim.get("type", "event"),
        })

    return annotations
