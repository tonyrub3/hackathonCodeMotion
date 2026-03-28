"""Input validators."""

from __future__ import annotations

from app.utils.urls import is_url


def detect_input_type(content: str) -> str:
    """Auto-detect if content is a URL or plain text."""
    if is_url(content.strip()):
        return "url"
    return "text"
