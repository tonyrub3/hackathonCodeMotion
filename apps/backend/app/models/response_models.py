"""Response models for the Truth Engine API."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any

from app.core.state import PipelineState
from app.services.retrieval.domain_policy import TRUSTED_DOMAINS


class ClaimResponse(BaseModel):
    id: str
    claim: str
    search_query: str = ""
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
    source_url: str = ""
    article_title: str = ""
    article_author: str = ""
    article_date: str = ""
    cited_links: list[str] = Field(default_factory=list)
    trusted_domains: dict[str, list[str]] = Field(default_factory=dict)
    claims: list[ClaimResponse] = Field(default_factory=list)
    generated_queries: list[str] = Field(default_factory=list)
    sources_used: list[SourceResponse] = Field(default_factory=list)
    all_tavily_results: list[dict[str, Any]] = Field(default_factory=list)
    tavily_answer_hints: list[dict[str, Any]] = Field(default_factory=list)
    tavily_search_profile: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceResponse] = Field(default_factory=list)
    contradictions: list[ContradictionResponse] = Field(default_factory=list)
    linguistic_risk: dict[str, Any] = Field(default_factory=dict)
    site_forensics: dict[str, Any] | None = None
    truth_score: float = 0.0
    confidence_score: float = 0.0
    verdict: str = "insufficient_evidence"
    explanation: ExplanationResponse = Field(default_factory=ExplanationResponse)
    errors: list[str] = Field(default_factory=list)
    timings: dict[str, float] = Field(default_factory=dict)


def build_response_from_state(state: PipelineState) -> VerifyResponse:
    """Convert the internal PipelineState into the public API response."""
    claims = [
        ClaimResponse(
            id=c.get("id", ""),
            claim=c.get("claim", ""),
            search_query=c.get("search_query", ""),
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
        source_url=state.source_url,
        article_title=state.article_title,
        article_author=state.article_author,
        article_date=state.article_date,
        cited_links=state.cited_links,
        trusted_domains=TRUSTED_DOMAINS,
        claims=claims,
        generated_queries=state.generated_queries,
        sources_used=sources,
        all_tavily_results=state.all_tavily_results,
        tavily_answer_hints=state.tavily_answer_hints,
        tavily_search_profile=state.tavily_search_profile,
        evidence=evidence,
        contradictions=contradictions,
        linguistic_risk=state.linguistic_risk,
        site_forensics=state.site_forensics,
        truth_score=state.truth_score,
        confidence_score=state.confidence_score,
        verdict=state.verdict,
        explanation=explanation,
        errors=state.errors,
        timings=state.timings,
    )
