"""Author presence checks."""

from __future__ import annotations

import unicodedata
from typing import Any
from urllib.parse import urlparse


def check_author_presence(
    author_name: str,
    article_metadata: dict[str, Any],
) -> dict[str, Any]:
    """Check whether an article has an identifiable author.

    Returns: {"present": bool, "name": str, "page_found": bool}
    """
    name = (author_name or article_metadata.get("byline", "") or "").strip()
    page_candidates = _find_author_page_candidates(article_metadata)
    byline_present = bool(name)
    page_hints = article_metadata.get("page_hints", {}) or {}
    page_found = bool(page_candidates or page_hints.get("author"))

    return {
        "present": byline_present,
        "name": name,
        "page_found": page_found,
        "page_candidates": page_candidates,
        "history_signal": bool(page_candidates) and byline_present,
    }


def _find_author_page_candidates(article_metadata: dict[str, Any]) -> list[str]:
    """Heuristically identify internal links that look like author pages."""
    links = article_metadata.get("internal_links", []) or []
    candidates: list[str] = []
    for link in links:
        parsed = urlparse(link)
        path = _normalize_path(parsed.path)
        if any(
            token in path
            for token in (
                "/author/",
                "/authors/",
                "/staff/",
                "/team/",
                "/redazione",
                "/autore",
                "/autori",
                "/profile/",
                "/profilo/",
            )
        ):
            candidates.append(link)
    return candidates[:10]


def _normalize_path(path: str) -> str:
    """Lowercase and strip accents from a URL path."""
    normalized = unicodedata.normalize("NFKD", path or "")
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.casefold()
