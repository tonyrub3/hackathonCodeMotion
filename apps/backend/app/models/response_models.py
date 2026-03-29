"""Response models for the Truth Engine API."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any

from app.core.state import PipelineState


class ClaimResponse(BaseModel):
    id: str
    claim: str
    type: str = "event"
    partial_verdict: str = "insufficient_evidence"
    partial_score: float = 0.0
    checkability_score: float = 0.5


class SourceResponse(BaseModel):
    source_id: str
    source_name: str = ""
    source_type: str = "news"
    url: str = ""
    tier: str = "C"
    source_reliability_score: float = 0.5
    dimensions: dict[str, float] = Field(default_factory=dict)


class EvidenceResponse(BaseModel):
    source_id: str
    stance: str = "neutral"
    evidence_score: float = 0.5
    excerpt: str = ""


class ContradictionResponse(BaseModel):
    claim_id: str
    type: str = ""
    description: str = ""
    severity: float = 0.5


class ExplanationResponse(BaseModel):
    summary: str = ""
    why: str = ""
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    source_analysis: list[str] = Field(default_factory=list)
    temporal_context: str = ""
    caveats: list[str] = Field(default_factory=list)


class VerifyResponse(BaseModel):
    """Top-level response returned by POST /api/verify."""

    input_type: str = "text"
    mode: str = "live"
    claims: list[ClaimResponse] = Field(default_factory=list)
    sources_used: list[SourceResponse] = Field(default_factory=list)
    all_sources_found: list[dict[str, Any]] = Field(default_factory=list)
    selected_sources: list[dict[str, Any]] = Field(default_factory=list)
    rejected_sources: list[dict[str, Any]] = Field(default_factory=list)
    source_forensics: list[dict[str, Any]] = Field(default_factory=list)
    claim_scores: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[EvidenceResponse] = Field(default_factory=list)
    contradictions: list[ContradictionResponse] = Field(default_factory=list)
    linguistic_risk: dict[str, Any] = Field(default_factory=dict)
    site_forensics: dict[str, Any] | None = None
    truth_score: float = 0.0
    confidence_score: float = 0.0
    verdict: str = "insufficient_evidence"
    explanation: ExplanationResponse = Field(default_factory=ExplanationResponse)
    layer_outputs: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    timings: dict[str, float] = Field(default_factory=dict)


def build_response_from_state(state: PipelineState) -> VerifyResponse:
    """Convert the internal PipelineState into the public API response."""
    claims = [
        ClaimResponse(
            id=c.get("id", ""),
            claim=c.get("claim", ""),
            type=c.get("type", "event"),
            partial_verdict=c.get("partial_verdict", "insufficient_evidence"),
            partial_score=c.get("partial_score", 0.0),
            checkability_score=c.get("checkability_score", 0.5),
        )
        for c in state.claims
    ]

    sources = [
        SourceResponse(
            source_id=s.get("source_id", ""),
            source_name=s.get("source_name", ""),
            source_type=s.get("source_type", "news"),
            url=s.get("url", ""),
            tier=s.get("tier", "C"),
            source_reliability_score=s.get("source_reliability_score", 0.5),
            dimensions=s.get("dimensions", {}),
        )
        for s in state.sources_used
    ]

    evidence = [
        EvidenceResponse(
            source_id=e.get("source_id", ""),
            stance=e.get("stance", "neutral"),
            evidence_score=e.get("evidence_score", 0.5),
            excerpt=e.get("excerpt", ""),
        )
        for e in state.scored_evidence
    ]

    contradictions = [
        ContradictionResponse(
            claim_id=c.get("claim_id", ""),
            type=c.get("type", ""),
            description=c.get("description", ""),
            severity=c.get("severity", 0.5),
        )
        for c in state.contradictions
    ]

    explanation = ExplanationResponse(**state.explanation) if state.explanation else ExplanationResponse()

    return VerifyResponse(
        input_type=state.input_type,
        mode=state.mode,
        claims=claims,
        sources_used=sources,
        all_sources_found=state.all_sources_found,
        selected_sources=state.selected_sources,
        rejected_sources=state.rejected_sources,
        source_forensics=state.source_forensics,
        claim_scores=state.claim_scores,
        evidence=evidence,
        contradictions=contradictions,
        linguistic_risk=state.linguistic_risk,
        site_forensics=state.site_forensics,
        truth_score=state.truth_score,
        confidence_score=state.confidence_score,
        verdict=state.verdict,
        explanation=explanation,
        layer_outputs=state.layer_outputs,
        errors=state.errors,
        timings=state.timings,
    )
