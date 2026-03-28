"""
Agent 1 – Input Normalizer.

Responsibilities:
  - Detect input type (text / url)
  - Normalize encoding, clean whitespace
  - If URL: fetch HTML, extract article body + metadata
  - Store normalized text and metadata in state

Tools used:
  - text_parser  (services.parsing.text_cleaner)
  - url_fetcher  (services.parsing.html_parser)
  - article_extractor  (services.parsing.article_extractor)
  - metadata_extractor  (services.parsing.metadata_extractor)
"""

from __future__ import annotations

import logging
from app.config import Settings
from app.core.state import PipelineState
from app.services.parsing.text_cleaner import clean_text
from app.services.parsing.html_parser import fetch_url
from app.services.parsing.article_extractor import extract_article
from app.services.parsing.metadata_extractor import extract_metadata
from app.services.parsing.language_detection import resolve_language

logger = logging.getLogger(__name__)


class InputNormalizerAgent:
    """Normalize raw input into clean text + metadata."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, state: PipelineState) -> PipelineState:
        """
        Input contract:  state.raw_content, state.input_type
        Output contract: state.normalized_text, state.article_*, state.cited_links
        """
        if state.input_type == "url":
            state = await self._handle_url(state)
        else:
            state = self._handle_text(state)
        return state

    def _handle_text(self, state: PipelineState) -> PipelineState:
        """Clean and normalize plain-text input."""
        state.normalized_text = clean_text(state.raw_content)
        detected = resolve_language(state.language, text=state.normalized_text)
        state.language = detected["language"]
        state.article_metadata["detected_language"] = detected["language"]
        state.article_metadata["language_confidence"] = detected["confidence"]
        state.article_metadata["language_source"] = detected["source"]
        logger.info("    input_type=text  chars=%d", len(state.normalized_text))
        logger.info(
            "    language=%s source=%s confidence=%.2f",
            state.language,
            detected["source"],
            detected["confidence"],
        )
        logger.debug("    normalized: %.200s", state.normalized_text)
        return state

    async def _handle_url(self, state: PipelineState) -> PipelineState:
        """Fetch URL, extract article, extract metadata."""
        state.source_url = state.raw_content.strip()
        logger.info("    input_type=url  url=%s", state.source_url)

        html = await fetch_url(state.source_url, timeout=self.settings.request_timeout_seconds)
        if not html:
            logger.error("    FAILED to fetch URL")
            state.errors.append("input_normalizer: failed to fetch URL")
            state.normalized_text = ""
            return state

        logger.info("    fetched HTML: %d chars", len(html))

        meta = extract_metadata(html, state.source_url)
        article = extract_article(html, state.source_url)
        state.normalized_text = clean_text(article.get("text", ""))
        state.article_title = article.get("title", "")
        state.article_author = article.get("author", "")
        state.article_date = article.get("date", "")

        detected = resolve_language(
            state.language,
            text=" ".join(
                part for part in [state.article_title, state.normalized_text, state.article_author] if part
            ),
            html=html,
            metadata=meta,
        )
        state.language = detected["language"]

        logger.info("    title:  %s", state.article_title or "(none)")
        logger.info("    author: %s", state.article_author or "(none)")
        logger.info("    date:   %s", state.article_date or "(none)")
        logger.info("    body:   %d chars", len(state.normalized_text))
        state.article_metadata = meta
        state.cited_links = meta.get("cited_links", [])
        state.article_metadata["detected_language"] = detected["language"]
        state.article_metadata["language_confidence"] = detected["confidence"]
        state.article_metadata["language_source"] = detected["source"]

        logger.info(
            "    language=%s source=%s confidence=%.2f",
            state.language,
            detected["source"],
            detected["confidence"],
        )
        logger.info("    cited links: %d", len(state.cited_links))

        return state
