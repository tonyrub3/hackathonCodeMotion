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

    def build(self, state: PipelineState, text: str) -> dict[str, Any]:
        topic = self.select_tavily_topic(state, text)
        temporal = self.build_temporal_filters(state, text, topic)
        return {
            "topic": topic,
            "country": self.select_country_boost(state, topic),
            "temporal": temporal,
        }

    def select_tavily_topic(self, state: PipelineState, text: str) -> str:
        requested = normalize_for_match(state.topic)
        if requested in {"general", "news", "finance"}:
            return requested
        if requested in TOPIC_ALIASES:
            return TOPIC_ALIASES[requested]

        normalized = normalize_for_match(text)
        if any(marker in normalized for marker in FINANCE_HINTS):
            return "finance"
        if self.has_recent_signal(state, text) or any(marker in normalized for marker in NEWS_HINTS):
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

    def build_temporal_filters(self, state: PipelineState, text: str, topic: str) -> dict[str, str]:
        article_dt = parse_iso_like_date(state.article_date)
        now = datetime.now(timezone.utc)
        temporal: dict[str, str] = {}
        strong_recent = self.has_recent_signal(state, text, strong_only=True)
        any_recent = strong_recent or self.has_recent_signal(state, text)

        if article_dt:
            age_days = abs((now - article_dt).days)
            if age_days <= 45:
                window_days = 3 if strong_recent else 10
                temporal["start_date"] = (article_dt - timedelta(days=window_days)).date().isoformat()
                temporal["end_date"] = (article_dt + timedelta(days=window_days)).date().isoformat()
                return temporal

        if topic in {"news", "finance"} and any_recent:
            temporal["time_range"] = "week" if strong_recent else "month"
        return temporal

    def has_recent_signal(self, state: PipelineState, text: str, strong_only: bool = False) -> bool:
        normalized = normalize_for_match(text)
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
        return len(stripped.split()) <= 4 and any(ch.isdigit() for ch in stripped)
