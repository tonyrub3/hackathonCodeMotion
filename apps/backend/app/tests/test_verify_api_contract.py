"""API contract regression tests for the agentic verify endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_verify_endpoint_exposes_agent_layers(monkeypatch) -> None:
    async def fake_search(**_: object) -> dict:
        return {
            "answer": "Auxiliary answer only.",
            "results": [
                {
                    "url": "https://source-a.example/article",
                    "title": "Source A",
                    "content": "Alpha beta happened in Rome according to the report.",
                    "raw_content": "Alpha beta happened in Rome according to the report.",
                    "score": 0.88,
                },
                {
                    "url": "https://source-b.example/article",
                    "title": "Source B",
                    "content": "Alpha beta happened in Rome with matching details.",
                    "raw_content": "Alpha beta happened in Rome with matching details.",
                    "score": 0.83,
                },
            ],
        }

    async def fake_extract(**_: object) -> dict:
        return {"results": []}

    async def fake_fetch_url(*_: object, **__: object) -> str:
        return ""

    monkeypatch.setattr("app.agents.discovery_agent.tavily_search", fake_search)
    monkeypatch.setattr("app.agents.discovery_agent.tavily_extract", fake_extract)
    monkeypatch.setattr("app.agents.source_forensics_agent.fetch_url", fake_fetch_url)

    app = create_app(Settings())
    with TestClient(app) as client:
        response = client.post(
            "/api/verify",
            json={"input_type": "text", "content": "Alpha beta happened in Rome.", "language": "en"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert "all_sources_found" in payload
        assert "selected_sources" in payload
        assert "rejected_sources" in payload
        assert "source_forensics" in payload
        assert "claim_scores" in payload
        assert "layer_outputs" in payload
        assert payload["all_sources_found"]
        assert payload["selected_sources"]
        assert isinstance(payload["source_forensics"], list)
        assert isinstance(payload["claim_scores"], list)
        assert "query_planning" in payload["layer_outputs"]
        assert "verdict_consistency" in payload["layer_outputs"]
