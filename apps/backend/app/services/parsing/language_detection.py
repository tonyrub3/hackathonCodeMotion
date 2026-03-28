"""Language detection helpers for English and Italian inputs."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any

_AUTO_LANGUAGE_VALUES = {"", "auto", "detect", "unknown", "und", "auto-detect"}

_HTML_LANGUAGE_PATTERNS = [
    re.compile(r'<html[^>]*\blang=["\']?([a-zA-Z_-]+)', re.IGNORECASE),
    re.compile(r'<meta[^>]*http-equiv=["\']content-language["\'][^>]*content=["\']([^"\']+)', re.IGNORECASE),
    re.compile(r'<meta[^>]*name=["\']language["\'][^>]*content=["\']([^"\']+)', re.IGNORECASE),
    re.compile(r'<meta[^>]*property=["\']og:locale["\'][^>]*content=["\']([^"\']+)', re.IGNORECASE),
]

_ITALIAN_STOPWORDS = {
    "il",
    "lo",
    "la",
    "i",
    "gli",
    "le",
    "l",
    "un",
    "una",
    "uno",
    "di",
    "del",
    "della",
    "dei",
    "delle",
    "che",
    "non",
    "per",
    "con",
    "su",
    "nel",
    "nella",
    "nei",
    "nelle",
    "al",
    "allo",
    "alla",
    "agli",
    "alle",
    "da",
    "d",
    "dal",
    "dallo",
    "dalla",
    "dai",
    "dalle",
    "e",
    "o",
    "ma",
    "se",
    "come",
    "che",
    "si",
    "sono",
    "era",
    "erano",
    "ha",
    "hanno",
    "del",
    "dell",
    "nell",
    "sull",
    "all",
    "perche",
    "poiche",
    "siccome",
    "quindi",
    "pertanto",
    "percio",
    "tuttavia",
    "nonostante",
    "dopo",
    "prima",
    "oggi",
    "ieri",
    "domani",
    "anche",
    "solo",
    "molto",
    "piu",
    "meno",
}

_ENGLISH_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "if",
    "because",
    "therefore",
    "however",
    "according",
    "to",
    "of",
    "in",
    "on",
    "at",
    "for",
    "with",
    "from",
    "by",
    "as",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "has",
    "have",
    "had",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "we",
    "they",
    "you",
}

_ITALIAN_STRONG_PHRASES = {
    "l'",
    "dell'",
    "nell'",
    "all'",
    "sull'",
    "dall'",
    "perche",
    "poiche",
    "siccome",
    "secondo",
    "ha detto",
    "ha dichiarato",
    "ha affermato",
    "ha annunciato",
    "il governo",
    "il parlamento",
    "la legge",
}

_ENGLISH_STRONG_PHRASES = {
    "the ",
    "because",
    "according to",
    "the government",
    "the parliament",
    "the law",
    "said",
    "stated",
    "declared",
    "announced",
}


def canonical_language_code(language: str | None) -> str:
    """Map a user-provided language hint to a supported code."""
    if not language:
        return "auto"

    normalized = language.strip().lower().replace("_", "-")
    if normalized in _AUTO_LANGUAGE_VALUES:
        return "auto"

    base = normalized.split("-", 1)[0]
    if base in {"it", "italian"}:
        return "it"
    if base in {"en", "english"}:
        return "en"
    return "auto"


def resolve_language(
    requested_language: str | None,
    *,
    text: str = "",
    html: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve the effective language for the current input.

    The detector prefers an explicit supported request, then HTML/meta hints,
    then a lightweight text classifier, and finally falls back to English.
    """
    requested = canonical_language_code(requested_language)
    if requested in {"it", "en"}:
        return {
            "language": requested,
            "confidence": 1.0,
            "source": "request",
        }

    html_hint = _html_language_hint(html, metadata)
    text_hint = _text_language_hint(text)

    if html_hint:
        if text_hint["language"] == html_hint:
            return {
                "language": html_hint,
                "confidence": max(0.9, text_hint["confidence"]),
                "source": "html",
            }
        if text_hint["confidence"] < 0.85:
            return {
                "language": html_hint,
                "confidence": 0.95,
                "source": "html",
            }

    if text_hint["confidence"] >= 0.55:
        return text_hint

    if html_hint:
        return {
            "language": html_hint,
            "confidence": 0.9,
            "source": "html",
        }

    return {
        "language": "en",
        "confidence": 0.5,
        "source": "default",
    }


def _html_language_hint(html: str, metadata: dict[str, Any] | None) -> str:
    """Extract a language hint from HTML metadata or raw tags."""
    if metadata:
        for key in ("html_lang", "content_language", "og_locale", "language"):
            code = canonical_language_code(str(metadata.get(key, "")))
            if code in {"it", "en"}:
                return code

    if not html:
        return ""

    for pattern in _HTML_LANGUAGE_PATTERNS:
        match = pattern.search(html)
        if match:
            code = canonical_language_code(match.group(1))
            if code in {"it", "en"}:
                return code

    return ""


def _text_language_hint(text: str) -> dict[str, Any]:
    """Classify the text with lightweight stop-word and marker heuristics."""
    if not text:
        return {
            "language": "en",
            "confidence": 0.0,
            "source": "default",
        }

    normalized = _normalize_text(text)
    tokens = re.findall(r"[a-z0-9']+", normalized)
    if not tokens:
        return {
            "language": "en",
            "confidence": 0.0,
            "source": "default",
        }

    counts = Counter(tokens)
    it_score = 0.0
    en_score = 0.0

    for token, count in counts.items():
        if token in _ITALIAN_STOPWORDS:
            it_score += count
        if token in _ENGLISH_STOPWORDS:
            en_score += count

    if _has_accented_characters(text):
        it_score += 1.5

    for phrase in _ITALIAN_STRONG_PHRASES:
        if phrase in normalized:
            it_score += 1.0

    for phrase in _ENGLISH_STRONG_PHRASES:
        if phrase in normalized:
            en_score += 1.0

    if it_score == 0.0 and en_score == 0.0:
        return {
            "language": "en",
            "confidence": 0.0,
            "source": "default",
        }

    language = "it" if it_score > en_score else "en"
    total = it_score + en_score
    confidence = 0.5 + min(0.4, abs(it_score - en_score) / max(total, 1.0) * 0.5)
    if it_score >= 2.0 or en_score >= 2.0:
        confidence = min(0.95, confidence + 0.1)

    return {
        "language": language,
        "confidence": round(min(0.95, confidence), 2),
        "source": "text",
    }


def _normalize_text(text: str) -> str:
    """Lowercase and strip accents for stable matching."""
    normalized = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.casefold()


def _has_accented_characters(text: str) -> bool:
    """Return True when the original string contains accent marks."""
    normalized = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped != text
