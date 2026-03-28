"""Metadata extractor – pulls domain, citations, byline, and links from HTML."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse, urljoin

from app.services.parsing.language_detection import canonical_language_code


def extract_metadata(html: str, url: str = "") -> dict[str, Any]:
    """Extract metadata from HTML: domain, canonical URL, byline, outgoing links, etc."""
    parsed = urlparse(url)
    domain = parsed.netloc

    meta: dict[str, Any] = {
        "domain": domain,
        "canonical_url": url,
        "site_name": "",
        "byline": "",
        "cited_links": [],
        "outgoing_domains": [],
        "internal_links": [],
        "html_lang": "",
        "content_language": "",
        "og_locale": "",
        "page_hints": {
            "about": [],
            "contact": [],
            "editorial": [],
            "author": [],
            "ownership": [],
        },
    }

    if not html:
        return meta

    # Canonical URL
    canonical = re.search(r'rel="canonical"\s+href="([^"]*)"', html)
    if canonical:
        meta["canonical_url"] = canonical.group(1)

    # Language hints
    html_lang = re.search(r'<html[^>]*\blang=["\']?([a-zA-Z_-]+)', html, re.IGNORECASE)
    if html_lang:
        meta["html_lang"] = canonical_language_code(html_lang.group(1))

    content_language = re.search(
        r'<meta[^>]*http-equiv=["\']content-language["\'][^>]*content=["\']([^"\']+)',
        html,
        re.IGNORECASE,
    )
    if content_language:
        meta["content_language"] = canonical_language_code(content_language.group(1).split(",")[0].strip())

    og_locale = re.search(
        r'<meta[^>]*property=["\']og:locale["\'][^>]*content=["\']([^"\']+)',
        html,
        re.IGNORECASE,
    )
    if og_locale:
        meta["og_locale"] = canonical_language_code(og_locale.group(1))

    site_name = re.search(
        r'<meta[^>]*property=["\']og:site_name["\'][^>]*content=["\']([^"\']+)',
        html,
        re.IGNORECASE,
    )
    if site_name:
        meta["site_name"] = site_name.group(1).strip()

    # Byline
    byline = re.search(r'class="[^"]*byline[^"]*"[^>]*>(.*?)</[^>]+>', html, re.IGNORECASE | re.DOTALL)
    if byline:
        meta["byline"] = re.sub(r"<[^>]+>", "", byline.group(1)).strip()

    # Extract all links and classify them as internal, external, or transparency hints
    links = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
    external_links: list[str] = []
    external_domains: set[str] = set()
    internal_links: list[str] = []
    page_hints = {
        "about": set(),
        "contact": set(),
        "editorial": set(),
        "author": set(),
        "ownership": set(),
    }

    for link in links:
        absolute = urljoin(url, link)
        parsed_link = urlparse(absolute)
        link_domain = parsed_link.netloc
        if not link_domain:
            continue

        if domain and link_domain == domain:
            internal_links.append(absolute)
            path = (parsed_link.path or "").lower()
            if any(token in path for token in ("about", "chi-siamo", "who-we-are", "about-us")):
                page_hints["about"].add(absolute)
            if any(token in path for token in ("contact", "contatti", "contacts", "support", "help")):
                page_hints["contact"].add(absolute)
            if any(
                token in path
                for token in (
                    "editorial",
                    "linee-editoriali",
                    "privacy",
                    "cookie",
                    "terms",
                    "policy",
                    "disclaimer",
                    "methodology",
                    "metodologia",
                )
            ):
                page_hints["editorial"].add(absolute)
            if any(
                token in path
                for token in (
                    "author",
                    "authors",
                    "staff",
                    "team",
                    "redazione",
                    "autore",
                    "autori",
                    "profile",
                    "profilo",
                )
            ):
                page_hints["author"].add(absolute)
            if any(
                token in path
                for token in (
                    "about",
                    "chi-siamo",
                    "company",
                    "impressum",
                    "organization",
                )
            ):
                page_hints["ownership"].add(absolute)
            continue

        external_links.append(absolute)
        external_domains.add(link_domain)

    meta["cited_links"] = external_links[:50]  # Cap
    meta["outgoing_domains"] = sorted(external_domains)
    meta["internal_links"] = sorted(set(internal_links))[:100]
    meta["page_hints"] = {key: sorted(values) for key, values in page_hints.items()}

    return meta
