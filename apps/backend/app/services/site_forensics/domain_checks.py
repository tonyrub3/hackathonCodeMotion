"""Domain metadata checks."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def check_domain_metadata(url: str) -> dict[str, Any]:
    """Inspect domain name, TLD, HTTPS, path structure."""
    parsed = urlparse(url)
    domain = parsed.netloc
    tld = domain.split(".")[-1] if "." in domain else ""

    return {
        "domain": domain,
        "tld": tld,
        "https": parsed.scheme == "https",
        "path_depth": len([p for p in parsed.path.split("/") if p]),
        "has_subdomain": domain.count(".") > 1,
    }
