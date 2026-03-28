"""URL utilities."""

from __future__ import annotations

import re
from urllib.parse import urlparse

_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")


def is_url(text: str) -> bool:
    """Check if text looks like a URL."""
    return bool(_URL_PATTERN.match(text.strip()))


def extract_domain(url: str) -> str:
    """Extract the domain from a URL."""
    return urlparse(url).netloc
