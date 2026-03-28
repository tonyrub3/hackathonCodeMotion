"""Shared helpers for contradiction detection heuristics."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from itertools import combinations
from typing import Any

_NUMBER_PATTERN = re.compile(
    r"(?<!\w)(?:\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)(?:\s*(%|per cento|percent(?:o)?|million(?:s)?|billion(?:s)?|thousand|mila|euro|eur|usd|\$|€|kg|km|m|anni|years?|months?|mesi))?",
    re.IGNORECASE,
)

_QUOTE_PATTERN = re.compile(r"[\"“”«»](.+?)[\"“”«»]")

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}

_ENTITY_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "il",
    "lo",
    "la",
    "i",
    "gli",
    "le",
    "un",
    "una",
    "uno",
    "del",
    "della",
    "dei",
    "delle",
    "dei",
    "di",
    "da",
    "de",
    "of",
    "to",
    "in",
    "on",
    "at",
    "for",
    "per",
    "con",
}


def group_evidence_by_claim(evidence: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group evidence items by claim id."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in evidence:
        claim_ids = item.get("matched_claim_ids", []) or []
        if not claim_ids:
            grouped["__unmatched__"].append(item)
            continue
        for claim_id in claim_ids:
            grouped[str(claim_id)].append(item)
    return grouped


def claim_lookup(claims: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map claim ids to claim dictionaries."""
    return {str(claim.get("id", "")): claim for claim in claims if claim.get("id")}


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    normalized = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.casefold()


def extract_numbers(text: str) -> list[dict[str, Any]]:
    """Extract numeric values and units from text."""
    results: list[dict[str, Any]] = []
    masked = _mask_date_like_fragments(text or "")
    for match in _NUMBER_PATTERN.finditer(masked):
        raw_value = match.group(0).strip()
        unit = (match.group(1) or "").strip().casefold()
        normalized_value = _normalize_number(raw_value)
        if normalized_value is None:
            continue
        results.append(
            {
                "raw": raw_value,
                "value": normalized_value,
                "unit": unit,
            }
        )
    return results


def extract_dates(text: str) -> list[dict[str, Any]]:
    """Extract date-like values from text."""
    results: list[dict[str, Any]] = []
    normalized = normalize_text(text or "")

    for match in re.finditer(r"\b(\d{4})-(\d{2})-(\d{2})\b", normalized):
        results.append({"raw": match.group(0), "value": match.group(0), "kind": "full_date"})

    for match in re.finditer(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", normalized):
        day, month, year = match.groups()
        year = _normalize_year(year)
        results.append(
            {
                "raw": match.group(0),
                "value": f"{year}-{int(month):02d}-{int(day):02d}",
                "kind": "full_date",
            }
        )

    month_names = "|".join(sorted(_MONTHS.keys(), key=len, reverse=True))
    for match in re.finditer(rf"\b(\d{{1,2}})\s+({month_names})\s+(\d{{4}})\b", normalized):
        day, month_name, year = match.groups()
        month = _MONTHS.get(month_name, 0)
        if month:
            results.append(
                {
                    "raw": match.group(0),
                    "value": f"{year}-{month:02d}-{int(day):02d}",
                    "kind": "full_date",
                }
            )

    for match in re.finditer(rf"\b({month_names})\s+(\d{{1,2}}),?\s+(\d{{4}})\b", normalized):
        month_name, day, year = match.groups()
        month = _MONTHS.get(month_name, 0)
        if month:
            results.append(
                {
                    "raw": match.group(0),
                    "value": f"{year}-{month:02d}-{int(day):02d}",
                    "kind": "full_date",
                }
            )

    for match in re.finditer(r"\b(19|20)\d{2}\b", normalized):
        results.append({"raw": match.group(0), "value": match.group(0), "kind": "year"})

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in results:
        key = f"{item['kind']}::{item['value']}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def extract_quotes(text: str) -> list[str]:
    """Extract quoted fragments from text."""
    quotes: list[str] = []
    for match in _QUOTE_PATTERN.finditer(text or ""):
        fragment = " ".join(match.group(1).split())
        if fragment:
            quotes.append(fragment)
    return _deduplicate_strings(quotes)


def extract_entities(text: str) -> list[str]:
    """Extract rough proper-noun entities from text."""
    entities: list[str] = []
    for match in re.finditer(r"(?<![\w-])(?:[A-ZÀ-ÖØ-Ý][\w'’.-]*(?:\s+[A-ZÀ-ÖØ-Ý][\w'’.-]*)*)", text or ""):
        entity = " ".join(match.group(0).split())
        normalized = normalize_text(entity)
        if not normalized:
            continue
        first_token = normalized.split()[0]
        if first_token in _ENTITY_STOPWORDS:
            continue
        if len(entity.split()) == 1 and len(entity) <= 2:
            continue
        entities.append(entity)
    return _deduplicate_strings(entities)


def pairwise(iterable: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Return all unique pairs from a list."""
    return list(combinations(iterable, 2))


def _normalize_number(raw_value: str) -> float | None:
    """Convert a textual number to a float when possible."""
    value = raw_value.replace(" ", "").strip()
    if not value:
        return None

    # Handle common European notation.
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        value = value.replace(".", "").replace(",", ".")
    else:
        value = value.replace(",", "")

    value = re.sub(r"[^0-9.\-]", "", value)
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _normalize_year(year: str) -> str:
    """Expand a two-digit year into a four-digit year."""
    year = year.strip()
    if len(year) == 2:
        prefix = "20" if int(year) <= 50 else "19"
        return f"{prefix}{year}"
    return year


def _deduplicate_strings(values: list[str]) -> list[str]:
    """Deduplicate a list of strings while preserving order."""
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        normalized = normalize_text(value)
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(value)
    return unique


def _mask_date_like_fragments(text: str) -> str:
    """Remove date-like fragments so they do not trigger number conflicts."""
    masked = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", text)
    masked = re.sub(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", " ", masked)
    month_names = "|".join(sorted(_MONTHS.keys(), key=len, reverse=True))
    masked = re.sub(rf"\b(\d{{1,2}}\s+(?:{month_names})\s+\d{{4}})", " ", masked, flags=re.IGNORECASE)
    masked = re.sub(rf"\b((?:{month_names})\s+\d{{1,2}},?\s+\d{{4}})", " ", masked, flags=re.IGNORECASE)
    masked = re.sub(r"\b(19|20)\d{2}\b", " ", masked)
    return masked
