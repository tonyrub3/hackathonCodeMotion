"""
Explanation builder – produces the structured explanation for the final response.

Mandatory sections (from spec §20):
  - Summary verdict
  - Why this verdict
  - Supporting evidence
  - Contradicting evidence
  - Source analysis
  - Temporal context
  - Caveats / unresolved issues
"""

from __future__ import annotations

from typing import Any


def build_explanation(
    verdict: str,
    truth_score: float,
    claims: list[dict[str, Any]],
    scored_evidence: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
    sources_used: list[dict[str, Any]],
    source_summary: list[str],
    site_forensics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the structured explanation dict."""

    supporting = [e for e in scored_evidence if e.get("stance") == "supporting"]
    contradicting = [e for e in scored_evidence if e.get("stance") == "contradicting"]

    # Summary
    summary = _build_summary(verdict, truth_score, len(claims), len(scored_evidence))

    # Why
    why = _build_why(verdict, truth_score, supporting, contradicting, contradictions)

    # Supporting evidence excerpts
    supporting_texts = [
        e.get("excerpt", "")[:200] for e in sorted(
            supporting, key=lambda x: x.get("evidence_score", 0), reverse=True
        )[:5]
        if e.get("excerpt")
    ]

    # Contradicting evidence excerpts
    contradicting_texts = [
        e.get("excerpt", "")[:200] for e in sorted(
            contradicting, key=lambda x: x.get("evidence_score", 0), reverse=True
        )[:3]
        if e.get("excerpt")
    ]

    # Temporal context
    temporal = _build_temporal_context(scored_evidence, claims)

    # Caveats
    caveats = _build_caveats(
        verdict, scored_evidence, contradictions, claims, site_forensics
    )

    return {
        "summary": summary,
        "why": why,
        "supporting_evidence": supporting_texts,
        "contradicting_evidence": contradicting_texts,
        "source_analysis": source_summary,
        "temporal_context": temporal,
        "caveats": caveats,
    }


def _build_summary(
    verdict: str, truth_score: float, claim_count: int, evidence_count: int
) -> str:
    """Build a short human-readable summary."""
    verdict_labels = {
        "verified": "The content is supported by strong evidence.",
        "mostly_verified": "The content is largely supported, with minor caveats.",
        "mixed": "The content contains a mix of supported and unsupported claims.",
        "misleading": "The content is misleading based on the evidence found.",
        "decontextualized": "The content contains facts taken out of context.",
        "insufficient_evidence": "There is not enough evidence to reach a conclusion.",
        "mostly_false": "The content is largely contradicted by the evidence.",
        "false": "The content is contradicted by strong evidence.",
    }
    base = verdict_labels.get(verdict, "Analysis complete.")
    return f"{base} (Truth score: {truth_score:.0f}/100, {claim_count} claims analyzed, {evidence_count} evidence items)"


def _build_why(
    verdict: str,
    truth_score: float,
    supporting: list[dict[str, Any]],
    contradicting: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
) -> str:
    """Plain-language explanation of why this verdict was assigned."""
    parts: list[str] = []

    if supporting:
        avg_score = sum(e.get("evidence_score", 0) for e in supporting) / len(supporting)
        parts.append(
            f"{len(supporting)} supporting evidence item(s) found "
            f"(avg score: {avg_score:.2f})."
        )

    if contradicting:
        avg_score = sum(e.get("evidence_score", 0) for e in contradicting) / len(contradicting)
        parts.append(
            f"{len(contradicting)} contradicting evidence item(s) found "
            f"(avg score: {avg_score:.2f})."
        )

    if contradictions:
        parts.append(
            f"{len(contradictions)} explicit contradiction(s) detected between sources."
        )

    if not supporting and not contradicting:
        parts.append("No strong evidence was found to support or contradict the claims.")

    return " ".join(parts)


def _build_temporal_context(
    scored_evidence: list[dict[str, Any]],
    claims: list[dict[str, Any]],
) -> str:
    """Build temporal context note."""
    dated = [e for e in scored_evidence if e.get("published_at")]
    time_claims = [c for c in claims if c.get("time_scope")]

    if time_claims:
        return (
            f"{len(time_claims)} claim(s) are time-sensitive. "
            f"{len(dated)} evidence item(s) have publication dates."
        )
    return "No specific temporal constraints detected."


def _build_caveats(
    verdict: str,
    scored_evidence: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    site_forensics: dict[str, Any] | None,
) -> list[str]:
    """List remaining uncertainties."""
    caveats: list[str] = []

    if len(scored_evidence) < 3:
        caveats.append("Limited evidence was available for this analysis.")

    if contradictions:
        caveats.append("Some sources contradict each other – further investigation recommended.")

    uncovered = [
        c for c in claims
        if not any(
            c["id"] in e.get("matched_claim_ids", []) for e in scored_evidence
        )
    ]
    if uncovered:
        caveats.append(f"{len(uncovered)} claim(s) had no matching evidence.")

    if site_forensics:
        trust = site_forensics.get("site_trust_score", 0.5)
        if trust < 0.4:
            caveats.append("The source site has low trust signals – treat with caution.")

    return caveats
