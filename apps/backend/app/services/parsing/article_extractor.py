"""Article extractor – pulls readable content from HTML."""

from __future__ import annotations

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_article(html: str, url: str = "") -> dict[str, Any]:
    """Extract article body, title, author, and date from HTML.

    Uses a lightweight regex approach for the MVP.
    TODO: integrate trafilatura or readability-lxml for production quality.
    """
    result: dict[str, Any] = {
        "text": "",
        "title": "",
        "author": "",
        "date": "",
        "url": url,
    }

    if not html:
        return result

    # Try trafilatura if available (best option)
    try:
        import trafilatura  # type: ignore

        downloaded = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            output_format="txt",
        )
        meta = trafilatura.extract(
            html,
            include_comments=False,
            output_format="xmltei",
        )
        if downloaded:
            result["text"] = downloaded

        # Extract metadata from TEI if available
        if meta:
            title_match = re.search(r"<title[^>]*>(.*?)</title>", meta, re.DOTALL)
            if title_match:
                result["title"] = title_match.group(1).strip()
            author_match = re.search(r'<author[^>]*>(.*?)</author>', meta, re.DOTALL)
            if author_match:
                result["author"] = author_match.group(1).strip()
            date_match = re.search(r'<date[^>]*>(.*?)</date>', meta, re.DOTALL)
            if date_match:
                result["date"] = date_match.group(1).strip()

        return result
    except ImportError:
        pass

    # Fallback: simple regex extraction
    # Title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title_match:
        result["title"] = _strip_tags(title_match.group(1)).strip()

    # OG meta
    og_title = re.search(r'property="og:title"\s+content="([^"]*)"', html)
    if og_title and not result["title"]:
        result["title"] = og_title.group(1)

    # Author
    author_match = re.search(r'name="author"\s+content="([^"]*)"', html)
    if author_match:
        result["author"] = author_match.group(1)

    # Date
    date_match = re.search(
        r'(?:datePublished|article:published_time|name="date")["\s]+content="([^"]*)"',
        html,
    )
    if date_match:
        result["date"] = date_match.group(1)

    # Body: strip tags from <article> or <body>
    article_match = re.search(r"<article[^>]*>(.*?)</article>", html, re.IGNORECASE | re.DOTALL)
    if article_match:
        result["text"] = _strip_tags(article_match.group(1))
    else:
        body_match = re.search(r"<body[^>]*>(.*?)</body>", html, re.IGNORECASE | re.DOTALL)
        if body_match:
            result["text"] = _strip_tags(body_match.group(1))

    return result


def _strip_tags(html_fragment: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html_fragment, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
