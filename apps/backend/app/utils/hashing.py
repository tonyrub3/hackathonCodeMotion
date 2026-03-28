"""Hashing utilities."""

from __future__ import annotations

import hashlib


def md5_short(text: str, length: int = 12) -> str:
    """Generate a short MD5 hash from text."""
    return hashlib.md5(text.encode()).hexdigest()[:length]
