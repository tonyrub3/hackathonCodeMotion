"""Prompt templates for LLM interactions."""

from __future__ import annotations

CLAIM_DECOMPOSITION_PROMPT = """\
Decompose the following sentence into atomic, independently verifiable claims.
The sentence may be in English or Italian. Do not translate it; keep the claim text in the original language.
If a context note is provided, use it to resolve pronouns and implicit references when possible.
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
- resolved_subject: optional resolved subject when the original sentence uses a pronoun
- context_reference: optional short note about the antecedent used for resolution

Context: {context}
Sentence: "{sentence}"

JSON:
"""

STANCE_CLASSIFICATION_PROMPT = """\
Given the claim and evidence excerpt below, classify the evidence stance as
exactly one of: supporting, contradicting, neutral.
The claim and evidence may be in English or Italian. Do not translate them.

Claim: {claim}
Evidence: {evidence}

Stance:
"""

JUDGE_SUMMARY_PROMPT = """\
Given the following fact-check analysis, write a brief summary verdict (2-3 sentences).
The analysis may be in English or Italian. Keep the same language and do not translate named entities.

Verdict: {verdict}
Truth Score: {truth_score}
Claims analyzed: {claim_count}
Sources used: {source_count}
Contradictions found: {contradiction_count}

Summary:
"""
