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


def test_search_profile_uses_claim_queries_for_recent_url_context() -> None:
    engine = TavilyFirstEngine(Settings())
    state = PipelineState(article_date="2026-03-28")

    profile = engine._build_search_profile(
        state,
        "Generic article body.",
        claims=[
            {
                "id": "c1",
                "claim": "Il presidente ha visitato Monaco il 28 marzo 2026.",
                "search_query": "presidente visita Monaco 28 marzo 2026",
            }
        ],
        queries=["presidente visita Monaco 28 marzo 2026"],
    )

    assert profile["topic"] == "news"
    assert profile["temporal"]


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

    async def fake_generate_queries(
        self: TavilyFirstEngine,
        text: str,
        claims: list[dict[str, object]] | None = None,
        state: PipelineState | None = None,
    ) -> list[str]:
        return ["alpha beta", '"rome 2026"']

    async def fake_cross_check(
        self: TavilyFirstEngine,
        text: str,
        results: list[dict[str, object]],
        search_tier: str,
        claims: list[dict[str, object]],
    ) -> dict[str, object]:
        return {
            "truth_score": 62,
            "confidence_score": 0.58,
            "verdict": "mixed",
            "explanation": {
                "summary": "Le fonti offrono un quadro misto.",
                "why": "Alcune fonti sono pertinenti, ma il contenuto non e confermato in modo pieno.",
                "supporting_evidence": ["Una fonte conferma parte del contesto."],
                "contradicting_evidence": [],
                "source_analysis": ["example.com: fonte usata nel confronto."],
                "temporal_context": "",
                "caveats": [],
            },
            "per_source": [
                {
                    "source_index": i,
                    "stance": "supporting",
                    "relevance": 0.7,
                    "key_excerpt": "confirmed by sources",
                }
                for i in range(len(results))
            ],
        }

    async def fake_score_explanation(
        self: TavilyFirstEngine,
        explanation: dict[str, object] | None,
        *,
        search_tier: str,
    ) -> dict[str, object]:
        return {
            "truth_score": 58,
            "confidence_score": 0.52,
            "verdict": "mixed",
            "reasoning": "Test stub",
        }

    monkeypatch.setattr("app.pipeline.tavily_first.tavily_search", fake_search)
    monkeypatch.setattr("app.pipeline.tavily_first.tavily_extract", fake_extract)
    monkeypatch.setattr(TavilyFirstEngine, "_generate_queries", fake_generate_queries)
    monkeypatch.setattr(TavilyFirstEngine, "_cross_check", fake_cross_check)
    monkeypatch.setattr(TavilyFirstEngine, "_score_explanation", fake_score_explanation)

    engine = TavilyFirstEngine(Settings())
    state = PipelineState(normalized_text="Rome 2026 article", country="IT")
    state = await engine.run(state)

    assert state.all_tavily_results
    assert len(state.tavily_answer_hints) == 2
    assert state.tavily_search_profile["country"] == "italy"
    assert state.generated_queries == ["alpha beta", '"rome 2026"']
    assert all(item["_search_country"] == "italy" for item in state.all_tavily_results)
    assert state.verdict == "mixed"
    assert 45.0 <= state.truth_score <= 65.0

    response = build_response_from_state(state)
    assert response.all_tavily_results
    assert response.tavily_answer_hints
    assert response.tavily_search_profile["country"] == "italy"
    assert response.generated_queries == ["alpha beta", '"rome 2026"']


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


def test_build_state_preserves_claims_and_uses_llm_judgment() -> None:
    engine = TavilyFirstEngine(Settings())
    state = PipelineState(input_type="url")
    state.claims = [
        {
            "id": "c1",
            "claim": "Il governo italiano ha approvato il decreto energia nel 2026.",
            "search_query": "decreto energia Italia 2026 approvazione",
            "type": "policy",
            "partial_verdict": "insufficient_evidence",
            "partial_score": 0.0,
            "checkability_score": 0.90,
        },
        {
            "id": "c2",
            "claim": "Il decreto prevede incentivi per le imprese energivore.",
            "search_query": "incentivi imprese energivore decreto energia",
            "type": "institutional",
            "partial_verdict": "insufficient_evidence",
            "partial_score": 0.0,
            "checkability_score": 0.80,
        },
    ]

    results = engine._pre_score_sources(
        [
            {
                "url": "https://reuters.com/world/article",
                "title": "Italy energy decree 2026",
                "content": "The Italian government approved the energy decree in 2026, confirming incentives.",
                "raw_content": "The Italian government approved the energy decree in 2026, confirming incentives.",
                "score": 0.85,
            }
        ],
        "Il governo italiano ha approvato il decreto energia nel 2026.",
    )
    analysis = {
        "judgment_basis": {
            "main_claim_confirmed": True,
            "direct_support_level": "moderate",
            "contradiction_level": "none",
            "subject_only_match": False,
            "evidence_sufficiency": "high",
            "source_agreement": "high",
            "temporal_alignment": "strong",
        },
        "truth_score": 78,
        "confidence_score": 0.74,
        "verdict": "mostly_verified",
        "explanation": {
            "summary": "Le fonti piu pertinenti confermano il fatto centrale.",
            "why": "Il decreto energia risulta confermato dalla fonte principale recuperata.",
            "supporting_evidence": ["Reuters riferisce dell'approvazione del decreto energia nel 2026."],
            "contradicting_evidence": [],
            "source_analysis": ["Reuters: fonte forte e coerente con il testo."],
            "temporal_context": "I fatti riguardano il 2026.",
            "caveats": [],
        },
        "per_source": [
            {
                "source_index": 0,
                "stance": "supporting",
                "relevance": 0.88,
                "key_excerpt": "approved the energy decree in 2026",
            }
        ],
    }

    engine._build_state(state, results, analysis, "tier1", state.claims)

    assert len(state.claims) == 2
    assert state.claims[0]["id"] == "c1"
    assert state.claims[1]["id"] == "c2"
    assert state.verdict in {"mostly_verified", "verified"}
    assert state.truth_score >= 65.0
    assert state.confidence_score >= 0.55
    assert state.explanation.get("summary") == "Le fonti piu pertinenti confermano il fatto centrale."
    assert "supporting_evidence" in state.explanation
    assert "source_analysis" in state.explanation
    assert state.consensus_signals["judgment_basis"]["direct_support_level"] == "moderate"

    response = build_response_from_state(state)
    assert len(response.claims) == 2
    assert response.claims[0].id == "c1"
    assert response.claims[0].checkability_score == 0.90


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
        "judgment_basis": {
            "main_claim_confirmed": False,
            "direct_support_level": "weak",
            "contradiction_level": "none",
            "subject_only_match": False,
            "evidence_sufficiency": "medium",
            "source_agreement": "medium",
            "temporal_alignment": "medium",
        },
        "truth_score": 55,
        "confidence_score": 0.5,
        "verdict": "mixed",
        "explanation": {
            "summary": "Le fonti danno un riscontro parziale.",
            "why": "Il contenuto ha copertura solo parziale.",
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "source_analysis": [],
            "temporal_context": "",
            "caveats": [],
        },
        "per_source": [
            {
                "source_index": 0,
                "stance": "supporting",
                "relevance": 0.9,
                "key_excerpt": "the official report confirmed the 2026 market reaction",
            }
        ],
    }

    claims = [{"id": "c0", "claim": "The 2026 market reaction in Rome was confirmed.", "type": "other", "checkability_score": 0.5}]
    engine._build_state(state, results, analysis, "tier1", claims)

    dims = state.sources_used[0]["dimensions"]
    assert "domain_trust" in dims
    assert "content_trust" in dims
    assert "claim_relevance" in dims
    assert state.sources_used[0]["source_reliability_score"] != dims["claim_relevance"]


def test_guardrails_block_positive_verdict_without_supporting_sources() -> None:
    engine = TavilyFirstEngine(Settings())
    state = PipelineState()
    results = engine._pre_score_sources(
        [
            {
                "url": "https://example.com/story",
                "title": "Generic context article",
                "content": "The article talks about the subject but does not confirm the main fact.",
                "raw_content": "The article talks about the subject but does not confirm the main fact.",
                "score": 0.61,
            }
        ],
        "Main fact that should not be over-verified.",
    )
    analysis = {
        "judgment_basis": {
            "main_claim_confirmed": False,
            "direct_support_level": "none",
            "contradiction_level": "none",
            "subject_only_match": True,
            "evidence_sufficiency": "low",
            "source_agreement": "low",
            "temporal_alignment": "weak",
        },
        "truth_score": 88,
        "confidence_score": 0.91,
        "verdict": "verified",
        "explanation": {
            "summary": "Le fonti sono molto forti.",
            "why": "Il modello avrebbe dato un giudizio troppo positivo.",
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "source_analysis": [],
            "temporal_context": "",
            "caveats": [],
        },
        "per_source": [
            {
                "source_index": 0,
                "stance": "neutral",
                "relevance": 0.72,
                "key_excerpt": "talks about the subject but not the predicate",
            }
        ],
    }

    engine._build_state(state, results, analysis, "tier1", [{"id": "c0", "claim": "Main fact", "type": "other", "checkability_score": 0.5}])

    assert state.verdict == "insufficient_evidence"
    assert state.confidence_score <= 0.45
    assert state.truth_score <= 59.0


def test_score_is_derived_from_judgment_basis_not_raw_llm_score() -> None:
    engine = TavilyFirstEngine(Settings())
    state = PipelineState()
    results = engine._pre_score_sources(
        [
            {
                "url": "https://example.com/story",
                "title": "Subject-only article",
                "content": "This article mentions the subject but never confirms the main predicate.",
                "raw_content": "This article mentions the subject but never confirms the main predicate.",
                "score": 0.79,
            }
        ],
        "Claim to verify",
    )
    analysis = {
        "judgment_basis": {
            "main_claim_confirmed": False,
            "direct_support_level": "none",
            "contradiction_level": "weak",
            "subject_only_match": True,
            "evidence_sufficiency": "low",
            "source_agreement": "low",
            "temporal_alignment": "medium",
        },
        "truth_score": 97,
        "confidence_score": 0.99,
        "verdict": "verified",
        "explanation": {
            "summary": "Le fonti parlano soprattutto del soggetto.",
            "why": "Il fatto principale non e confermato in modo diretto.",
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "source_analysis": [],
            "temporal_context": "",
            "caveats": [],
        },
        "per_source": [
            {
                "source_index": 0,
                "stance": "neutral",
                "relevance": 0.71,
                "key_excerpt": "mentions the subject",
            }
        ],
    }

    engine._build_state(state, results, analysis, "tier1", [{"id": "c0", "claim": "Claim to verify", "type": "other", "checkability_score": 0.5}])

    assert state.verdict == "insufficient_evidence"
    assert state.truth_score < 60.0
    assert state.confidence_score < 0.5


def test_guardrails_downgrade_when_explanation_denies_confirmation() -> None:
    engine = TavilyFirstEngine(Settings())
    state = PipelineState()
    results = engine._pre_score_sources(
        [
            {
                "url": "https://apnews.com/story",
                "title": "Article about the subject",
                "content": "The article mentions the subject but not the alleged death.",
                "raw_content": "The article mentions the subject but not the alleged death.",
                "score": 0.83,
            }
        ],
        "donald trump è stato ucciso l'anno scorso",
    )
    analysis = {
        "judgment_basis": {
            "main_claim_confirmed": False,
            "direct_support_level": "weak",
            "contradiction_level": "weak",
            "subject_only_match": True,
            "evidence_sufficiency": "low",
            "source_agreement": "low",
            "temporal_alignment": "weak",
        },
        "truth_score": 100,
        "confidence_score": 1.0,
        "verdict": "mostly_verified",
        "explanation": {
            "summary": "Le fonti non confermano il claim principale.",
            "why": "Le fonti citate parlano del soggetto ma non confermano che sia stato ucciso l'anno scorso.",
            "supporting_evidence": [],
            "contradicting_evidence": ["Le fonti non confermano l'affermazione principale."],
            "source_analysis": ["AP News menziona Donald Trump ma non conferma il presunto evento."],
            "temporal_context": "",
            "caveats": ["Evidenza insufficiente sul fatto principale."],
        },
        "per_source": [
            {
                "source_index": 0,
                "stance": "supporting",
                "relevance": 0.74,
                "key_excerpt": "mentions the subject",
            }
        ],
    }

    engine._build_state(state, results, analysis, "tier1", [{"id": "c0", "claim": "donald trump è stato ucciso l'anno scorso", "type": "other", "checkability_score": 0.5}])

    assert state.verdict in {"insufficient_evidence", "mostly_false"}
    assert state.confidence_score <= 0.45
    assert state.truth_score < 60.0


def test_url_claims_use_search_queries_not_raw_text() -> None:
    """Claims should use their LLM-composed search_query for Tavily, not raw claim text."""
    engine = TavilyFirstEngine(Settings())
    state = PipelineState(input_type="url")
    state.claims = [
        {"id": "c1", "claim": "Il Papa ha visitato Roma nel 2026.", "search_query": "Papa Francesco visita Roma 2026", "type": "event", "checkability_score": 0.9},
        {"id": "c2", "claim": "L'incontro e durato 3 ore.", "search_query": "incontro Papa Roma durata", "type": "event", "checkability_score": 0.7},
    ]

    queries = [c.get("search_query") or c["claim"][:80] for c in state.claims]
    assert queries == [
        "Papa Francesco visita Roma 2026",
        "incontro Papa Roma durata",
    ]
    for q in queries:
        assert len(q) < len(state.claims[0]["claim"])
