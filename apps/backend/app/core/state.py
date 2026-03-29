"""
Pipeline state – mutable data container passed through all agents.

Each agent reads what it needs and writes its outputs into the state.
This keeps the pipeline linear and debuggable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class PipelineState:
    """Mutable state that flows through the verification pipeline."""

    # --- Input ---
    request_id: str = ""
    input_type: str = "text"  # "text" | "url"
    raw_content: str = ""
    language: str = "auto"
    country: str = ""
    topic: str = ""
    mode: str = "live"  # "live" | "benchmark"

    # --- After Input Normalizer ---
    normalized_text: str = ""
    article_title: str = ""
    article_author: str = ""
    article_date: str = ""
    article_metadata: dict[str, Any] = field(default_factory=dict)
    source_url: str = ""
    cited_links: list[str] = field(default_factory=list)

    # --- After Claim Decomposition ---
    claims: list[dict[str, Any]] = field(default_factory=list)
    query_plan: list[dict[str, Any]] = field(default_factory=list)

    # --- After Source Discovery ---
    evidence_items: list[dict[str, Any]] = field(default_factory=list)
    sources_used: list[dict[str, Any]] = field(default_factory=list)
    all_sources_found: list[dict[str, Any]] = field(default_factory=list)
    selected_sources: list[dict[str, Any]] = field(default_factory=list)
    rejected_sources: list[dict[str, Any]] = field(default_factory=list)
    source_forensics: list[dict[str, Any]] = field(default_factory=list)
    claim_scores: list[dict[str, Any]] = field(default_factory=list)
    layer_outputs: dict[str, Any] = field(default_factory=dict)

    # --- After Evidence Analysis ---
    scored_evidence: list[dict[str, Any]] = field(default_factory=list)
    contradictions: list[dict[str, Any]] = field(default_factory=list)
    consensus_signals: dict[str, Any] = field(default_factory=dict)

    # --- After Site Forensics (URL only) ---
    site_forensics: dict[str, Any] | None = None

    # --- After Judge ---
    truth_score: float = 0.0
    confidence_score: float = 0.0
    verdict: str = "insufficient_evidence"
    partial_verdicts: list[dict[str, Any]] = field(default_factory=list)
    explanation: dict[str, Any] = field(default_factory=dict)
    linguistic_risk: dict[str, Any] = field(default_factory=dict)

    # --- Metadata ---
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    errors: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
