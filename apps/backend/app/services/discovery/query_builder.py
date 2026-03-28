"""Query builder – constructs search queries from claims."""

from __future__ import annotations

import re
from typing import Any


def build_queries(claim: dict[str, Any], topic: str = "") -> list[str]:
    """Build 1-3 search queries from a claim for use with GDELT / news discovery.

    Expands with entities, dates, numbers, and topic-specific hints.
    """
    text = claim.get("claim", "")
    queries: list[str] = [text]

    # Extract key entities / nouns for a focused query
    subject = claim.get("subject", "")
    obj = claim.get("object", "")
    time_scope = claim.get("time_scope", "")

    parts: list[str] = []
    if subject:
        parts.append(subject)
    if obj:
        parts.append(obj)
    if time_scope:
        parts.append(time_scope)

    if parts:
        queries.append(" ".join(parts))

    # Topic-enriched query
    if topic:
        queries.append(f"{topic} {text[:80]}")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        q_norm = q.strip().lower()
        if q_norm and q_norm not in seen:
            seen.add(q_norm)
            unique.append(q.strip())

    return unique[:3]
