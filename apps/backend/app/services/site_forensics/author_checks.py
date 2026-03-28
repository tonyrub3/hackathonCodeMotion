"""Author presence checks."""

from __future__ import annotations

from typing import Any


def check_author_presence(
    author_name: str,
    article_metadata: dict[str, Any],
) -> dict[str, Any]:
    """Check whether an article has an identifiable author.

    Returns: {"present": bool, "name": str, "page_found": bool}
    """
    name = author_name or article_metadata.get("byline", "")

    return {
        "present": bool(name and name.strip()),
        "name": name.strip() if name else "",
        "page_found": False,  # TODO: check if author page exists on the site
    }
