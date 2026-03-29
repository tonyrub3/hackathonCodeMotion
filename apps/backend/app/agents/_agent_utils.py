"""Shared utilities for the agentic runtime."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urlparse, urlunparse


STOPWORDS = {
    "en": {
        "a", "an", "the", "of", "for", "to", "in", "on", "at", "by", "with", "from",
        "is", "are", "was", "were", "be", "been", "being", "that", "this", "these",
        "those", "it", "its", "as", "and", "or", "but", "than", "then", "after",
        "before", "about", "into", "over", "under", "between", "during", "your",
    },
    "it": {
        "il", "lo", "la", "i", "gli", "le", "un", "una", "di", "del", "della", "delle",
        "dei", "da", "dal", "dalla", "dalle", "a", "al", "alla", "alle", "in", "su",
        "con", "per", "tra", "fra", "e", "o", "ma", "che", "questo", "questa", "questi",
        "queste", "quello", "quella", "quelli", "quelle", "era", "sono", "ha", "hanno",
        "come", "dove", "quando", "dopo", "prima",
    },
}

NEGATION_MARKERS = {
    "en": {"not", "never", "false", "incorrect", "denied", "debunked", "no evidence", "did not"},
    "it": {"non", "mai", "falso", "errato", "smentito", "smentisce", "nessuna prova"},
}

RECENT_MARKERS = {
    "en": {"today", "yesterday", "breaking", "just", "hours ago", "minutes ago"},
    "it": {"oggi", "ieri", "ultim'ora", "appena", "ore fa", "minuti fa"},
}


def normalize_text(text: str) -> str:
    """Lowercase alphanumeric normalization with collapsed whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s:/.-]", " ", (text or "").lower())).strip()


def split_sentences(text: str) -> list[str]:
    """Simple sentence splitter good enough for the current runtime."""
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [chunk.strip() for chunk in chunks if chunk and chunk.strip()]


def tokenize(text: str, language: str = "en") -> set[str]:
    """Tokenize text into informative terms."""
    tokens = [part for part in normalize_text(text).split() if len(part) > 2]
    stop = STOPWORDS.get(language, STOPWORDS["en"])
    return {token for token in tokens if token not in stop}


def overlap_ratio(reference: Iterable[str], observed: Iterable[str]) -> float:
    """Return coverage of reference tokens present in observed tokens."""
    reference_set = set(reference)
    if not reference_set:
        return 0.0
    observed_set = set(observed)
    return round(len(reference_set & observed_set) / len(reference_set), 4)


def stable_id(prefix: str, value: str) -> str:
    """Generate a stable short identifier."""
    digest = hashlib.sha1((value or "").encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def canonicalize_url(url: str) -> str:
    """Canonicalize URL for deduplication."""
    parsed = urlparse(url)
    netloc = parsed.netloc.lower().replace("www.", "")
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), netloc, path, "", "", ""))


def domain_from_url(url: str) -> str:
    """Return normalized domain from URL."""
    return urlparse(url).netloc.lower().replace("www.", "")


def infer_claim_type(text: str) -> str:
    """Infer a coarse claim type from lexical cues."""
    lowered = normalize_text(text)
    if any(char.isdigit() for char in text):
        return "statistical"
    if '"' in text or "'" in text:
        return "quote"
    if any(token in lowered for token in ("minister", "government", "pope", "ministero", "governo", "papa")):
        return "institutional"
    if any(token in lowered for token in ("because", "caused", "ha causato", "perché", "perche")):
        return "causal"
    return "event"


def detect_recent_claim(text: str) -> bool:
    """Detect whether a claim looks freshness-sensitive."""
    normalized = normalize_text(text)
    markers = RECENT_MARKERS["en"] | RECENT_MARKERS["it"]
    return any(marker in normalized for marker in markers)


def parse_datetime(value: str) -> datetime | None:
    """Best-effort datetime parser."""
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def temporal_alignment_score(claim: dict, published_at: str) -> float:
    """Score temporal alignment between a claim and evidence."""
    claim_recent = bool(claim.get("time_sensitive") or claim.get("recent"))
    published = parse_datetime(published_at)
    if not claim_recent:
        return 0.8 if published else 0.6
    if not published:
        return 0.25
    delta = datetime.now(timezone.utc) - published
    if delta.days <= 3:
        return 1.0
    if delta.days <= 14:
        return 0.75
    return 0.45


def contradiction_hit(text: str, language: str) -> bool:
    """Detect negation/contradiction cues."""
    lowered = normalize_text(text)
    markers = NEGATION_MARKERS.get(language, NEGATION_MARKERS["en"]) | NEGATION_MARKERS["en"] | NEGATION_MARKERS["it"]
    return any(marker in lowered for marker in markers)
