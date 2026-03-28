"""Query builder – constructs search queries from claims."""

from __future__ import annotations

import unicodedata
from typing import Any

_TOPIC_ALIASES = {
    "economy": {"economy", "economia", "finanza", "economico", "economica"},
    "politics": {"politics", "politica", "politico", "istituzioni"},
    "defense": {"defense", "difesa", "sicurezza", "militare"},
    "health": {"health", "salute", "sanita", "sanità", "medicina"},
    "technology": {"technology", "tecnologia", "digitale", "tech"},
}

_TOPIC_HINTS = {
    "economy": {
        "en": ["GDP", "inflation", "employment", "trade balance", "interest rate"],
        "it": ["PIL", "inflazione", "occupazione", "bilancia commerciale", "tasso di interesse", "Banca d'Italia", "ISTAT"],
    },
    "politics": {
        "en": ["parliament", "legislation", "election", "policy"],
        "it": ["parlamento", "legge", "elezioni", "politica", "governo"],
    },
    "defense": {
        "en": ["military", "defense", "security", "NATO"],
        "it": ["difesa", "sicurezza", "forze armate", "NATO", "ministero della difesa"],
    },
    "health": {
        "en": ["health", "medical", "disease", "vaccine", "treatment"],
        "it": ["salute", "medico", "malattia", "vaccino", "trattamento", "ministero della salute", "ISS"],
    },
    "technology": {
        "en": ["technology", "AI", "software", "hardware"],
        "it": ["tecnologia", "IA", "intelligenza artificiale", "software", "hardware", "digitale"],
    },
}

_SOURCE_HINTS = {
    "statistical": {
        "en": ["statistics office", "Eurostat", "central bank"],
        "it": ["ISTAT", "Eurostat", "Banca d'Italia"],
    },
    "regulatory": {
        "en": ["official gazette", "legislation", "parliament", "government"],
        "it": ["Gazzetta Ufficiale", "Normattiva", "Parlamento", "Camera dei deputati", "Senato", "Ministero"],
    },
    "institutional": {
        "en": ["government", "ministry", "parliament", "agency", "official page"],
        "it": ["governo", "ministero", "parlamento", "agenzia", "istituto", "pagina ufficiale"],
    },
    "quote": {
        "en": ["original statement", "transcript"],
        "it": ["dichiarazione ufficiale", "trascrizione", "comunicato"],
    },
    "causal": {
        "en": ["analysis", "data", "report"],
        "it": ["analisi", "dati", "rapporto"],
    },
}

_PRONOUN_STARTERS = {
    "en": {
        "this",
        "that",
        "these",
        "those",
        "it",
        "he",
        "she",
        "they",
        "them",
        "which",
        "who",
        "whom",
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
        "lui",
        "lei",
        "loro",
        "essi",
        "esse",
    },
}


def build_queries(claim: dict[str, Any], topic: str = "", language: str = "en") -> list[str]:
    """Build 1-3 search queries from a claim for use with GDELT / news discovery.

    Expands with entities, dates, numbers, topic-specific hints, and
    bilingual source cues without translating the original claim text.
    """
    text = claim.get("claim", "").strip()
    language_key = _language_key(language)
    topic_key = _canonical_topic(topic)
    claim_type = _normalize_for_match(str(claim.get("type", "")))

    queries: list[str] = []
    if text:
        queries.append(text)

    # Extract key entities / nouns for a focused query
    subject = str(claim.get("resolved_subject") or claim.get("subject") or "").strip()
    obj = str(claim.get("resolved_object") or claim.get("object") or "").strip()
    time_scope = str(claim.get("time_scope", "")).strip()
    context_reference = str(claim.get("context_reference", "")).strip()
    if _is_pronoun_like(subject, language_key):
        subject = ""
    if _is_pronoun_like(obj, language_key):
        obj = ""

    parts: list[str] = []
    if subject:
        parts.append(subject)
    if obj:
        parts.append(obj)
    if time_scope:
        parts.append(time_scope)

    if parts:
        queries.append(" ".join(parts))

    if context_reference and not subject and claim.get("dependency_type") != "standalone":
        queries.append(context_reference)

    # Topic-enriched query
    topic_terms = _topic_terms(topic_key, language_key)
    if topic or topic_terms:
        topic_parts: list[str] = []
        if topic:
            topic_parts.append(topic.strip())
        topic_parts.extend(topic_terms)
        topic_query = _join_unique_terms(topic_parts)
        if topic_query:
            if text:
                queries.append(f"{topic_query} {text[:80]}".strip())
            else:
                queries.append(topic_query)

    # Source-oriented query
    source_terms = _source_terms(claim_type, language_key)
    if source_terms:
        source_parts: list[str] = []
        if subject:
            source_parts.append(subject)
        if time_scope:
            source_parts.append(time_scope)
        if obj:
            source_parts.append(obj)
        if context_reference and not subject:
            source_parts.append(context_reference)
        if topic:
            source_parts.append(topic.strip())
        source_parts.extend(source_terms)
        source_query = _join_unique_terms(source_parts)
        if source_query:
            queries.append(source_query)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        q_norm = q.strip().lower()
        if q_norm and q_norm not in seen:
            seen.add(q_norm)
            unique.append(q.strip())

    return unique[:3]


def _language_key(language: str) -> str:
    """Normalize the input language to an internal key."""
    return "it" if language and language.lower().startswith("it") else "en"


def _canonical_topic(topic: str) -> str:
    """Map English and Italian topic labels to a canonical key."""
    normalized = _normalize_for_match(topic)
    for canonical, aliases in _TOPIC_ALIASES.items():
        if normalized in aliases:
            return canonical
    return normalized


def _topic_terms(topic_key: str, language_key: str) -> list[str]:
    """Return topic search hints for the requested language."""
    return _TOPIC_HINTS.get(topic_key, {}).get(language_key, [])


def _source_terms(claim_type: str, language_key: str) -> list[str]:
    """Return source search hints for the requested claim type."""
    return _SOURCE_HINTS.get(claim_type, {}).get(language_key, [])


def _normalize_for_match(text: str) -> str:
    """Lowercase and remove accents for resilient cue matching."""
    normalized = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.casefold()


def _join_unique_terms(parts: list[str]) -> str:
    """Join terms while removing duplicates and extra whitespace."""
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        cleaned = " ".join(part.split())
        if not cleaned:
            continue
        key = _normalize_for_match(cleaned)
        if key in seen:
            continue
        seen.add(key)
        unique.append(cleaned)
    return " ".join(unique)


def _is_pronoun_like(text: str, language_key: str) -> bool:
    """Detect whether a candidate field is just a pronoun/reference."""
    normalized = _normalize_for_match(text)
    if not normalized:
        return False
    starters = _PRONOUN_STARTERS.get(language_key, _PRONOUN_STARTERS["en"])
    if normalized in starters:
        return True
    tokens = normalized.split()
    return bool(tokens and tokens[0] in starters)
