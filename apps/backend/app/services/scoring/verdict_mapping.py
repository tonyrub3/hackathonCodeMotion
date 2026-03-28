"""
Verdict mapping – maps truth score to a nuanced verdict label.

Mapping (from spec §19):
  85–100 → verified
  70–84  → mostly_verified
  55–69  → mixed
  40–54  → misleading or decontextualized
  25–39  → mostly_false
   0–24  → false

Override rules:
  - If evidence is too weak → insufficient_evidence regardless of score
  - If context is missing but core fact is correct → decontextualized
"""

from __future__ import annotations

from typing import Any


def map_verdict(
    truth_score: float,
    confidence: float,
    evidence_count: int,
    contradictions: list[dict[str, Any]] | None = None,
) -> str:
    """Map a truth score to a verdict label with override rules.

    Args:
        truth_score: 0-100 score
        confidence: 0-1 confidence level
        evidence_count: total evidence items found
        contradictions: list of detected contradictions

    Returns:
        One of the 8 verdict labels.
    """
    contradictions = contradictions or []

    # Override: insufficient evidence
    if evidence_count == 0 or confidence < 0.15:
        return "insufficient_evidence"

    # Override: very low evidence with moderate score → insufficient
    if evidence_count <= 1 and truth_score < 70:
        return "insufficient_evidence"

    # Score-based mapping
    if truth_score >= 85:
        return "verified"
    if truth_score >= 70:
        return "mostly_verified"
    if truth_score >= 55:
        return "mixed"
    if truth_score >= 40:
        # Check if contradictions suggest decontextualization
        if contradictions and any(
            c.get("type") == "temporal" or c.get("severity", 0) < 0.4
            for c in contradictions
        ):
            return "decontextualized"
        return "misleading"
    if truth_score >= 25:
        return "mostly_false"
    return "false"
