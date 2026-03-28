"""Tests for discovery utilities."""

import pytest

from app.services.discovery.discovery_router import get_discovery_strategy
from app.services.discovery.official_source_discovery import discover_official_sources
from app.services.discovery.query_builder import build_queries


def test_build_queries_basic():
    claim = {"claim": "Inflation in Italy is 2%", "subject": "", "object": "", "time_scope": ""}
    queries = build_queries(claim)
    assert len(queries) >= 1
    assert "Inflation" in queries[0]


def test_build_queries_with_topic():
    claim = {"claim": "GDP grew by 3%", "subject": "GDP", "object": "3%", "time_scope": "2025"}
    queries = build_queries(claim, topic="economy")
    assert len(queries) >= 2
    assert any("economy" in q for q in queries)


def test_build_queries_dedup():
    claim = {"claim": "Test claim", "subject": "", "object": "", "time_scope": ""}
    queries = build_queries(claim)
    assert len(queries) == len(set(q.lower() for q in queries))


def test_build_queries_italian_topic_hints():
    claim = {
        "claim": "L'inflazione in Italia è al 2% nel 2026.",
        "subject": "inflazione",
        "object": "2%",
        "time_scope": "2026",
        "type": "statistical",
    }
    queries = build_queries(claim, topic="economia", language="it")
    assert len(queries) >= 2
    assert queries[0] == claim["claim"]
    assert any("economia" in q.lower() for q in queries)
    assert any("istat" in q.lower() or "banca d'italia" in q.lower() for q in queries)


@pytest.mark.asyncio
async def test_discover_official_sources_italian_statistical():
    claim = {
        "claim": "L'ISTAT ha pubblicato dati sull'inflazione italiana.",
        "subject": "ISTAT",
        "type": "statistical",
    }
    results = await discover_official_sources(claim, topic="economia", language="it")
    names = [item["source_name"].lower() for item in results]

    assert any("istat" in name for name in names)
    assert any("eurostat" in name for name in names)


def test_discovery_strategy_accepts_italian_topic_labels():
    strategy = get_discovery_strategy("statistical", topic="difesa")
    assert strategy["official_source"] is True
    assert strategy["official_social"] is False
