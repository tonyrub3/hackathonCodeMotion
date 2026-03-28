"""
Official source discovery – heuristic-based discovery of primary/official sources.

Uses patterns from discovery_policies to identify likely official sources
from claim entities, NOT a static whitelist of approved domains.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

# Load official patterns at import time
_PATTERNS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "..", "data", "discovery_policies", "official_patterns.json"
)
_OFFICIAL_PATTERNS: dict[str, Any] = {}
try:
    with open(_PATTERNS_PATH) as f:
        _OFFICIAL_PATTERNS = json.load(f)
except FileNotFoundError:
    logger.info("official_patterns.json not found – official source discovery will use built-in defaults")


# Built-in fallback patterns
_DEFAULT_TLD_PATTERNS = [".gov", ".gov.*", ".europa.eu", ".mil", ".edu", ".int"]
_DEFAULT_PATH_PATTERNS = [
    "/investors", "/investor-relations", "/press", "/media",
    "/newsroom", "/press-releases", "/official-statements",
]
_DEFAULT_INSTITUTION_PATTERNS = [
    "ministry", "ministero", "regulator", "authority", "commission",
    "parliament", "government", "agency", "institute", "istituto",
]
_DEFAULT_STATISTICAL_HINTS = ["istat", "eurostat", "statistics", "statistical", "census"]
_DEFAULT_CENTRAL_BANK_HINTS = ["ecb", "european central bank", "bancaditalia", "bank of italy"]


async def discover_official_sources(
    claim: dict[str, Any],
    topic: str = "",
    language: str = "en",
) -> list[dict[str, Any]]:
    """Discover likely official sources from claim entities and type.

    This is a heuristic-based stub. In production, it would query search
    engines or domain indexes to find real URLs matching the patterns.

    The MVP keeps the original claim text unchanged and adds bilingual
    source cues for English and Italian inputs.

    Returns evidence-like dicts.
    """
    results: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    claim_type = str(claim.get("type", "")).strip().lower()
    subject = str(claim.get("subject", "")).strip()
    claim_text = str(claim.get("claim", "")).strip()
    language_key = "it" if (language or "").lower().startswith("it") else "en"
    normalized = _normalize_for_match(" ".join(part for part in [subject, claim_text, topic] if part))

    institution_patterns = _OFFICIAL_PATTERNS.get("institution_patterns", _DEFAULT_INSTITUTION_PATTERNS)
    statistical_hints = _OFFICIAL_PATTERNS.get("statistical_office_hints", _DEFAULT_STATISTICAL_HINTS)
    central_bank_hints = _OFFICIAL_PATTERNS.get("central_bank_hints", _DEFAULT_CENTRAL_BANK_HINTS)

    # For statistical claims, suggest statistics office sources
    if claim_type == "statistical" or _contains_any(normalized, statistical_hints):
        _add_source(
            results,
            seen_names,
            _statistical_source_name(language_key),
            relevance=0.9,
            note=f"Expected official statistics source for: {subject or claim_text[:60]}",
        )
        _add_source(
            results,
            seen_names,
            "Eurostat",
            relevance=0.82,
            note=f"European statistical source relevant to: {subject or claim_text[:60]}",
        )
        if _topic_is_economy(topic, normalized) or _contains_any(normalized, central_bank_hints):
            _add_source(
                results,
                seen_names,
                _central_bank_source_name(language_key),
                relevance=0.84,
                note=f"Central bank / monetary authority source relevant to: {subject or claim_text[:60]}",
            )

    # For regulatory claims, suggest legal/regulatory sources
    if claim_type == "regulatory" or _contains_any(normalized, ["legge", "regolamento", "direttiva", "decreto", "normativa", "law", "regulation", "directive", "decree"]):
        _add_source(
            results,
            seen_names,
            _regulatory_source_name(language_key),
            relevance=0.86,
            note=f"Expected regulatory source for: {subject or claim_text[:60]}",
        )
        if language_key == "it" or _contains_any(normalized, ["gazzetta ufficiale", "normattiva", "parlamento", "camera dei deputati", "senato"]):
            _add_source(
                results,
                seen_names,
                "Parlamento italiano / legislative records",
                relevance=0.78,
                note=f"Legislative reference relevant to: {subject or claim_text[:60]}",
            )

    # For institutional claims, suggest government/institutional pages
    if claim_type == "institutional" or _contains_any(normalized, institution_patterns):
        _add_source(
            results,
            seen_names,
            _institutional_source_name(language_key),
            relevance=0.8,
            note=f"Expected official page for: {subject or claim_text[:60]}",
        )
        if _contains_any(normalized, ["ministero", "governo", "government", "parliament", "parlamento", "agency", "agenzia", "istituto"]):
            _add_source(
                results,
                seen_names,
                _government_body_source_name(language_key),
                relevance=0.76,
                note=f"Institutional source relevant to: {subject or claim_text[:60]}",
            )

    # TODO: In production, use a search engine API or domain index
    # to actually resolve these patterns to real URLs.
    # For now, these serve as discovery hints that downstream processing
    # can attempt to resolve.

    return results


def _make_placeholder_source(
    name: str,
    source_type: str = "official",
    tier: str = "A",
    relevance: float = 0.7,
    note: str = "",
) -> dict[str, Any]:
    """Create a placeholder evidence entry for a discovered source type."""
    source_id = hashlib.md5(name.encode()).hexdigest()[:12]
    return {
        "source_id": f"off_{source_id}",
        "source_name": name,
        "source_type": source_type,
        "url": "",
        "tier": tier,
        "published_at": "",
        "stance": "neutral",
        "relevance_score": relevance,
        "trust_score": 0.7,
        "excerpt": note,
        "matched_claim_ids": [],
    }


def _add_source(
    results: list[dict[str, Any]],
    seen_names: set[str],
    name: str,
    relevance: float,
    note: str,
    source_type: str = "official",
    tier: str = "A",
) -> None:
    """Append a placeholder source once per normalized source name."""
    normalized_name = _normalize_for_match(name)
    if not normalized_name or normalized_name in seen_names:
        return
    seen_names.add(normalized_name)
    results.append(
        _make_placeholder_source(
            name=name,
            source_type=source_type,
            tier=tier,
            relevance=relevance,
            note=note,
        )
    )


def _topic_is_economy(topic: str, normalized: str) -> bool:
    """Detect economy-related topic hints in English or Italian."""
    topic_norm = _normalize_for_match(topic)
    return topic_norm in {"economy", "economia", "finanza"} or any(
        hint in normalized
        for hint in ("economy", "economia", "gdp", "pil", "inflation", "inflazione", "interest rate", "tasso di interesse")
    )


def _statistical_source_name(language_key: str) -> str:
    return "ISTAT / Istituto Nazionale di Statistica" if language_key == "it" else "National Statistics Office"


def _central_bank_source_name(language_key: str) -> str:
    return "Banca d'Italia / Central Bank" if language_key == "it" else "Central Bank / Monetary Authority"


def _regulatory_source_name(language_key: str) -> str:
    return "Gazzetta Ufficiale / Normattiva" if language_key == "it" else "Official Legal / Regulatory Database"


def _institutional_source_name(language_key: str) -> str:
    return "Ministero competente / Official institution page" if language_key == "it" else "Official Government / Institution Page"


def _government_body_source_name(language_key: str) -> str:
    return "Parlamento italiano / legislative records" if language_key == "it" else "Parliamentary records / government page"


def _contains_any(text: str, phrases: list[str]) -> bool:
    """Check whether any cue phrase appears in normalized text."""
    return any(_normalize_for_match(phrase) in text for phrase in phrases if phrase)


def _normalize_for_match(text: str) -> str:
    """Lowercase and remove accents so English and Italian cues both match."""
    normalized = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.casefold()
