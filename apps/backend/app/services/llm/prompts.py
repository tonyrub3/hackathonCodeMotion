"""Prompt templates for LLM interactions."""

from __future__ import annotations

CLAIM_DECOMPOSITION_PROMPT = """\
Decompose the following sentence into atomic, independently verifiable claims.
For causal sentences, separate the event, the cause, and the causal link.
Return a JSON array where each item has:
- claim: text of the atomic claim
- type: one of (statistical, event, quote, institutional, regulatory, causal, historical, technical)
- subject: the subject entity
- predicate: the verb/relation
- object: the object/value
- time_scope: relevant time period
- geo_scope: relevant geography
- checkability_score: 0.0-1.0
- dependency_type: "standalone" or parent claim id
- requires_evidence_type: list of evidence types

Sentence: "{sentence}"

JSON:
"""

STANCE_CLASSIFICATION_PROMPT = """\
Given the claim and evidence excerpt below, classify the evidence stance as
exactly one of: supporting, contradicting, neutral.

Claim: {claim}
Evidence: {evidence}

Stance:
"""

JUDGE_SUMMARY_PROMPT = """\
Given the following fact-check analysis, write a brief summary verdict (2-3 sentences).

Verdict: {verdict}
Truth Score: {truth_score}
Claims analyzed: {claim_count}
Sources used: {source_count}
Contradictions found: {contradiction_count}

Summary:
"""
