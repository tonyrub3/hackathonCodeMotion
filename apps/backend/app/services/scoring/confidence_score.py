"""
Confidence score – how confident the system is in its verdict.

Factors:
  - Amount of evidence found
  - Number of independent sources
  - Average source reliability
  - Presence of contradictions
"""

from __future__ import annotations


def compute_confidence(
    evidence_count: int,
    source_count: int,
    avg_source_reliability: float,
    has_contradictions: bool,
) -> float:
    """Compute a confidence score in [0, 1].

    Higher evidence count + more sources + higher reliability = higher confidence.
    Contradictions reduce confidence.
    """
    # Evidence volume signal (diminishing returns)
    evidence_signal = min(1.0, evidence_count / 8.0)

    # Source diversity
    source_signal = min(1.0, source_count / 5.0)

    # Reliability
    reliability_signal = avg_source_reliability

    # Contradiction penalty
    contradiction_penalty = 0.15 if has_contradictions else 0.0

    confidence = (
        0.35 * evidence_signal
        + 0.25 * source_signal
        + 0.30 * reliability_signal
        - contradiction_penalty
    )

    return round(max(0.0, min(1.0, confidence)), 2)
