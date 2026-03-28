"""
Truth Score – deterministic, explainable final score.

Formula (from spec §18):
  truth_score =
    (0.28 * support_strength) +
    (0.18 * consensus_score) +
    (0.18 * average_source_reliability) +
    (0.12 * temporal_validity_score) +
    (0.10 * claim_checkability_score) +
    (0.07 * evidence_coverage_score) -
    (0.17 * contradiction_strength) -
    (0.05 * linguistic_risk_penalty) -
    (0.05 * site_trust_penalty_if_url)

All components normalized to [0, 1]. Final score scaled to 0–100.
"""

from __future__ import annotations

from typing import Any


def compute_truth_score(
    scored_evidence: list[dict[str, Any]],
    consensus_signals: dict[str, Any],
    claims: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
    site_forensics: dict[str, Any] | None = None,
    linguistic_risk: dict[str, Any] | None = None,
) -> float:
    """Compute the global truth score (0-100)."""
    if not claims:
        return 0.0

    # --- Support strength ---
    supporting = [e for e in scored_evidence if e.get("stance") == "supporting"]
    support_strength = (
        sum(e.get("evidence_score", 0.5) for e in supporting) / max(len(supporting), 1)
        if supporting
        else 0.0
    )

    # --- Contradiction strength ---
    contradicting = [e for e in scored_evidence if e.get("stance") == "contradicting"]
    contradiction_strength = (
        sum(e.get("evidence_score", 0.5) for e in contradicting) / max(len(contradicting), 1)
        if contradicting
        else 0.0
    )

    # --- Consensus ---
    consensus_values = [
        v.get("consensus_ratio", 0.5) for v in consensus_signals.values()
    ]
    consensus_score = (
        sum(consensus_values) / len(consensus_values) if consensus_values else 0.5
    )

    # --- Average source reliability ---
    reliabilities = [e.get("source_reliability_score", 0.5) for e in scored_evidence]
    avg_reliability = (
        sum(reliabilities) / len(reliabilities) if reliabilities else 0.5
    )

    # --- Temporal validity (simplified) ---
    has_dates = sum(1 for e in scored_evidence if e.get("published_at"))
    temporal_validity = min(1.0, has_dates / max(len(scored_evidence), 1) + 0.3)

    # --- Claim checkability ---
    checkabilities = [c.get("checkability_score", 0.5) for c in claims]
    avg_checkability = sum(checkabilities) / len(checkabilities) if checkabilities else 0.5

    # --- Evidence coverage ---
    claims_with_evidence = set()
    for e in scored_evidence:
        for cid in e.get("matched_claim_ids", []):
            claims_with_evidence.add(cid)
    evidence_coverage = len(claims_with_evidence) / max(len(claims), 1)

    # --- Linguistic risk penalty ---
    ling_penalty = 0.0
    if linguistic_risk:
        ling_penalty = linguistic_risk.get("sensationalism_score", 0.0) * 0.5 + \
                       linguistic_risk.get("attribution_risk", 0.0) * 0.5

    # --- Site trust penalty (URL only) ---
    site_penalty = 0.0
    if site_forensics:
        site_trust = site_forensics.get("site_trust_score", 0.5)
        site_penalty = max(0.0, 1.0 - site_trust)  # Lower trust = higher penalty

    # --- Compute final score ---
    raw = (
        0.28 * support_strength
        + 0.18 * consensus_score
        + 0.18 * avg_reliability
        + 0.12 * temporal_validity
        + 0.10 * avg_checkability
        + 0.07 * evidence_coverage
        - 0.17 * contradiction_strength
        - 0.05 * ling_penalty
        - 0.05 * site_penalty
    )

    # Scale to 0-100
    score = raw * 100
    return round(max(0.0, min(100.0, score)), 1)
