"""Source-level scoring utilities."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "was", "were", "are",
    "del", "della", "delle", "degli", "dello", "con", "per", "che", "sono", "era", "dalla",
    "dalle", "nella", "nelle", "alla", "alle", "una", "uno", "gli", "lo", "la", "dei",
}
ATTRIBUTION_MARKERS = (
    "according to", "reported", "reports", "confirmed", "statement", "official", "data from",
    "said", "told", "announced", "published by", "secondo", "ha detto", "ha dichiarato",
    "ha confermato", "riporta", "comunicato", "dati di", "ufficiale", "ha annunciato",
)
STRUCTURE_MARKERS = (
    "%", "percent", "per cento", "million", "billion", "miliardi", "milioni",
    "202", "2026", "2025", "2024", "monday", "tuesday", "luned", "marted", "mercoled",
)
SPAM_MARKERS = (
    "click here", "buy now", "you won't believe", "shocking", "miracle", "viral",
    "clicca qui", "compra ora", "incredibile", "assurdo", "clamoroso", "miracoloso",
)


def domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url[:60]


def normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def tokenize(text: str) -> set[str]:
    cleaned = re.sub(r"[^\w\s]", " ", normalize_for_match(text))
    return {part for part in cleaned.split() if len(part) > 2 and part not in STOPWORDS}


def domain_reliability(domain: str) -> float:
    d = domain.lower()
    if any(x in d for x in [".gov", ".gob."]):
        return 0.92
    if any(x in d for x in [".edu", ".ac."]):
        return 0.87
    if any(x in d for x in [".int", ".europa.eu", "un.org", "who.int"]):
        return 0.90
    if any(x in d for x in [
        "reuters", "apnews", "bbc", "nytimes", "washingtonpost",
        "theguardian", "lemonde", "ansa.it", "ilsole24ore",
        "corriere", "repubblica", "nature.com", "science.org",
    ]):
        return 0.82
    if d.endswith(".org"):
        return 0.70
    return 0.60


def source_tier(reliability: float) -> str:
    if reliability >= 0.80:
        return "A"
    if reliability >= 0.65:
        return "B"
    return "C"


class SourceScoringLayer:
    """Score sources before cross-check, keeping trust and relevance separate."""

    def score_sources(self, results: list[dict[str, Any]], text: str) -> list[dict[str, Any]]:
        for item in results:
            domain = domain_from_url(item.get("url", ""))
            body = self.source_body(item)
            domain_trust = domain_reliability(domain)
            content_trust = self.content_trust_score(body)
            local_relevance = self.local_relevance_score(text, body)
            source_reliability = self.combine_source_trust(domain_trust, content_trust)
            pre_score = round(
                min(
                    1.0,
                    0.35 * float(item.get("score", 0.0))
                    + 0.30 * source_reliability
                    + 0.20 * local_relevance
                    + 0.15 * content_trust,
                ),
                3,
            )
            item["_domain_trust"] = round(domain_trust, 3)
            item["_content_trust"] = round(content_trust, 3)
            item["_local_relevance"] = round(local_relevance, 3)
            item["_source_reliability"] = round(source_reliability, 3)
            item["_pre_score"] = pre_score

        results.sort(
            key=lambda item: (
                float(item.get("_pre_score", 0.0)),
                float(item.get("score", 0.0)),
            ),
            reverse=True,
        )
        return results

    def source_body(self, source: dict[str, Any]) -> str:
        return " ".join(
            part for part in (
                source.get("title", ""),
                source.get("content", ""),
                source.get("raw_content", ""),
            ) if part
        )

    def content_trust_score(self, text: str) -> float:
        normalized = normalize_for_match(text)
        word_count = len(text.split())
        length_score = min(word_count / 320.0, 1.0)
        attribution_hits = sum(1 for marker in ATTRIBUTION_MARKERS if marker in normalized)
        attribution_score = min(attribution_hits / 3.0, 1.0)
        structure_hits = sum(1 for marker in STRUCTURE_MARKERS if marker in normalized)
        quote_bonus = 0.25 if '"' in text or "'" in text else 0.0
        structure_score = min(1.0, structure_hits / 3.0 + quote_bonus)
        spam_hits = sum(1 for marker in SPAM_MARKERS if marker in normalized)
        punctuation_penalty = 0.15 if text.count("!") >= 3 else 0.0
        spam_penalty = min(1.0, 0.22 * spam_hits + punctuation_penalty)

        return round(
            max(
                0.05,
                min(
                    1.0,
                    0.32 * length_score
                    + 0.33 * attribution_score
                    + 0.20 * structure_score
                    + 0.15 * (1.0 - spam_penalty),
                ),
            ),
            3,
        )

    def local_relevance_score(self, text_to_verify: str, source_text: str) -> float:
        reference = tokenize(text_to_verify)
        observed = tokenize(source_text)
        if not reference or not observed:
            return 0.0
        return round(min(1.0, len(reference & observed) / len(reference)), 3)

    def combine_source_trust(self, domain_trust: float, content_trust: float) -> float:
        return round(min(1.0, 0.58 * domain_trust + 0.42 * content_trust), 3)
