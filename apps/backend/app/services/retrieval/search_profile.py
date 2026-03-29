"""Build Tavily search profiles from request and content context."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.state import PipelineState


RECENT_MARKERS_STRONG = (
    "today", "yesterday", "breaking", "latest", "just", "hours ago",
    "oggi", "ieri", "ultim'ora", "appena", "ore fa",
)
RECENT_MARKERS_SOFT = (
    "this week", "this month", "current", "currently", "now", "recent",
    "questa settimana", "questo mese", "attuale", "attualmente", "recente",
)
NEWS_HINTS = (
    "election", "minister", "government", "war", "earthquake", "visit", "appointed",
    "president", "pope", "sports", "match", "breaking", "ministero", "governo",
    "guerra", "terremoto", "visita", "nominato", "presidente", "papa", "partita",
)
FINANCE_HINTS = (
    "stock", "stocks", "market", "markets", "nasdaq", "dow jones", "s&p", "bond",
    "bonds", "inflation", "gdp", "earnings", "revenue", "interest rate", "rates",
    "crypto", "bitcoin", "ethereum", "share price", "fed", "ecb", "inflazione",
    "pil", "mercato", "mercati", "azioni", "obbligazioni", "tassi", "borsa",
    "ricavi", "utili", "criptovalute",
)
TOPIC_ALIASES = {
    "politics": "news",
    "politica": "news",
    "world": "news",
    "cronaca": "news",
    "sport": "news",
    "sports": "news",
    "current_events": "news",
    "attualita": "news",
    "attualità": "news",
    "economy": "finance",
    "economia": "finance",
    "business": "finance",
    "finance": "finance",
    "finanza": "finance",
    "markets": "finance",
    "mercati": "finance",
}
COUNTRY_ALIASES = {
    "it": "italy",
    "ita": "italy",
    "italia": "italy",
    "us": "united states",
    "usa": "united states",
    "u.s.": "united states",
    "u.s.a.": "united states",
    "uk": "united kingdom",
    "gb": "united kingdom",
    "gbr": "united kingdom",
    "england": "united kingdom",
    "fr": "france",
    "fra": "france",
    "de": "germany",
    "ger": "germany",
    "es": "spain",
    "esp": "spain",
}


def normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def parse_iso_like_date(value: str) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    for candidate in (text, text[:10]):
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


class TavilySearchProfileBuilder:
    """Select Tavily topic/country/time filters from content context."""

    def build(
        self,
        state: PipelineState,
        text: str,
        *,
        claims: list[dict[str, Any]] | None = None,
        queries: list[str] | None = None,
    ) -> dict[str, Any]:
        topic = self.select_tavily_topic(state, text, claims=claims, queries=queries)
        temporal = self.build_temporal_filters(state, text, topic, claims=claims, queries=queries)
        return {
            "topic": topic,
            "country": self.select_country_boost(state, topic),
            "temporal": temporal,
        }

    def select_tavily_topic(
        self,
        state: PipelineState,
        text: str,
        *,
        claims: list[dict[str, Any]] | None = None,
        queries: list[str] | None = None,
    ) -> str:
        requested = normalize_for_match(state.topic)
        if requested in {"general", "news", "finance"}:
            return requested
        if requested in TOPIC_ALIASES:
            return TOPIC_ALIASES[requested]

        normalized = normalize_for_match(self._search_context_text(text, claims=claims, queries=queries))
        if any(marker in normalized for marker in FINANCE_HINTS):
            return "finance"
        if self.has_recent_signal(state, text, claims=claims, queries=queries) or any(marker in normalized for marker in NEWS_HINTS):
            return "news"
        return "general"

    def select_country_boost(self, state: PipelineState, topic: str) -> str:
        if topic != "general":
            return ""
        return self.normalize_country(state.country)

    def normalize_country(self, country: str) -> str:
        normalized = normalize_for_match(country)
        if not normalized:
            return ""
        return COUNTRY_ALIASES.get(normalized, normalized)

    def build_temporal_filters(
        self,
        state: PipelineState,
        text: str,
        topic: str,
        *,
        claims: list[dict[str, Any]] | None = None,
        queries: list[str] | None = None,
    ) -> dict[str, str]:
        article_dt = parse_iso_like_date(state.article_date)
        now = datetime.now(timezone.utc)
        temporal: dict[str, str] = {}
        context_text = self._search_context_text(text, claims=claims, queries=queries)
        strong_recent = self.has_recent_signal(state, context_text, strong_only=True, claims=claims, queries=queries)
        any_recent = strong_recent or self.has_recent_signal(state, context_text, claims=claims, queries=queries)
        explicit_year = self._extract_explicit_year(context_text)

        if article_dt:
            age_days = abs((now - article_dt).days)
            if age_days <= 45:
                window_days = 3 if strong_recent else 10
                temporal["start_date"] = (article_dt - timedelta(days=window_days)).date().isoformat()
                temporal["end_date"] = (article_dt + timedelta(days=window_days)).date().isoformat()
                return temporal
            if explicit_year and str(article_dt.year) == explicit_year and topic in {"news", "finance"}:
                temporal["time_range"] = "month"
                return temporal

        if topic in {"news", "finance"} and any_recent:
            temporal["time_range"] = "week" if strong_recent else "month"
        return temporal

    def has_recent_signal(
        self,
        state: PipelineState,
        text: str,
        strong_only: bool = False,
        *,
        claims: list[dict[str, Any]] | None = None,
        queries: list[str] | None = None,
    ) -> bool:
        normalized = normalize_for_match(self._search_context_text(text, claims=claims, queries=queries))
        markers = RECENT_MARKERS_STRONG if strong_only else RECENT_MARKERS_STRONG + RECENT_MARKERS_SOFT
        if any(marker in normalized for marker in markers):
            return True
        if state.article_date:
            article_dt = parse_iso_like_date(state.article_date)
            if article_dt:
                days_old = abs((datetime.now(timezone.utc) - article_dt).days)
                return days_old <= (7 if strong_only else 30)
        return False

    def should_use_exact_match(self, query: str) -> bool:
        stripped = (query or "").strip()
        if stripped.startswith('"') and stripped.endswith('"'):
            return True
        if len(stripped.split()) <= 4 and any(ch.isdigit() for ch in stripped):
            return True
        quoted_entities = sum(1 for token in stripped.split() if token[:1].isupper())
        return len(stripped.split()) <= 6 and quoted_entities >= 2 and any(ch.isdigit() for ch in stripped)

    def _search_context_text(
        self,
        text: str,
        *,
        claims: list[dict[str, Any]] | None = None,
        queries: list[str] | None = None,
    ) -> str:
        parts = [text or ""]
        for claim in claims or []:
            parts.append(str(claim.get("claim", "")))
            parts.append(str(claim.get("search_query", "")))
        for query in queries or []:
            parts.append(str(query))
        return " ".join(part for part in parts if part)

    def _extract_explicit_year(self, text: str) -> str:
        match = re.search(r"\b(19|20)\d{2}\b", text or "")
        return match.group(0) if match else ""
