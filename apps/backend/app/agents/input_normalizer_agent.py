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
from app.utils.pipeline_trace import layer_tag

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
        logger.info("%s input_type=text chars=%d", layer_tag("input"), len(state.normalized_text))
        logger.info(
            "%s language=%s source=%s confidence=%.2f",
            layer_tag("input"),
            state.language,
            detected["source"],
            detected["confidence"],
        )
        logger.debug("%s normalized: %.200s", layer_tag("input"), state.normalized_text)
        return state

    async def _handle_url(self, state: PipelineState) -> PipelineState:
        """Fetch URL, extract article, extract metadata."""
        state.source_url = state.raw_content.strip()
        logger.info("%s input_type=url url=%s", layer_tag("input"), state.source_url)

        html = await fetch_url(
            state.source_url,
            timeout=None if self.settings.request_timeout_seconds <= 0 else self.settings.request_timeout_seconds,
        )
        if not html:
            logger.error("%s failed_to_fetch_url", layer_tag("input"))
            raise RuntimeError("input_normalizer: failed to fetch URL")

        logger.info("%s fetched_html_chars=%d", layer_tag("input"), len(html))

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

        logger.info("%s title=%s", layer_tag("input"), state.article_title or "(none)")
        logger.info("%s author=%s", layer_tag("input"), state.article_author or "(none)")
        logger.info("%s date=%s", layer_tag("input"), state.article_date or "(none)")
        logger.info("%s body_chars=%d", layer_tag("input"), len(state.normalized_text))
        state.article_metadata = meta
        state.cited_links = meta.get("cited_links", [])
        state.article_metadata["detected_language"] = detected["language"]
        state.article_metadata["language_confidence"] = detected["confidence"]
        state.article_metadata["language_source"] = detected["source"]

        logger.info(
            "%s language=%s source=%s confidence=%.2f",
            layer_tag("input"),
            state.language,
            detected["source"],
            detected["confidence"],
        )
        logger.info("%s cited_links=%d", layer_tag("input"), len(state.cited_links))

        return state
