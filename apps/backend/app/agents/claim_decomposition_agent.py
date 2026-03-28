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
import unicodedata
from typing import Any

from app.config import Settings
from app.core.state import PipelineState
from app.services.llm.prompts import CLAIM_DECOMPOSITION_PROMPT
from app.services.parsing.sentence_splitter import split_sentences
from app.services.llm.regolo_client import RegoloClient

logger = logging.getLogger(__name__)

# Surface cues in English and Italian.
CAUSAL_HINTS = [
    "because",
    "due to",
    "caused by",
    "as a result of",
    "therefore",
    "consequently",
    "despite",
    "although",
    "led to",
    "resulting in",
    "owing to",
    "perche",
    "poiche",
    "dato che",
    "visto che",
    "a causa di",
    "grazie a",
    "di conseguenza",
    "quindi",
    "pertanto",
    "percio",
    "ha portato a",
    "ha causato",
    "ha provocato",
    "nonostante",
    "sebbene",
    "malgrado",
    "tuttavia",
    "siccome",
]

STATISTICAL_HINTS = [
    "%",
    "percent",
    "percento",
    "per cento",
    "million",
    "millions",
    "billion",
    "billions",
    "growth",
    "rate",
    "gdp",
    "pil",
    "inflazione",
    "crescita",
    "tasso",
    "indice",
    "variazione",
    "disoccupazione",
]

QUOTE_HINTS = [
    "said",
    "stated",
    "declared",
    "according to",
    "ha detto",
    "ha affermato",
    "ha dichiarato",
    "secondo",
]

REGULATORY_HINTS = [
    "law",
    "regulation",
    "directive",
    "decree",
    "act",
    "legge",
    "regolamento",
    "direttiva",
    "decreto",
    "ordinanza",
    "norma",
]

DEMONSTRATIVE_STARTERS = {
    "en": {
        "this",
        "that",
        "these",
        "those",
        "it",
        "which",
        "who",
        "whom",
        "the latter",
        "the former",
    },
    "it": {
        "questo",
        "questa",
        "questi",
        "queste",
        "quello",
        "quella",
        "quelli",
        "quelle",
        "cio",
        "ciò",
        "tale",
        "tali",
    },
}

PERSONAL_STARTERS = {
    "en": {"he", "she", "they", "them", "him", "her", "we", "us", "you"},
    "it": {"lui", "lei", "loro", "essi", "esse", "ci", "vi"},
}

CLAUSE_MARKERS = {
    "en": [
        "has led to",
        "have led to",
        "led to",
        "has caused",
        "have caused",
        "caused",
        "because",
        "due to",
        "according to",
        "said",
        "stated",
        "declared",
        "announced",
        "approved",
        "confirmed",
        "reported",
        "is",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
        "will",
        "would",
        "could",
        "should",
        "might",
    ],
    "it": [
        "ha portato a",
        "hanno portato a",
        "ha causato",
        "hanno causato",
        "ha provocato",
        "hanno provocato",
        "a causa di",
        "perche",
        "perché",
        "poiche",
        "poiché",
        "siccome",
        "secondo",
        "ha detto",
        "hanno detto",
        "ha dichiarato",
        "hanno dichiarato",
        "ha affermato",
        "hanno affermato",
        "ha annunciato",
        "hanno annunciato",
        "ha approvato",
        "hanno approvato",
        "ha confermato",
        "hanno confermato",
        "ha riferito",
        "hanno riferito",
        "era",
        "erano",
        "sono",
        "ha",
        "hanno",
        "sara",
        "sarà",
        "saranno",
    ],
}

INSTITUTIONAL_HINTS = [
    "ministry",
    "government",
    "parliament",
    "commission",
    "agency",
    "ministero",
    "governo",
    "parlamento",
    "commissione",
    "agenzia",
    "autorita",
    "regione",
    "comune",
]

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
            logger.warning("    no text to decompose")
            return state

        sentences = split_sentences(text)
        language = (state.language or "en").lower()
        logger.info("    sentences found: %d", len(sentences))
        claims: list[dict[str, Any]] = []
        claim_counter = 0
        context_state = self._empty_context_state()

        for idx, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue

            normalized_sentence = _normalize_for_match(sentence)
            is_causal = _contains_any(normalized_sentence, CAUSAL_HINTS)
            is_complex = len(sentence.split()) > 25 or sentence.count(",") >= 2
            context_note = self._build_context_note(context_state)

            if is_complex or is_causal:
                logger.info("    [S%d] COMPLEX/CAUSAL -> LLM decomposition: %.80s", idx, sentence)
                decomposed = await self._semantic_decompose(sentence, idx, language, context_note, context_state)
                logger.info("    [S%d] LLM returned %d sub-claims", idx, len(decomposed))
                sentence_claims = [
                    self._normalize_decomposed_claim(sub, sentence, idx, language, context_state)
                    for sub in decomposed
                ]
            else:
                logger.info("    [S%d] SIMPLE -> heuristic: %.80s", idx, sentence)
                sentence_claims = [
                    self._make_simple_claim(sentence, idx, language, context_state)
                ]

            for claim in sentence_claims:
                claim_counter += 1
                claim["id"] = f"c{claim_counter}"
                claim["original_sentence_index"] = idx
                claim = self._resolve_coreference(claim, sentence, context_state, language)
                claims.append(claim)
                context_state = self._update_context_state(context_state, claim)

        # Deduplicate
        before_dedup = len(claims)
        claims = self._deduplicate(claims)
        if before_dedup != len(claims):
            logger.info("    dedup: %d -> %d claims", before_dedup, len(claims))

        # Cap
        claims = claims[: self.settings.max_claims_per_request]
        state.claims = claims

        for c in claims:
            logger.info("    CLAIM [%s] type=%s checkability=%.2f: %s",
                         c["id"], c["type"], c.get("checkability_score", 0), c["claim"][:80])
        return state

    def _make_simple_claim(
        self,
        sentence: str,
        idx: int,
        language: str,
        context_state: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Build a claim dict from a simple sentence using lightweight heuristics."""
        claim_type = self._classify_type(sentence)
        subject, predicate, obj = self._extract_clause_parts(sentence, language)
        dates = DATE_PATTERN.findall(sentence)
        claim: dict[str, Any] = {
            "claim": sentence,
            "type": claim_type,
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "time_scope": dates[0] if dates else "",
            "geo_scope": "",
            "checkability_score": self._estimate_checkability(sentence, claim_type),
            "dependency_type": "standalone",
            "requires_evidence_type": self._evidence_type_hints(claim_type),
        }
        if subject and self._is_pronoun_like(subject, language):
            claim["original_subject"] = subject
            claim["subject"] = ""
        if context_state:
            claim = self._resolve_coreference(claim, sentence, context_state, language)
        return claim

    async def _semantic_decompose(
        self,
        sentence: str,
        idx: int,
        language: str = "en",
        context_note: str = "",
        context_state: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Use LLM to decompose a complex or causal sentence into atomic claims."""
        prompt = CLAIM_DECOMPOSITION_PROMPT.format(
            sentence=sentence,
            context=context_note or "None",
        )
        try:
            result = await self.llm.complete_json(prompt)
            if isinstance(result, list) and result:
                return result
        except Exception as exc:
            logger.warning("LLM decomposition failed, falling back to simple: %s", exc)

        # Fallback: treat as single claim
        return [self._make_simple_claim(sentence, idx, language, context_state)]

    def _classify_type(self, sentence: str) -> str:
        """Lightweight claim-type classification from surface patterns."""
        s = _normalize_for_match(sentence)
        if _contains_any(s, STATISTICAL_HINTS):
            return "statistical"
        if _contains_any(s, CAUSAL_HINTS):
            return "causal"
        if _contains_any(s, REGULATORY_HINTS):
            return "regulatory"
        if _contains_any(s, INSTITUTIONAL_HINTS):
            return "institutional"
        if _contains_any(s, QUOTE_HINTS):
            return "quote"
        return "event"

    def _normalize_decomposed_claim(
        self,
        raw_claim: dict[str, Any],
        sentence: str,
        idx: int,
        language: str,
        context_state: dict[str, str],
    ) -> dict[str, Any]:
        """Normalize an LLM-produced claim dict and fill missing structure."""
        claim_text = str(raw_claim.get("claim") or sentence).strip()
        claim_type = str(raw_claim.get("type") or self._classify_type(claim_text)).strip().lower()
        if claim_type not in {
            "statistical",
            "event",
            "quote",
            "institutional",
            "regulatory",
            "causal",
            "historical",
            "technical",
        }:
            claim_type = self._classify_type(claim_text)

        subject = str(raw_claim.get("subject", "")).strip()
        predicate = str(raw_claim.get("predicate", "")).strip()
        obj = str(raw_claim.get("object", "")).strip()
        time_scope = str(raw_claim.get("time_scope", "")).strip()
        geo_scope = str(raw_claim.get("geo_scope", "")).strip()
        dependency_type = str(raw_claim.get("dependency_type", "standalone")).strip() or "standalone"
        requires_evidence_type = raw_claim.get("requires_evidence_type")
        if not isinstance(requires_evidence_type, list) or not requires_evidence_type:
            requires_evidence_type = self._evidence_type_hints(claim_type)

        checkability = raw_claim.get("checkability_score")
        try:
            checkability_score = float(checkability)
        except (TypeError, ValueError):
            checkability_score = self._estimate_checkability(claim_text, claim_type)

        normalized: dict[str, Any] = {
            "claim": claim_text,
            "type": claim_type,
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "time_scope": time_scope or (DATE_PATTERN.findall(claim_text)[0] if DATE_PATTERN.findall(claim_text) else ""),
            "geo_scope": geo_scope,
            "checkability_score": max(0.0, min(1.0, checkability_score)),
            "dependency_type": "standalone" if dependency_type != "standalone" else dependency_type,
            "requires_evidence_type": requires_evidence_type,
        }
        if dependency_type != "standalone":
            normalized["model_dependency_type"] = dependency_type

        if subject and self._is_pronoun_like(subject, language):
            normalized["original_subject"] = subject
            normalized["subject"] = ""

        if raw_claim.get("resolved_subject"):
            normalized["resolved_subject"] = str(raw_claim.get("resolved_subject", "")).strip()
        if raw_claim.get("context_reference"):
            normalized["context_reference"] = str(raw_claim.get("context_reference", "")).strip()
        if raw_claim.get("model_dependency_type"):
            normalized["model_dependency_type"] = str(raw_claim.get("model_dependency_type", "")).strip()
        if raw_claim.get("original_subject") and not normalized.get("original_subject"):
            normalized["original_subject"] = str(raw_claim.get("original_subject", "")).strip()

        return self._resolve_coreference(normalized, sentence, context_state, language)

    def _resolve_coreference(
        self,
        claim: dict[str, Any],
        sentence: str,
        context_state: dict[str, str],
        language: str,
    ) -> dict[str, Any]:
        """Resolve obvious pronoun references using the previous claim context."""
        if not context_state:
            return claim

        sentence_norm = _normalize_for_match(sentence)
        subject = str(claim.get("subject", "")).strip()
        original_subject = str(claim.get("original_subject", "")).strip()
        subject_norm = _normalize_for_match(subject or original_subject)

        if subject and not self._is_pronoun_like(subject, language):
            return claim
        if not self._sentence_starts_with_reference(sentence_norm, language):
            return claim

        anchor, anchor_source = self._choose_reference_anchor(context_state, language, sentence_norm)
        if not anchor:
            return claim

        if subject:
            claim.setdefault("original_subject", subject)
        elif original_subject:
            claim.setdefault("original_subject", original_subject)

        claim["resolved_subject"] = anchor
        if not subject or self._is_pronoun_like(subject_norm or subject, language):
            claim["subject"] = anchor
        if not claim.get("context_reference"):
            claim["context_reference"] = context_state.get("last_claim_text", "")
        if claim.get("dependency_type", "standalone") == "standalone" and context_state.get("last_claim_id"):
            claim["dependency_type"] = context_state["last_claim_id"]
        claim["coreference_resolved"] = True
        claim["coreference_source"] = anchor_source
        return claim

    def _choose_reference_anchor(
        self,
        context_state: dict[str, str],
        language: str,
        sentence_norm: str,
    ) -> tuple[str, str]:
        """Pick the most plausible antecedent for a pronoun-starting sentence."""
        demonstrative = self._sentence_starts_with_demonstrative(sentence_norm, language)
        if demonstrative:
            for key, source in (
                ("last_object", "previous_object"),
                ("last_anchor", "previous_anchor"),
                ("last_subject", "previous_subject"),
                ("last_claim_text", "previous_claim"),
            ):
                value = context_state.get(key, "").strip()
                if value:
                    return value, source
        else:
            for key, source in (
                ("last_subject", "previous_subject"),
                ("last_anchor", "previous_anchor"),
                ("last_claim_text", "previous_claim"),
                ("last_object", "previous_object"),
            ):
                value = context_state.get(key, "").strip()
                if value:
                    return value, source
        return "", ""

    def _update_context_state(
        self,
        context_state: dict[str, str],
        claim: dict[str, Any],
    ) -> dict[str, str]:
        """Update context memory after a claim has been created."""
        next_state = dict(context_state)
        subject = str(claim.get("subject", "")).strip()
        object_ = str(claim.get("object", "")).strip()
        resolved_subject = str(claim.get("resolved_subject", "")).strip()
        resolved_object = str(claim.get("resolved_object", "")).strip()
        claim_text = str(claim.get("claim", "")).strip()

        anchor = resolved_subject or subject or resolved_object or object_ or claim_text
        if subject and not self._is_pronoun_like_any_language(subject):
            next_state["last_subject"] = subject
        elif resolved_subject:
            next_state["last_subject"] = resolved_subject

        if object_:
            next_state["last_object"] = object_
        elif resolved_object:
            next_state["last_object"] = resolved_object

        if anchor:
            next_state["last_anchor"] = anchor
        if claim_text:
            next_state["last_claim_text"] = claim_text
        if claim.get("id"):
            next_state["last_claim_id"] = str(claim.get("id"))
        return next_state

    def _empty_context_state(self) -> dict[str, str]:
        """Initialize the memory used for pronoun/coreference resolution."""
        return {
            "last_subject": "",
            "last_object": "",
            "last_anchor": "",
            "last_claim_text": "",
            "last_claim_id": "",
        }

    def _build_context_note(self, context_state: dict[str, str]) -> str:
        """Render the previous claim context for the LLM prompt."""
        pieces: list[str] = []
        subject = context_state.get("last_subject", "").strip()
        obj = context_state.get("last_object", "").strip()
        claim_text = context_state.get("last_claim_text", "").strip()
        if subject:
            pieces.append(f"Previous subject: {subject}")
        if obj:
            pieces.append(f"Previous object: {obj}")
        if claim_text:
            pieces.append(f"Previous claim: {claim_text}")
        return " | ".join(pieces[-3:])

    def _sentence_starts_with_reference(self, sentence_norm: str, language: str) -> bool:
        """Return True if the sentence begins with a reference-like starter."""
        return (
            self._sentence_starts_with_demonstrative(sentence_norm, language)
            or any(sentence_norm.startswith(starter) for starter in self._starter_tokens(language))
        )

    def _sentence_starts_with_demonstrative(self, sentence_norm: str, language: str) -> bool:
        """Detect demonstrative references that often point back to prior claims."""
        return any(sentence_norm.startswith(starter) for starter in self._starter_tokens(language, demonstrative=True))

    def _starter_tokens(self, language: str, demonstrative: bool = False) -> list[str]:
        """Return normalized pronoun starters for the requested language."""
        key = "it" if (language or "").lower().startswith("it") else "en"
        starters = DEMONSTRATIVE_STARTERS[key] if demonstrative else PERSONAL_STARTERS[key]
        return sorted((_normalize_for_match(token) for token in starters), key=len, reverse=True)

    def _is_pronoun_like(self, text: str, language: str) -> bool:
        """Check whether a subject string is just a pronoun or reference marker."""
        if not text:
            return False
        normalized = _normalize_for_match(text)
        tokens = normalized.split()
        if not tokens:
            return False
        starter_pool = set(self._starter_tokens(language, demonstrative=True)) | set(self._starter_tokens(language))
        if normalized in starter_pool:
            return True
        first_two = " ".join(tokens[:2])
        return first_two in starter_pool or tokens[0] in starter_pool

    def _is_pronoun_like_any_language(self, text: str) -> bool:
        """Detect pronoun-like subjects in either supported language."""
        return self._is_pronoun_like(text, "en") or self._is_pronoun_like(text, "it")

    def _extract_clause_parts(self, sentence: str, language: str) -> tuple[str, str, str]:
        """Roughly split a sentence into subject, predicate, and object."""
        marker = self._find_first_clause_marker(sentence, language)
        if not marker:
            return "", "", ""

        start, end, phrase = marker
        subject = sentence[:start].strip(" ,;:-")
        tail = sentence[end:].strip(" ,;:-")
        predicate = phrase
        obj = tail
        return subject, predicate, obj

    def _find_first_clause_marker(self, sentence: str, language: str) -> tuple[int, int, str] | None:
        """Find the first clause marker span in the sentence."""
        markers = sorted(CLAUSE_MARKERS["it" if (language or "").lower().startswith("it") else "en"], key=len, reverse=True)
        normalized_sentence = _normalize_for_match(sentence)
        best: tuple[int, int, str] | None = None
        for marker in markers:
            marker_norm = _normalize_for_match(marker)
            if len(marker_norm) < 2:
                continue
            match = re.search(rf"(?<![\w]){re.escape(marker_norm)}(?![\w])", normalized_sentence)
            if not match:
                continue
            candidate = (match.start(), match.end(), marker)
            if best is None or candidate[0] < best[0]:
                best = candidate
        return best

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


def _normalize_for_match(text: str) -> str:
    """Lowercase and strip accents so Italian and English cues both match."""
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.casefold()


def _contains_any(text: str, phrases: list[str]) -> bool:
    """Return True when any cue phrase appears in the normalized text."""
    return any(phrase in text for phrase in phrases)
