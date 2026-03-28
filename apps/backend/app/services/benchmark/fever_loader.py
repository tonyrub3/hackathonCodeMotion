"""FEVER dataset loader – parses FEVER JSONL files."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_fever_claims(
    jsonl_path: str,
    limit: int = 0,
) -> list[dict[str, Any]]:
    """Load FEVER claims from a JSONL file.

    Each line has: {"id": int, "claim": str, "label": str, "evidence": [...]}

    Args:
        jsonl_path: Path to the JSONL file.
        limit: Max claims to load (0 = all).

    Returns:
        List of parsed claim dicts.
    """
    path = Path(jsonl_path)
    if not path.exists():
        logger.warning("FEVER file not found: %s", jsonl_path)
        return []

    claims: list[dict[str, Any]] = []
    with open(path) as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                claims.append({
                    "id": entry.get("id", i),
                    "claim": entry.get("claim", ""),
                    "label": entry.get("label", ""),
                    "evidence": entry.get("evidence", []),
                })
            except json.JSONDecodeError:
                logger.warning("Skipping malformed line %d in %s", i, jsonl_path)

    logger.info("Loaded %d FEVER claims from %s", len(claims), jsonl_path)
    return claims
