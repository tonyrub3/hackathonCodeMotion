"""Source summary builder – human-readable summary of source trust decisions."""

from __future__ import annotations

from typing import Any


def build_source_summary(sources_used: list[dict[str, Any]]) -> list[str]:
    """Produce a list of human-readable explanations for each source's trust level."""
    summaries: list[str] = []

    for src in sources_used:
        name = src.get("source_name", "Unknown")
        tier = src.get("tier", "C")
        score = src.get("source_reliability_score", 0.5)
        src_type = src.get("source_type", "news")

        tier_label = {"A": "primary/official", "B": "trusted secondary", "C": "weak/indirect"}.get(tier, "unclassified")

        if score >= 0.75:
            trust_note = "high reliability"
        elif score >= 0.50:
            trust_note = "moderate reliability"
        else:
            trust_note = "low reliability"

        summaries.append(
            f"{name} ({src_type}, tier {tier} – {tier_label}): "
            f"reliability {score:.2f} ({trust_note})"
        )

    return summaries
