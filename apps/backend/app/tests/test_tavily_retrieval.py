"""Regression tests for the Tavily retrieval layer."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import pytest

from app.config import Settings
from app.core.state import PipelineState
from app.models.response_models import build_response_from_state
from app.pipeline.tavily_first import TavilyFirstEngine


@pytest.mark.asyncio
async def test_tavily_multi_runs_queries_in_parallel(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_countries: list[str | None] = []

    async def fake_search(**kwargs: object) -> dict:
        await asyncio.sleep(0.12)
        seen_countries.append(kwargs.get("country"))
        query = str(kwargs["query"])
        return {
            "answer": f"hint:{query}",
            "request_id": f"req:{query}",
            "auto_parameters": {"topic": kwargs["topic"], "search_depth": "advanced"},
            "results": [
                {
                    "url": f"https://example.com/{query.replace(' ', '-')}",
                    "title": query,
                    "content": f"Content for {query}",
                    "score": 0.7,
                }
            ],
        }

    monkeypatch.setattr("app.pipeline.tavily_first.tavily_search", fake_search)

    engine = TavilyFirstEngine(Settings())
    started = time.perf_counter()
    results, hints = await engine._tavily_multi(
        ["alpha beta", "gamma delta", "rome 2026"],
        topic="general",
        country="italy",
        temporal={},
        exclude_domains=["reddit.com"],
    )
    elapsed = time.perf_counter() - started

    assert len(results) == 3
    assert len(hints) == 3
    assert elapsed < 0.26
    assert all("_query" in item for item in results)
    assert all("_answer_hint" in item for item in results)
    assert seen_countries == ["italy", "italy", "italy"]


def test_search_profile_prefers_finance_for_market_queries() -> None:
    engine = TavilyFirstEngine(Settings())
    state = PipelineState(topic="", article_date="")

    profile = engine._build_search_profile(
        state,
        "La BCE ha alzato i tassi e i mercati obbligazionari hanno reagito subito.",
    )

    assert profile["topic"] == "finance"
    assert profile["temporal"] == {}


def test_search_profile_uses_news_and_recent_window_for_current_events() -> None:
    engine = TavilyFirstEngine(Settings())
    state = PipelineState(topic="", article_date="")

    profile = engine._build_search_profile(
        state,
        "Ultim'ora: oggi il Papa visita Monaco per un incontro diplomatico.",
    )

    assert profile["topic"] == "news"
    assert profile["country"] == ""
    assert profile["temporal"]["time_range"] == "week"


def test_temporal_filters_anchor_around_recent_article_date() -> None:
    engine = TavilyFirstEngine(Settings())
    recent_date = datetime.now(timezone.utc).date().isoformat()
    state = PipelineState(article_date=recent_date)

    profile = engine._build_search_profile(
        state,
        "Report on a current government visit.",
    )

    assert profile["topic"] == "news"
    assert "start_date" in profile["temporal"]
    assert "end_date" in profile["temporal"]


def test_search_profile_normalizes_country_for_general_queries() -> None:
    engine = TavilyFirstEngine(Settings())
    state = PipelineState(country="IT")

    profile = engine._build_search_profile(
        state,
        "Mario Rossi biography and career details.",
    )

    assert profile["topic"] == "general"
    assert profile["country"] == "italy"


def test_content_trust_rewards_attribution_and_penalizes_spam() -> None:
    engine = TavilyFirstEngine(Settings())

    attributed = (
        'According to the official statement, Reuters reported that the ministry confirmed the 2026 figures. '
        'The report includes percentages, quoted remarks, and published data from the agency.'
    )
    spammy = "Shocking miracle click here buy now!!! You won't believe this viral story!!!"

    assert engine._content_trust_score(attributed) > engine._content_trust_score(spammy)


def test_pre_score_sources_keeps_domain_content_and_relevance_separate() -> None:
    engine = TavilyFirstEngine(Settings())
    results = [
        {
            "url": "https://unknown.example/story",
            "title": "Rome market update",
            "content": "According to the official report, Rome bond markets reacted after the ECB statement in 2026.",
            "raw_content": "According to the official report, Rome bond markets reacted after the ECB statement in 2026.",
            "score": 0.64,
        }
    ]

    scored = engine._pre_score_sources(results, "Rome bond markets reacted after the ECB statement.")
    item = scored[0]

    assert item["_domain_trust"] != item["_content_trust"]
    assert item["_local_relevance"] > 0
    assert item["_source_reliability"] != item["_local_relevance"]


@pytest.mark.asyncio
async def test_run_persists_tavily_results_and_answer_hints(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_search(**kwargs: object) -> dict:
        query = str(kwargs["query"])
        return {
            "answer": f"answer:{query}",
            "request_id": f"rid:{query}",
            "auto_parameters": {"topic": kwargs["topic"], "search_depth": "advanced"},
            "usage": {"credits": 2},
            "results": [
                {
                    "url": f"https://example.com/{query.replace(' ', '-')}",
                    "title": f"title:{query}",
                    "content": f"content:{query}",
                    "raw_content": f"raw:{query}",
                    "score": 0.81,
                }
            ],
        }

    async def fake_extract(**_: object) -> dict:
        return {"results": []}

    async def fake_generate_queries(self: TavilyFirstEngine, text: str) -> list[str]:
        return ["alpha beta", "\"rome 2026\""]

    async def fake_cross_check(
        self: TavilyFirstEngine,
        text: str,
        results: list[dict[str, object]],
        search_tier: str,
    ) -> dict[str, object]:
        return {
            "truth_score": 62,
            "confidence_score": 0.58,
            "verdict": "mixed",
            "explanation": {
                "summary": "summary",
                "why": "why",
                "supporting_evidence": [],
                "contradicting_evidence": [],
                "source_analysis": [],
                "temporal_context": "",
                "caveats": [],
            },
            "per_source": [],
        }

    monkeypatch.setattr("app.pipeline.tavily_first.tavily_search", fake_search)
    monkeypatch.setattr("app.pipeline.tavily_first.tavily_extract", fake_extract)
    monkeypatch.setattr(TavilyFirstEngine, "_generate_queries", fake_generate_queries)
    monkeypatch.setattr(TavilyFirstEngine, "_cross_check", fake_cross_check)

    engine = TavilyFirstEngine(Settings())
    state = PipelineState(normalized_text="Rome 2026 article", country="IT")
    state = await engine.run(state)

    assert state.all_tavily_results
    assert len(state.tavily_answer_hints) == 2
    assert state.tavily_search_profile["country"] == "italy"
    assert state.generated_queries == ["alpha beta", "\"rome 2026\""]
    assert all(item["_search_country"] == "italy" for item in state.all_tavily_results)

    response = build_response_from_state(state)
    assert response.all_tavily_results
    assert response.tavily_answer_hints
    assert response.tavily_search_profile["country"] == "italy"
    assert response.generated_queries == ["alpha beta", "\"rome 2026\""]


def test_build_response_exposes_url_processing_metadata() -> None:
    state = PipelineState(
        input_type="url",
        source_url="https://example.com/story",
        article_title="Example title",
        article_author="Jane Doe",
        article_date="2026-03-29",
        cited_links=["https://source.one", "https://source.two"],
    )

    response = build_response_from_state(state)

    assert response.source_url == "https://example.com/story"
    assert response.article_title == "Example title"
    assert response.article_author == "Jane Doe"
    assert response.article_date == "2026-03-29"
    assert response.cited_links == ["https://source.one", "https://source.two"]
    assert "news_general" in response.trusted_domains
    assert "ansa.it" in response.trusted_domains["news_general"]


def test_build_state_exposes_domain_content_and_claim_relevance_dimensions() -> None:
    engine = TavilyFirstEngine(Settings())
    state = PipelineState()
    results = engine._pre_score_sources(
        [
            {
                "url": "https://reuters.com/world/article",
                "title": "Official market report",
                "content": "According to Reuters, the official report confirmed the 2026 market reaction in Rome.",
                "raw_content": "According to Reuters, the official report confirmed the 2026 market reaction in Rome.",
                "score": 0.82,
            }
        ],
        "The 2026 market reaction in Rome was confirmed.",
    )
    analysis = {
        "truth_score": 55,
        "confidence_score": 0.5,
        "verdict": "mixed",
        "explanation": {},
        "per_source": [
            {
                "source_index": 0,
                "stance": "supporting",
                "relevance": 0.9,
                "key_excerpt": "the official report confirmed the 2026 market reaction",
            }
        ],
    }

    engine._build_state(state, results, analysis, "tier1")

    dims = state.sources_used[0]["dimensions"]
    assert "domain_trust" in dims
    assert "content_trust" in dims
    assert "claim_relevance" in dims
    assert state.sources_used[0]["source_reliability_score"] != dims["claim_relevance"]
