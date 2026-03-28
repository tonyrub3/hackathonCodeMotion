"""Tests for discovery utilities."""

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
