"""Tests for input normalization and language detection."""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.input_normalizer_agent import InputNormalizerAgent
from app.config import Settings
from app.core.state import PipelineState


@pytest.mark.asyncio
async def test_normalizer_auto_detects_italian_text():
    agent = InputNormalizerAgent(Settings())
    state = PipelineState(
        raw_content="L'inflazione e aumentata perche i prezzi dell'energia sono saliti.",
        input_type="text",
        language="auto",
    )

    await agent.run(state)

    assert state.language == "it"
    assert state.normalized_text.startswith("L'inflazione")
    assert state.article_metadata["detected_language"] == "it"
    assert state.article_metadata["language_source"] == "text"


@pytest.mark.asyncio
async def test_normalizer_uses_html_language_hint_for_url():
    agent = InputNormalizerAgent(Settings())
    html = """
    <html lang="it">
      <head>
        <meta http-equiv="content-language" content="it_IT">
      </head>
      <body>
        <article>
          <h1>Titolo di prova</h1>
          <p>Il governo ha approvato la misura.</p>
        </article>
      </body>
    </html>
    """

    article = {
        "text": "Il governo ha approvato la misura.",
        "title": "Titolo di prova",
        "author": "Redazione",
        "date": "2026-01-01",
    }
    metadata = {
        "domain": "example.it",
        "canonical_url": "https://example.it/articolo",
        "byline": "Redazione",
        "cited_links": [],
        "outgoing_domains": [],
        "html_lang": "it",
        "content_language": "it",
        "og_locale": "",
    }

    with (
        patch("app.agents.input_normalizer_agent.fetch_url", new=AsyncMock(return_value=html)),
        patch("app.agents.input_normalizer_agent.extract_article", return_value=article),
        patch("app.agents.input_normalizer_agent.extract_metadata", return_value=metadata),
    ):
        state = PipelineState(
            raw_content="https://example.it/articolo",
            input_type="url",
            language="auto",
        )
        await agent.run(state)

    assert state.language == "it"
    assert state.article_metadata["detected_language"] == "it"
    assert state.article_metadata["language_source"] == "html"
