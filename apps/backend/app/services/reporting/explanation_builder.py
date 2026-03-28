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
    language: str = "en",
) -> dict[str, Any]:
    """Build the structured explanation dict."""
    language_key = _language_key(language)

    supporting = [e for e in scored_evidence if e.get("stance") == "supporting"]
    contradicting = [e for e in scored_evidence if e.get("stance") == "contradicting"]

    # Summary
    summary = _build_summary(verdict, truth_score, len(claims), len(scored_evidence), language_key)

    # Why
    why = _build_why(verdict, truth_score, supporting, contradicting, contradictions, language_key)

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
    temporal = _build_temporal_context(scored_evidence, claims, language_key)

    # Caveats
    caveats = _build_caveats(
        verdict, scored_evidence, contradictions, claims, site_forensics, language_key
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
    verdict: str, truth_score: float, claim_count: int, evidence_count: int, language_key: str
) -> str:
    """Build a short human-readable summary."""
    verdict_labels = {
        "verified": {
            "en": "The content is supported by strong evidence.",
            "it": "I contenuti sono supportati da prove solide.",
        },
        "mostly_verified": {
            "en": "The content is largely supported, with minor caveats.",
            "it": "I contenuti sono per lo piu supportati, con alcune cautele.",
        },
        "mixed": {
            "en": "The content contains a mix of supported and unsupported claims.",
            "it": "I contenuti includono affermazioni supportate e non supportate.",
        },
        "misleading": {
            "en": "The content is misleading based on the evidence found.",
            "it": "I contenuti sono fuorvianti in base alle prove trovate.",
        },
        "decontextualized": {
            "en": "The content contains facts taken out of context.",
            "it": "I contenuti riportano fatti fuori contesto.",
        },
        "insufficient_evidence": {
            "en": "There is not enough evidence to reach a conclusion.",
            "it": "Non ci sono prove sufficienti per arrivare a una conclusione.",
        },
        "mostly_false": {
            "en": "The content is largely contradicted by the evidence.",
            "it": "I contenuti sono in larga parte smentiti dalle prove.",
        },
        "false": {
            "en": "The content is contradicted by strong evidence.",
            "it": "I contenuti sono smentiti da prove forti.",
        },
    }
    base = verdict_labels.get(verdict, {"en": "Analysis complete.", "it": "Analisi completata."}).get(language_key, "Analysis complete.")
    if language_key == "it":
        return (
            f"{base} (Punteggio verita: {truth_score:.0f}/100, "
            f"{claim_count} affermazioni analizzate, {evidence_count} elementi di prova)"
        )
    return (
        f"{base} (Truth score: {truth_score:.0f}/100, "
        f"{claim_count} claims analyzed, {evidence_count} evidence items)"
    )


def _build_why(
    verdict: str,
    truth_score: float,
    supporting: list[dict[str, Any]],
    contradicting: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
    language_key: str,
) -> str:
    """Plain-language explanation of why this verdict was assigned."""
    parts: list[str] = []

    if supporting:
        avg_score = sum(e.get("evidence_score", 0) for e in supporting) / len(supporting)
        if language_key == "it":
            parts.append(
                f"Trovati {len(supporting)} elementi di prova a sostegno "
                f"(punteggio medio: {avg_score:.2f})."
            )
        else:
            parts.append(
                f"{len(supporting)} supporting evidence item(s) found "
                f"(avg score: {avg_score:.2f})."
            )

    if contradicting:
        avg_score = sum(e.get("evidence_score", 0) for e in contradicting) / len(contradicting)
        if language_key == "it":
            parts.append(
                f"Trovati {len(contradicting)} elementi di prova contrari "
                f"(punteggio medio: {avg_score:.2f})."
            )
        else:
            parts.append(
                f"{len(contradicting)} contradicting evidence item(s) found "
                f"(avg score: {avg_score:.2f})."
            )

    if contradictions:
        if language_key == "it":
            parts.append(
                f"Rilevate {len(contradictions)} contraddizioni esplicite tra le fonti."
            )
        else:
            parts.append(
                f"{len(contradictions)} explicit contradiction(s) detected between sources."
            )

    if not supporting and not contradicting:
        if language_key == "it":
            parts.append("Non sono emerse prove forti a sostegno o contro le affermazioni.")
        else:
            parts.append("No strong evidence was found to support or contradict the claims.")

    return " ".join(parts)


def _build_temporal_context(
    scored_evidence: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    language_key: str,
) -> str:
    """Build temporal context note."""
    dated = [e for e in scored_evidence if e.get("published_at")]
    time_claims = [c for c in claims if c.get("time_scope")]

    if time_claims:
        if language_key == "it":
            return (
                f"{len(time_claims)} affermazioni dipendono dal tempo. "
                f"{len(dated)} elementi di prova hanno una data di pubblicazione."
            )
        return (
            f"{len(time_claims)} claim(s) are time-sensitive. "
            f"{len(dated)} evidence item(s) have publication dates."
        )
    return "Non sono emersi vincoli temporali specifici." if language_key == "it" else "No specific temporal constraints detected."


def _build_caveats(
    verdict: str,
    scored_evidence: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    site_forensics: dict[str, Any] | None,
    language_key: str,
) -> list[str]:
    """List remaining uncertainties."""
    caveats: list[str] = []

    if len(scored_evidence) < 3:
        caveats.append(
            "Le prove disponibili sono limitate per questa analisi."
            if language_key == "it"
            else "Limited evidence was available for this analysis."
        )

    if contradictions:
        caveats.append(
            "Alcune fonti si contraddicono: si consiglia un'ulteriore verifica."
            if language_key == "it"
            else "Some sources contradict each other – further investigation recommended."
        )

    uncovered = [
        c for c in claims
        if not any(
            c["id"] in e.get("matched_claim_ids", []) for e in scored_evidence
        )
    ]
    if uncovered:
        if language_key == "it":
            caveats.append(f"{len(uncovered)} affermazioni non hanno trovato prove corrispondenti.")
        else:
            caveats.append(f"{len(uncovered)} claim(s) had no matching evidence.")

    if site_forensics:
        trust = site_forensics.get("site_trust_score", 0.5)
        if trust < 0.4:
            caveats.append(
                "Il sito fonte mostra segnali di scarsa affidabilita: usare cautela."
                if language_key == "it"
                else "The source site has low trust signals – treat with caution."
            )

    return caveats


def _language_key(language: str) -> str:
    """Normalize the requested language to a supported key."""
    return "it" if (language or "").lower().startswith("it") else "en"
