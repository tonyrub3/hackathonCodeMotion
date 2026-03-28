"""
Official social discovery – find official social accounts for claim entities.

Only official, verified accounts are treated as credible.
Never uses non-official social as strong evidence.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def discover_official_social(
    claim: dict[str, Any],
    language: str = "en",
) -> list[dict[str, Any]]:
    """Discover official social accounts for entities in the claim.

    In MVP, this is a stub. In production, it would:
    - Extract organization/person entities from the claim
    - Search for verified social profiles (e.g., Twitter/X blue check, LinkedIn company pages)
    - Only return profiles that are clearly official

    Returns evidence-like dicts.
    """
    # TODO: Implement social media account discovery
    _ = language
    return []
