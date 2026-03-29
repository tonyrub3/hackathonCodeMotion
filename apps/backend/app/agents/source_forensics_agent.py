"""Agent 5 - forensic analysis for discovered URLs."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from app.config import Settings
from app.core.state import PipelineState
from app.services.parsing.article_extractor import extract_article
from app.services.parsing.html_parser import fetch_url
from app.services.parsing.metadata_extractor import extract_metadata

from ._agent_utils import domain_from_url, normalize_text

logger = logging.getLogger(__name__)


class SourceForensicsAgent:
    """Compute URL-level forensic signals before evidence scoring."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, state: PipelineState) -> PipelineState:
        by_source: dict[str, dict[str, Any]] = {}
        selected_ids = {item.get("source_id", "") for item in state.selected_sources}

        for source in state.all_sources_found:
            forensic = await self._analyze_source(source, fetch_live=self._should_fetch_live(source, selected_ids))
            by_source[source["source_id"]] = forensic
            source["forensic_score"] = forensic["forensic_score"]
            source["forensic_flags"] = forensic["flags"]
            source["dimensions"] = forensic["dimensions"]

        for collection in (state.selected_sources, state.sources_used):
            for source in collection:
                forensic = by_source.get(source.get("source_id", ""))
                if forensic:
                    source["forensic_score"] = forensic["forensic_score"]
                    source["dimensions"] = forensic["dimensions"]

        state.source_forensics = list(by_source.values())
        if state.input_type == "url" and state.source_url:
            input_domain = domain_from_url(state.source_url)
            state.site_forensics = next(
                (item for item in state.source_forensics if item.get("domain") == input_domain),
                None,
            )
        state.layer_outputs["source_forensics"] = {
            "source_forensics": state.source_forensics,
        }
        logger.info("    source forensics completed for %d source(s)", len(state.source_forensics))
        return state

    def _should_fetch_live(self, source: dict[str, Any], selected_ids: set[str]) -> bool:
        if source.get("source_id") not in selected_ids:
            return False
        domain = domain_from_url(str(source.get("url", "")))
        reserved_suffixes = (".example", ".invalid", ".test", ".local", ".localhost")
        if not domain or domain == "localhost" or domain.endswith(reserved_suffixes):
            return False
        return True

    async def _analyze_source(self, source: dict[str, Any], fetch_live: bool) -> dict[str, Any]:
        url = source.get("url", "")
        parsed = urlparse(url)
        domain = domain_from_url(url)
        tld = domain.split(".")[-1] if domain else ""
        https = parsed.scheme == "https"
        html = ""
        metadata: dict[str, Any] = {
            "page_hints": {"about": [], "contact": [], "editorial": [], "author": [], "ownership": []},
            "cited_links": [],
        }
        article: dict[str, Any] = {}

        if fetch_live and url:
            html = await fetch_url(url, timeout=self.settings.request_timeout_seconds)
            if html:
                metadata = extract_metadata(html, url)
                article = extract_article(html, url)

        cited_links = metadata.get("cited_links", [])
        raw_text = " ".join(
            part
            for part in (
                source.get("title", ""),
                source.get("snippet", ""),
                source.get("raw_content", ""),
                article.get("text", ""),
            )
            if part
        )
        word_count = max(len(raw_text.split()), 1)
        citation_density = min(1.0, len(cited_links) / max(word_count / 120.0, 1.0))
        page_hints = metadata.get("page_hints", {})
        transparency_signal = min(
            1.0,
            (
                len(page_hints.get("about", []))
                + len(page_hints.get("contact", []))
                + len(page_hints.get("editorial", []))
            )
            / 6.0,
        )
        author_name = article.get("author") or metadata.get("byline", "")
        author_present = bool(author_name)
        brand_mimicry_risk = self._brand_mimicry_risk(domain)
        low_quality_risk = self._low_quality_risk(domain, raw_text, https)

        forensic_score = max(
            0.0,
            min(
                1.0,
                0.22 * (1.0 if https else 0.2)
                + 0.18 * (1.0 if author_present else 0.35)
                + 0.20 * citation_density
                + 0.20 * transparency_signal
                + 0.20 * (1.0 - max(brand_mimicry_risk, low_quality_risk)),
            ),
        )

        flags: list[str] = []
        if not https:
            flags.append("no_https")
        if not author_present:
            flags.append("author_missing")
        if brand_mimicry_risk > 0.4:
            flags.append("brand_mimicry_risk")
        if low_quality_risk > 0.45:
            flags.append("low_quality_risk")
        if transparency_signal < 0.2:
            flags.append("low_transparency")

        return {
            "source_id": source.get("source_id", ""),
            "url": url,
            "domain": domain,
            "tld": tld,
            "https": https,
            "canonical_origin": metadata.get("canonical_url") or url,
            "author_present": author_present,
            "author_name": author_name,
            "citation_density": round(citation_density, 3),
            "citation_count": len(cited_links),
            "about_links": len(page_hints.get("about", [])),
            "contact_links": len(page_hints.get("contact", [])),
            "editorial_links": len(page_hints.get("editorial", [])),
            "brand_mimicry_risk": round(brand_mimicry_risk, 3),
            "low_quality_risk": round(low_quality_risk, 3),
            "published_at": article.get("date", "") or source.get("published_at", ""),
            "forensic_score": round(forensic_score, 3),
            "dimensions": {
                "https": 1.0 if https else 0.2,
                "author": 1.0 if author_present else 0.35,
                "citation_density": round(citation_density, 3),
                "transparency": round(transparency_signal, 3),
                "brand_safety": round(1.0 - brand_mimicry_risk, 3),
                "quality": round(1.0 - low_quality_risk, 3),
            },
            "flags": flags,
        }

    def _brand_mimicry_risk(self, domain: str) -> float:
        known_brands = ("reuters", "apnews", "bbc", "nytimes", "theguardian", "ansa")
        if domain.startswith("xn--"):
            return 0.8
        hyphen_count = domain.count("-")
        if hyphen_count >= 3:
            return 0.65
        if any(brand in domain and not domain.endswith(f"{brand}.com") for brand in known_brands):
            return 0.55
        return 0.1

    def _low_quality_risk(self, domain: str, raw_text: str, https: bool) -> float:
        lowered = normalize_text(raw_text)
        spam_markers = ("click here", "subscribe now", "you won't believe", "scopri ora", "clicca qui")
        marker_hits = sum(1 for marker in spam_markers if marker in lowered)
        risk = 0.15 * marker_hits
        if len(raw_text.split()) < 80:
            risk += 0.2
        if domain.endswith(".info") or domain.endswith(".xyz"):
            risk += 0.25
        if not https:
            risk += 0.15
        return min(1.0, risk)
