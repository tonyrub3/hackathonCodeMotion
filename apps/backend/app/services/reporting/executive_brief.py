"""Executive brief – concise one-paragraph summary for quick consumption."""

from __future__ import annotations

from typing import Any


def build_executive_brief(
    verdict: str,
    truth_score: float,
    confidence: float,
    claim_count: int,
    source_count: int,
    contradiction_count: int,
) -> str:
    """Generate a concise executive brief."""
    confidence_label = "high" if confidence > 0.7 else "moderate" if confidence > 0.4 else "low"

    brief = (
        f"Verdict: {verdict.upper().replace('_', ' ')} "
        f"(score {truth_score:.0f}/100, {confidence_label} confidence). "
        f"Analyzed {claim_count} claim(s) against {source_count} source(s)."
    )

    if contradiction_count > 0:
        brief += f" {contradiction_count} contradiction(s) found between sources."

    return brief
