"""
Discovery router – decides which discovery channels to activate based on claim type and topic.

Uses discovery_rules.json and topic_rules.json to configure the discovery strategy.
"""

from __future__ import annotations

import json
import logging
import os
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

_RULES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "..", "data", "discovery_policies"
)

_TOPIC_ALIASES = {
    "economy": {"economy", "economia", "finanza"},
    "politics": {"politics", "politica"},
    "defense": {"defense", "difesa", "sicurezza", "militare"},
    "health": {"health", "salute", "sanita", "sanità"},
    "technology": {"technology", "tecnologia", "digitale"},
}


def load_discovery_rules() -> dict[str, Any]:
    """Load discovery rules from config files."""
    rules: dict[str, Any] = {}
    for filename in ("discovery_rules.json", "topic_rules.json"):
        path = os.path.join(_RULES_DIR, filename)
        try:
            with open(path) as f:
                rules[filename.replace(".json", "")] = json.load(f)
        except FileNotFoundError:
            logger.info("%s not found – using defaults", filename)
    return rules


def get_discovery_strategy(
    claim_type: str,
    topic: str = "",
) -> dict[str, bool]:
    """Determine which discovery channels to activate for a given claim.

    Returns a dict of channel_name -> enabled.
    """
    # Default: all channels enabled
    channels = {
        "google_factcheck": True,
        "gdelt_doc": True,
        "gdelt_context": True,
        "official_source": True,
        "news_source": True,
        "cited_source": True,
        "official_social": False,  # Off by default – expensive and noisy
    }

    # Prioritize official sources for certain claim types
    if claim_type in ("statistical", "regulatory", "institutional"):
        channels["official_source"] = True
        channels["official_social"] = False

    # Topic-specific adjustments
    topic_key = _canonical_topic(topic)
    if topic_key == "defense":
        channels["official_social"] = False  # Defense rarely posts on social

    return channels


def _canonical_topic(topic: str) -> str:
    """Map English and Italian topic labels to a canonical key."""
    normalized = _normalize_for_match(topic)
    for canonical, aliases in _TOPIC_ALIASES.items():
        if normalized in aliases:
            return canonical
    return normalized


def _normalize_for_match(text: str) -> str:
    """Lowercase and remove accents so English and Italian cues both match."""
    normalized = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.casefold()
