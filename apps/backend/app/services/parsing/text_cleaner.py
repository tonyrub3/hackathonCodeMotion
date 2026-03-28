"""Text cleaning utilities."""

from __future__ import annotations

import re
import unicodedata


def clean_text(raw: str) -> str:
    """Normalize whitespace, encoding, and remove artifacts."""
    if not raw:
        return ""
    # Normalize unicode
    text = unicodedata.normalize("NFKC", raw)
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    # Normalize line breaks
    text = re.sub(r"\r\n?", "\n", text)
    # Remove zero-width chars
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
