"""
Agent 2 – Claim Decomposition.

Responsibilities:
  - Split text into atomic, independently verifiable claims
  - Classify claim types
  - Handle causal claims specially (split into event + cause + causal link)
  - Assign checkability scores

Tools used:
  - sentence_splitter  (services.parsing.sentence_splitter)
  - entity_extractor   (lightweight NER)
  - date_number_extractor
  - causal_cue_detector
  - semantic_claim_decomposer  (Regolo / LLM for complex sentences)
  - claim_deduplicator
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from app.config import Settings
from app.core.state import PipelineState
from app.services.parsing.sentence_splitter import split_sentences
from app.services.llm.regolo_client import RegoloClient

logger = logging.getLogger(__name__)

# Causal cue patterns
CAUSAL_CUES = re.compile(
    r"\b(because|due to|caused by|as a result of|therefore|consequently|"
    r"despite|although|led to|resulting in|owing to)\b",
    re.IGNORECASE,
)

# Simple NER-like patterns for lightweight extraction
DATE_PATTERN = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4})\b")
NUMBER_PATTERN = re.compile(r"\b\d+[.,]?\d*\s*(%|percent|million|billion|thousand|euro|EUR|USD|\$|€)?\b")


class ClaimDecompositionAgent:
    """Decompose text into structured atomic claims."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = RegoloClient(settings)

    async def run(self, state: PipelineState) -> PipelineState:
        """
        Input contract:  state.normalized_text
        Output contract: state.claims (list of claim dicts)
        """
        text = state.normalized_text
        if not text:
            return state

        sentences = split_sentences(text)
        claims: list[dict[str, Any]] = []
        claim_counter = 0

        for idx, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue

            is_causal = bool(CAUSAL_CUES.search(sentence))
            is_complex = len(sentence.split()) > 25 or sentence.count(",") >= 2

            if is_complex or is_causal:
                decomposed = await self._semantic_decompose(sentence, idx)
                for sub in decomposed:
                    claim_counter += 1
                    sub["id"] = f"c{claim_counter}"
                    sub["original_sentence_index"] = idx
                    claims.append(sub)
            else:
                claim_counter += 1
                claims.append(self._make_simple_claim(sentence, claim_counter, idx))

        # Deduplicate
        claims = self._deduplicate(claims)

        # Cap
        claims = claims[: self.settings.max_claims_per_request]
        state.claims = claims
        return state

    def _make_simple_claim(self, sentence: str, num: int, idx: int) -> dict[str, Any]:
        """Build a claim dict from a simple sentence using lightweight heuristics."""
        claim_type = self._classify_type(sentence)
        dates = DATE_PATTERN.findall(sentence)
        numbers = NUMBER_PATTERN.findall(sentence)

        return {
            "id": f"c{num}",
            "claim": sentence,
            "type": claim_type,
            "subject": "",
            "predicate": "",
            "object": "",
            "time_scope": dates[0] if dates else "",
            "geo_scope": "",
            "checkability_score": self._estimate_checkability(sentence, claim_type),
            "dependency_type": "standalone",
            "requires_evidence_type": self._evidence_type_hints(claim_type),
            "original_sentence_index": idx,
        }

    async def _semantic_decompose(self, sentence: str, idx: int) -> list[dict[str, Any]]:
        """Use LLM to decompose a complex or causal sentence into atomic claims."""
        prompt = (
            "Decompose the following sentence into atomic, independently verifiable claims. "
            "For causal sentences, separate the event, the cause, and the causal link. "
            "Return a JSON array where each item has: claim, type "
            "(statistical|event|quote|institutional|regulatory|causal|historical|technical), "
            "subject, predicate, object, time_scope, geo_scope, checkability_score (0-1), "
            "dependency_type (standalone or parent claim id), requires_evidence_type (list).\n\n"
            f"Sentence: \"{sentence}\"\n\nJSON:"
        )
        try:
            result = await self.llm.complete_json(prompt)
            if isinstance(result, list):
                return result
        except Exception as exc:
            logger.warning("LLM decomposition failed, falling back to simple: %s", exc)

        # Fallback: treat as single claim
        return [self._make_simple_claim(sentence, 0, idx)]

    def _classify_type(self, sentence: str) -> str:
        """Lightweight claim-type classification from surface patterns."""
        s = sentence.lower()
        if any(kw in s for kw in ["%", "percent", "million", "billion", "growth", "rate", "gdp"]):
            return "statistical"
        if any(kw in s for kw in ["said", "stated", "declared", "announced", "according to"]):
            return "quote"
        if any(kw in s for kw in ["law", "regulation", "directive", "decree", "act"]):
            return "regulatory"
        if any(kw in s for kw in ["ministry", "government", "parliament", "commission", "agency"]):
            return "institutional"
        if CAUSAL_CUES.search(sentence):
            return "causal"
        return "event"

    def _estimate_checkability(self, sentence: str, claim_type: str) -> float:
        """Heuristic checkability score."""
        score = 0.5
        if DATE_PATTERN.search(sentence):
            score += 0.15
        if NUMBER_PATTERN.search(sentence):
            score += 0.15
        if claim_type in ("statistical", "regulatory", "institutional"):
            score += 0.1
        if claim_type == "causal":
            score -= 0.2
        return max(0.0, min(1.0, score))

    def _evidence_type_hints(self, claim_type: str) -> list[str]:
        """Suggest what kind of evidence would be most useful."""
        mapping = {
            "statistical": ["official_statistics", "reports"],
            "event": ["news_coverage", "official_statements"],
            "quote": ["original_source", "transcript"],
            "institutional": ["official_documents", "government_pages"],
            "regulatory": ["legal_databases", "official_gazettes"],
            "causal": ["analysis", "expert_commentary", "data"],
            "historical": ["archives", "encyclopedias"],
            "technical": ["technical_papers", "official_specs"],
        }
        return mapping.get(claim_type, ["general"])

    def _deduplicate(self, claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove near-duplicate claims using simple text hashing."""
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for c in claims:
            # Normalize for dedup
            key = hashlib.md5(c["claim"].lower().strip().encode()).hexdigest()
            if key not in seen:
                seen.add(key)
                unique.append(c)
        return unique
