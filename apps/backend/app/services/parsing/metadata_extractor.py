"""Metadata extractor – pulls domain, citations, byline, and links from HTML."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse, urljoin


def extract_metadata(html: str, url: str = "") -> dict[str, Any]:
    """Extract metadata from HTML: domain, canonical URL, byline, outgoing links, etc."""
    parsed = urlparse(url)
    domain = parsed.netloc

    meta: dict[str, Any] = {
        "domain": domain,
        "canonical_url": url,
        "byline": "",
        "cited_links": [],
        "outgoing_domains": [],
    }

    if not html:
        return meta

    # Canonical URL
    canonical = re.search(r'rel="canonical"\s+href="([^"]*)"', html)
    if canonical:
        meta["canonical_url"] = canonical.group(1)

    # Byline
    byline = re.search(r'class="[^"]*byline[^"]*"[^>]*>(.*?)</[^>]+>', html, re.IGNORECASE | re.DOTALL)
    if byline:
        meta["byline"] = re.sub(r"<[^>]+>", "", byline.group(1)).strip()

    # Extract all outgoing links
    links = re.findall(r'href="(https?://[^"]+)"', html)
    external_links: list[str] = []
    external_domains: set[str] = set()
    for link in links:
        link_domain = urlparse(link).netloc
        if link_domain and link_domain != domain:
            external_links.append(link)
            external_domains.add(link_domain)

    meta["cited_links"] = external_links[:50]  # Cap
    meta["outgoing_domains"] = sorted(external_domains)

    return meta
