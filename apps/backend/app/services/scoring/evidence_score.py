"""
Evidence scoring – per-evidence-item score.

Formula (from spec §15):
  evidence_score =
    0.30 * source_reliability_score +
    0.20 * relevance_score +
    0.20 * directness_score +
    0.15 * specificity_score +
    0.10 * temporal_fit +
    0.05 * geographic_fit
"""

from __future__ import annotations


def compute_evidence_score(
    source_reliability: float,
    relevance: float,
    directness: float,
    specificity: float,
    temporal_fit: float,
    geographic_fit: float,
) -> float:
    """Compute the weighted evidence score.

    All inputs should be in [0, 1]. Output is in [0, 1].
    """
    score = (
        0.30 * _clamp(source_reliability)
        + 0.20 * _clamp(relevance)
        + 0.20 * _clamp(directness)
        + 0.15 * _clamp(specificity)
        + 0.10 * _clamp(temporal_fit)
        + 0.05 * _clamp(geographic_fit)
    )
    return round(max(0.0, min(1.0, score)), 3)


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))
