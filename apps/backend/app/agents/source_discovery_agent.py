"""
Agent 3 – Source Discovery.

Responsibilities:
  - Generate retrieval queries from each claim
  - Discover evidence sources automatically (no manual whitelist)
  - Query Google Fact Check, GDELT, official-source heuristics
  - Mine cited sources from input article (URL mode)
  - Collect candidate evidence items

  Tools used:
  - query_builder
  - google_factcheck_search
  - gdelt_doc_search
  - gdelt_context_search
  - cited_source_miner
  - internal official / social target synthesis
  - passage_selector
"""

from __future__ import annotations

import hashlib
import re
import logging
import unicodedata
from typing import Any
from urllib.parse import urlparse

from app.config import Settings
from app.core.state import PipelineState
from app.services.discovery.discovery_router import get_discovery_strategy
from app.services.discovery.query_builder import build_queries
from app.services.connectors.google_factcheck_search import search_google_factcheck
from app.services.connectors.gdelt_doc_search import search_gdelt_docs
from app.services.connectors.gdelt_context_search import search_gdelt_context
from app.services.discovery.cited_source_miner import mine_cited_sources
from app.services.parsing.language_detection import resolve_language

logger = logging.getLogger(__name__)

_INSTITUTION_CUES = {
    "ministero",
    "governo",
    "parlamento",
    "commissione",
    "agenzia",
    "authority",
    "regulator",
    "agency",
    "department",
    "ministry",
    "parliament",
    "congress",
    "senate",
    "government",
    "comune",
    "regione",
    "municipality",
    "municipal",
    "council",
    "office",
    "ufficio",
    "istat",
    "eurostat",
    "banca d'italia",
    "bank of italy",
    "central bank",
}

_COMPANY_CUES = {
    "spa",
    "s.p.a.",
    "inc",
    "ltd",
    "llc",
    "corp",
    "company",
    "group",
    "holding",
    "industries",
    "technology",
    "tech",
    "societa",
    "società",
    "azienda",
    "azienda",
    "enterprise",
}

_MEDIA_CUES = {
    "press",
    "news",
    "newsroom",
    "media",
    "editorial",
    "redazione",
    "giornale",
    "newspaper",
    "tv",
    "radio",
    "magazine",
}

_SOCIAL_PLATFORM_HINTS = {
    "institution": ["X", "Facebook", "YouTube", "LinkedIn"],
    "company": ["X", "LinkedIn", "YouTube", "Facebook"],
    "person": ["X", "Instagram", "YouTube", "Facebook"],
    "media": ["X", "Facebook", "YouTube", "Instagram"],
    "default": ["X", "LinkedIn", "YouTube"],
}

_OFFICIAL_QUERY_HINTS = {
    "en": {
        "statistical": ["official statistics", "official data", "statistics office", "central bank"],
        "regulatory": ["official statement", "government release", "parliament record", "official gazette"],
        "institutional": ["official statement", "government release", "ministry page", "official page"],
        "quote": ["official statement", "press release", "transcript", "original source"],
        "causal": ["official data", "analysis", "report", "press release"],
        "technical": ["documentation", "specification", "release notes", "technical paper"],
        "event": ["official statement", "press release", "newsroom", "breaking"],
        "historical": ["archive", "primary source", "historical record", "official archive"],
    },
    "it": {
        "statistical": ["dati ufficiali", "ufficio statistico", "banca centrale", "statistiche ufficiali"],
        "regulatory": ["comunicato ufficiale", "gazzetta ufficiale", "documenti parlamentari", "atto ufficiale"],
        "institutional": ["comunicato ufficiale", "pagina ufficiale", "ministero", "ente ufficiale"],
        "quote": ["dichiarazione ufficiale", "comunicato", "trascrizione", "fonte originale"],
        "causal": ["dati ufficiali", "analisi", "rapporto", "comunicato"],
        "technical": ["documentazione", "specifiche", "note di rilascio", "documento tecnico"],
        "event": ["comunicato ufficiale", "nota", "newsroom", "ultime notizie"],
        "historical": ["archivio", "fonte primaria", "record storico", "archivio ufficiale"],
    },
}

_SOCIAL_HANDLE_STOPWORDS = {
    "account",
    "official",
    "ufficiale",
    "profilo",
    "verified",
    "verificato",
    "channel",
    "canale",
    "page",
    "pagina",
    "profile",
    "press",
    "stampa",
    "media",
    "news",
    "newsroom",
    "di",
    "del",
    "della",
    "dei",
    "delle",
    "da",
    "a",
    "al",
    "alla",
    "alle",
    "the",
    "of",
    "and",
    "for",
}

_PERSON_ROLE_HINTS = {
    "en": {
        "president",
        "prime minister",
        "minister",
        "senator",
        "governor",
        "mayor",
        "ceo",
        "director",
        "spokesperson",
        "speaker",
        "professor",
        "doctor",
        "dr",
        "mr",
        "mrs",
        "ms",
    },
    "it": {
        "presidente",
        "primo ministro",
        "ministro",
        "senatore",
        "governatore",
        "sindaco",
        "amministratore delegato",
        "direttore",
        "portavoce",
        "professore",
        "dottore",
        "dott",
        "sig",
        "sigra",
        "signor",
        "signora",
    },
}


class SourceDiscoveryAgent:
    """Discover and collect evidence sources for each claim."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, state: PipelineState) -> PipelineState:
        """
        Input contract:  state.claims, state.cited_links, state.topic
        Output contract: state.evidence_items, state.sources_used
        """
        all_evidence: list[dict[str, Any]] = []
        all_sources: dict[str, dict[str, Any]] = {}
        language_key = self._language_key(state.language, state)
        state.language = language_key

        for claim in state.claims:
            strategy = get_discovery_strategy(claim.get("type", ""), state.topic)
            profile = self._build_discovery_profile(claim, state, language_key)
            base_queries = self._normalize_queries(
                build_queries(claim, state.topic, language_key),
                claim,
            )
            docs_queries = self._select_queries(base_queries, profile, channel="docs")
            context_queries = self._select_queries(base_queries, profile, channel="context")
            claim["_discovery_profile"] = profile
            target_sources: list[dict[str, Any]] = []
            social_probe = self._should_probe_official_social(claim, profile, state)

            if strategy.get("official_source", True):
                target_sources.extend(self._build_official_source_targets(claim, profile))
            if social_probe:
                target_sources.extend(self._build_official_social_targets(claim, profile))

            for target in target_sources:
                sid = target.get("source_id", "")
                if sid and sid not in all_sources:
                    all_sources[sid] = target

            claim["_discovery_targets"] = [
                target.get("source_name", "")
                for target in target_sources
                if target.get("source_name")
            ]
            claim["_discovery_targets"] = self._dedupe_preserve_order(claim["_discovery_targets"])

            logger.info(
                "    [%s] discovery priority=%s entity=%s kind=%s",
                claim["id"],
                profile["priority"],
                profile["anchor"] or "(none)",
                profile["entity_kind"],
            )
            logger.info(
                "    [%s] official queries: %s",
                claim["id"],
                profile["official_queries"],
            )
            logger.info(
                "    [%s] social queries: %s",
                claim["id"],
                profile["social_queries"],
            )
            logger.info(
                "    [%s] candidate targets: %s",
                claim["id"],
                claim["_discovery_targets"],
            )
            logger.info("    [%s] docs queries: %s", claim["id"], docs_queries)
            logger.info("    [%s] context queries: %s", claim["id"], context_queries)

            evidence_batch: list[dict[str, Any]] = []

            # 1. Google Fact Check
            if strategy.get("google_factcheck", True):
                try:
                    fc_results = await search_google_factcheck(
                        claim["claim"],
                        api_key=self.settings.google_factcheck_api_key,
                        language=state.language,
                    )
                    self._annotate_batch(
                        fc_results,
                        claim,
                        profile,
                        "google_factcheck",
                        query=claim["claim"],
                    )
                    evidence_batch.extend(fc_results)
                    logger.info("    [%s] Google FactCheck: %d results", claim["id"], len(fc_results))
                except Exception as exc:
                    logger.warning("    [%s] Google FactCheck FAILED: %s", claim["id"], exc)

            # 2. GDELT Context
            if strategy.get("gdelt_context", True) and context_queries:
                try:
                    ctx_results = await self._search_gdelt_context_queries(context_queries)
                    self._annotate_batch(
                        ctx_results,
                        claim,
                        profile,
                        "gdelt_context",
                        query_pool=context_queries,
                    )
                    evidence_batch.extend(ctx_results)
                    logger.info("    [%s] GDELT Context: %d results", claim["id"], len(ctx_results))
                except Exception as exc:
                    logger.warning("    [%s] GDELT Context FAILED: %s", claim["id"], exc)

            # 3. GDELT DOC
            if strategy.get("gdelt_doc", True) and docs_queries:
                try:
                    gdelt_results = await search_gdelt_docs(
                        docs_queries,
                        api_url=self.settings.gdelt_doc_api_url,
                    )
                    self._annotate_batch(
                        gdelt_results,
                        claim,
                        profile,
                        "gdelt_doc",
                        query_pool=docs_queries,
                    )
                    evidence_batch.extend(gdelt_results)
                    logger.info("    [%s] GDELT DOC: %d results", claim["id"], len(gdelt_results))
                except Exception as exc:
                    logger.warning("    [%s] GDELT DOC FAILED: %s", claim["id"], exc)

            # 4. Official source discovery
            if strategy.get("official_source", True) and profile["official_queries"]:
                try:
                    off_results = await self._search_gdelt_doc_queries(profile["official_queries"])
                    self._annotate_batch(
                        off_results,
                        claim,
                        profile,
                        "official_source",
                        query_pool=profile["official_queries"],
                    )
                    evidence_batch.extend(off_results)
                    logger.info("    [%s] Official sources: %d results", claim["id"], len(off_results))
                except Exception as exc:
                    logger.warning("    [%s] Official sources FAILED: %s", claim["id"], exc)

            # 5. Cited source mining (URL input)
            if state.cited_links and strategy.get("cited_source", True):
                try:
                    cited_results = await mine_cited_sources(state.cited_links, claim)
                    self._annotate_batch(
                        cited_results,
                        claim,
                        profile,
                        "cited_source",
                        query_pool=base_queries,
                    )
                    evidence_batch.extend(cited_results)
                    logger.info("    [%s] Cited sources: %d results", claim["id"], len(cited_results))
                except Exception as exc:
                    logger.warning("    [%s] Cited sources FAILED: %s", claim["id"], exc)

            # 6. Automatic official-social discovery via targeted search queries.
            if strategy.get("official_social", False) and social_probe and profile["social_queries"]:
                try:
                    social_results = await self._search_gdelt_context_queries(profile["social_queries"])
                    self._annotate_batch(
                        social_results,
                        claim,
                        profile,
                        "official_social",
                        query_pool=profile["social_queries"],
                    )
                    evidence_batch.extend(social_results)
                    logger.info(
                        "    [%s] Official social search targets: %s",
                        claim["id"],
                        profile["social_queries"],
                    )
                    logger.info("    [%s] Official social results: %d", claim["id"], len(social_results))
                except Exception as exc:
                    logger.warning("    [%s] Official social FAILED: %s", claim["id"], exc)

            evidence_batch = self._rank_evidence_batch(evidence_batch, claim, profile)
            logger.info("    [%s] TOTAL evidence for claim: %d items", claim["id"], len(evidence_batch))

            # Tag evidence with claim id
            for ev in evidence_batch:
                ev.setdefault("matched_claim_ids", [])
                if claim["id"] not in ev["matched_claim_ids"]:
                    ev["matched_claim_ids"].append(claim["id"])

            all_evidence.extend(evidence_batch)

            # Track unique sources
            for ev in evidence_batch:
                sid = ev.get("source_id", "")
                if sid and sid not in all_sources:
                    all_sources[sid] = {
                        "source_id": sid,
                        "source_name": ev.get("source_name", ""),
                        "source_type": ev.get("source_type", "news"),
                        "source_platform": ev.get("source_platform", ""),
                        "url": ev.get("url", ""),
                        "tier": ev.get("tier", "C"),
                        "published_at": ev.get("published_at", ""),
                        "discovery_score": ev.get("discovery_score", 0.0),
                        "discovery_channel": ev.get("discovery_channel", ""),
                        "discovery_reason": ev.get("discovery_reason", ""),
                        "source_role": ev.get("source_role", "retrieved"),
                        "source_role_rank": ev.get("source_role_rank", 2.0),
                    }
                elif sid:
                    existing = all_sources[sid]
                    existing["discovery_score"] = max(
                        existing.get("discovery_score", 0.0),
                        ev.get("discovery_score", 0.0),
                    )
                    if ev.get("discovery_channel"):
                        channels = set(existing.get("discovery_channels", []))
                        channels.add(ev["discovery_channel"])
                        existing["discovery_channels"] = sorted(channels)
                    if ev.get("discovery_reason"):
                        reasons = existing.get("discovery_reasons", [])
                        if ev["discovery_reason"] not in reasons:
                            reasons.append(ev["discovery_reason"])
                        existing["discovery_reasons"] = reasons
                    existing["source_role_rank"] = max(
                        existing.get("source_role_rank", 0.0),
                        ev.get("source_role_rank", 0.0),
                    )
                    if ev.get("source_platform") and not existing.get("source_platform"):
                        existing["source_platform"] = ev["source_platform"]
                    if ev.get("source_type") == "official":
                        existing["source_type"] = "official"

        # Rank globally so the best sources survive the cap.
        all_evidence = sorted(
            all_evidence,
            key=lambda ev: (
                ev.get("discovery_score", 0.0),
                self._tier_rank(ev.get("tier", "C")),
                ev.get("relevance_score", 0.0),
                ev.get("trust_score", 0.0),
            ),
            reverse=True,
        )

        # Cap evidence per request.
        state.evidence_items = all_evidence[: self.settings.max_evidence_per_claim * len(state.claims)]
        state.sources_used = sorted(
            all_sources.values(),
            key=lambda src: (
                src.get("source_role_rank", 0.0),
                src.get("discovery_score", 0.0),
                self._tier_rank(src.get("tier", "C")),
                src.get("published_at", ""),
            ),
            reverse=True,
        )
        return state

    def _normalize_queries(self, raw_queries: Any, claim: dict[str, Any]) -> list[str]:
        """Ensure discovery queries are clean strings to avoid connector crashes."""
        queries: list[str] = []
        if isinstance(raw_queries, list):
            for q in raw_queries:
                if isinstance(q, str):
                    q = q.strip()
                    if q:
                        queries.append(q)
                elif isinstance(q, dict):
                    q_claim = q.get("claim")
                    if isinstance(q_claim, str) and q_claim.strip():
                        queries.append(q_claim.strip())

        if not queries:
            fallback = str(claim.get("claim", "")).strip()
            if fallback:
                queries = [fallback]

        return self._dedupe_preserve_order(queries)[:3]

    def _build_discovery_profile(
        self,
        claim: dict[str, Any],
        state: PipelineState,
        language_key: str,
    ) -> dict[str, Any]:
        """Infer what kind of sources and accounts should be searched for a claim."""
        claim_type = str(claim.get("type", "")).strip().lower() or "event"
        anchor = self._anchor_text(claim)
        entity_kind = self._infer_entity_kind(anchor, claim, state.topic, language_key)
        evidence_hints = {
            self._normalize_for_match(str(item))
            for item in (claim.get("requires_evidence_type", []) or [])
            if str(item).strip()
        }
        priority = self._priority_for_claim(claim_type, entity_kind, state.topic, evidence_hints)
        official_queries = self._build_official_queries(anchor, claim, state.topic, language_key, entity_kind)
        social_queries = self._build_social_queries(anchor, claim, state.topic, language_key, entity_kind)
        return {
            "language": language_key,
            "claim_type": claim_type,
            "anchor": anchor,
            "topic": state.topic,
            "entity_kind": entity_kind,
            "priority": priority,
            "official_queries": official_queries,
            "social_queries": social_queries,
            "reason": self._profile_reason(claim_type, entity_kind, state.topic, anchor, priority),
        }

    def _select_queries(
        self,
        base_queries: list[str],
        profile: dict[str, Any],
        *,
        channel: str,
    ) -> list[str]:
        """Pick a small set of prioritized queries for a search channel."""
        base = self._dedupe_preserve_order(base_queries)
        official = profile.get("official_queries", [])
        social = profile.get("social_queries", [])
        priority = profile.get("priority", "general")

        if channel == "context":
            if priority == "context_first":
                ordered = social + base + official
            elif priority == "official_first":
                ordered = official + social + base
            else:
                ordered = social + official + base
        else:
            if priority == "official_first":
                ordered = official + base + social
            elif priority == "broad_coverage":
                ordered = base + official + social
            else:
                ordered = base + official + social

        return self._dedupe_preserve_order(ordered)[:3]

    async def _search_gdelt_context_queries(self, queries: list[str]) -> list[dict[str, Any]]:
        """Run GDELT context search for a small set of prioritized queries."""
        results: list[dict[str, Any]] = []
        for query in queries[:3]:
            try:
                results.extend(
                    await search_gdelt_context(
                        query,
                        api_url=self.settings.gdelt_context_api_url,
                    )
                )
            except Exception as exc:
                logger.warning("    GDELT context query failed for '%s': %s", query, exc)
        return results

    async def _search_gdelt_doc_queries(self, queries: list[str]) -> list[dict[str, Any]]:
        """Run GDELT DOC search for a small set of prioritized queries."""
        if not queries:
            return []
        try:
            return await search_gdelt_docs(
                queries[:3],
                api_url=self.settings.gdelt_doc_api_url,
            )
        except Exception as exc:
            logger.warning("    GDELT doc query batch failed: %s", exc)
            return []

    def _build_official_source_targets(
        self,
        claim: dict[str, Any],
        profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Build likely official source targets for the claim."""
        targets: list[dict[str, Any]] = []
        seen: set[str] = set()
        language_key = profile.get("language", "en")
        claim_type = profile.get("claim_type", "event")
        entity_kind = profile.get("entity_kind", "unknown")
        anchor = profile.get("anchor", "")
        topic = profile.get("topic", "")
        base = anchor or self._topic_fallback(topic, language_key) or claim.get("claim", "")[:60]

        def add(
            name: str,
            relevance: float,
            note: str,
            search_query: str,
            tier: str = "A",
            source_type: str = "official",
            source_role_rank: float = 1.0,
        ) -> None:
            record = self._make_target_source(
                name=name,
                source_type=source_type,
                tier=tier,
                relevance=relevance,
                note=note,
                search_target=base,
                search_query=search_query,
                source_role="official_target",
                source_role_rank=source_role_rank,
                source_platform="",
            )
            key = record["source_id"]
            if key in seen:
                return
            seen.add(key)
            targets.append(record)

        if claim_type in {"statistical", "regulatory", "institutional"}:
            if language_key == "it":
                add(
                    "ISTAT / Istituto Nazionale di Statistica",
                    0.97,
                    "Official statistics authority for Italian statistical claims",
                    f"{base} ISTAT dati ufficiali",
                )
                add(
                    "Gazzetta Ufficiale / Normattiva",
                    0.95,
                    "Official legal and regulatory source for Italian claims",
                    f"{base} Gazzetta Ufficiale Normattiva",
                )
                if self._normalize_for_match(topic) in {"economia", "economy", "finanza"}:
                    add(
                        "Banca d'Italia / central bank",
                        0.93,
                        "Monetary and macroeconomic authority relevant to the claim",
                        f"{base} Banca d'Italia dati ufficiali",
                    )
            else:
                add(
                    "National Statistics Office",
                    0.97,
                    "Official statistics authority for the claim",
                    f"{base} official statistics",
                )
                add(
                    "Official Legal / Regulatory Database",
                    0.95,
                    "Official legal and regulatory source for the claim",
                    f"{base} official gazette regulation",
                )
                if self._normalize_for_match(topic) in {"economy", "economia", "finance", "finanza"}:
                    add(
                        "Central Bank / Monetary Authority",
                        0.93,
                        "Monetary and macroeconomic authority relevant to the claim",
                        f"{base} central bank official data",
                    )

        if claim_type == "quote":
            if language_key == "it":
                add(
                    f"{base} dichiarazione ufficiale",
                    0.90,
                    "Official statement or transcript for a quoted claim",
                    f"{base} dichiarazione ufficiale",
                )
                add(
                    f"{base} ufficio stampa",
                    0.86,
                    "Press office or original source for the quote",
                    f"{base} ufficio stampa",
                )
            else:
                add(
                    f"{base} official statement",
                    0.90,
                    "Official statement or transcript for a quoted claim",
                    f"{base} official statement",
                )
                add(
                    f"{base} press office",
                    0.86,
                    "Press office or original source for the quote",
                    f"{base} press office",
                )

        if claim_type in {"causal", "technical", "historical"}:
            if language_key == "it":
                add(
                    f"{base} documentazione ufficiale",
                    0.88,
                    "Official documentation, archive or report for the claim",
                    f"{base} documentazione ufficiale",
                )
                add(
                    f"{base} archivio ufficiale",
                    0.84,
                    "Primary archive or historical record for the claim",
                    f"{base} archivio ufficiale",
                )
            else:
                add(
                    f"{base} official documentation",
                    0.88,
                    "Official documentation, archive or report for the claim",
                    f"{base} official documentation",
                )
                add(
                    f"{base} official archive",
                    0.84,
                    "Primary archive or historical record for the claim",
                    f"{base} official archive",
                )

        if entity_kind in {"institution", "company", "media", "person"}:
            if language_key == "it":
                add(
                    f"{base} pagina ufficiale",
                    0.89,
                    "Official website or institution page for the anchor entity",
                    f"{base} pagina ufficiale",
                )
                add(
                    f"{base} comunicato ufficiale",
                    0.87,
                    "Official communication or newsroom source for the anchor entity",
                    f"{base} comunicato ufficiale",
                )
            else:
                add(
                    f"{base} official page",
                    0.89,
                    "Official website or institution page for the anchor entity",
                    f"{base} official page",
                )
                add(
                    f"{base} press release",
                    0.87,
                    "Official communication or newsroom source for the anchor entity",
                    f"{base} press release",
                )

        return targets[:6]

    def _build_official_social_targets(
        self,
        claim: dict[str, Any],
        profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Build likely official social account targets for the claim."""
        targets: list[dict[str, Any]] = []
        seen: set[str] = set()
        language_key = profile.get("language", "en")
        entity_kind = profile.get("entity_kind", "unknown")
        anchor = profile.get("anchor", "")
        topic = profile.get("topic", "")
        base = anchor or self._topic_fallback(topic, language_key)
        if not base or entity_kind not in {"institution", "company", "person", "media"}:
            return targets

        slug = self._social_handle_slug(base)
        platforms = _SOCIAL_PLATFORM_HINTS.get(entity_kind, _SOCIAL_PLATFORM_HINTS["default"])

        def add(
            name: str,
            relevance: float,
            note: str,
            search_query: str,
            platform: str,
            tier: str = "B",
        ) -> None:
            record = self._make_target_source(
                name=name,
                source_type="social_official",
                tier=tier,
                relevance=relevance,
                note=note,
                search_target=base,
                search_query=search_query,
                source_role="official_social_target",
                source_role_rank=0.8,
                source_platform=platform,
            )
            key = record["source_id"]
            if key in seen:
                return
            seen.add(key)
            targets.append(record)

        for platform in platforms[:4]:
            if language_key == "it":
                add(
                    f"{base} account ufficiale {platform}",
                    0.78,
                    f"Official social account target on {platform}",
                    f"{base} account ufficiale {platform}",
                    platform,
                )
                add(
                    f"{base} profilo ufficiale {platform}",
                    0.76,
                    f"Official social profile target on {platform}",
                    f"{base} profilo ufficiale {platform}",
                    platform,
                )
            else:
                add(
                    f"{base} official {platform} account",
                    0.78,
                    f"Official social account target on {platform}",
                    f"{base} official {platform} account",
                    platform,
                )
                add(
                    f"{base} verified {platform} account",
                    0.76,
                    f"Verified social profile target on {platform}",
                    f"{base} verified {platform} account",
                    platform,
                )

            if slug:
                add(
                    f"@{slug} ({platform})",
                    0.80,
                    f"Handle-like social target derived from the entity name on {platform}",
                    f"@{slug} {platform}",
                    platform,
                )

        return targets[:6]

    def _make_target_source(
        self,
        *,
        name: str,
        source_type: str,
        tier: str,
        relevance: float,
        note: str,
        search_target: str,
        search_query: str,
        source_role: str,
        source_role_rank: float,
        source_platform: str,
    ) -> dict[str, Any]:
        """Create a placeholder record describing a discovered search target."""
        source_id = hashlib.md5(
            self._normalize_for_match(
                f"{source_role}:{source_type}:{name}:{search_target}:{source_platform}"
            ).encode()
        ).hexdigest()[:12]
        trust_score = self._clamp_float(
            0.65 if source_type == "social_official" else 0.82
        )
        if tier == "A":
            trust_score = max(trust_score, 0.85)
        return {
            "source_id": f"target_{source_id}",
            "source_name": name,
            "source_type": source_type,
            "source_platform": source_platform,
            "url": "",
            "tier": tier,
            "published_at": "",
            "stance": "neutral",
            "relevance_score": relevance,
            "trust_score": trust_score,
            "excerpt": note,
            "matched_claim_ids": [],
            "discovery_channel": source_role,
            "discovery_reason": note,
            "search_target": search_target,
            "search_query": search_query,
            "source_role": source_role,
            "source_role_rank": source_role_rank,
            "discovery_score": relevance,
        }

    def _social_handle_slug(self, text: str) -> str:
        """Build a compact slug that can be used as a social handle hint."""
        normalized = self._normalize_for_match(text)
        tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", normalized)
            if token and token not in _SOCIAL_HANDLE_STOPWORDS
        ]
        if not tokens:
            return ""
        return "".join(tokens)[:32]

    def _tier_rank(self, tier: str) -> int:
        """Return a numeric rank for source tiers so A outranks B and C."""
        return {"A": 3, "B": 2, "C": 1}.get(str(tier or "").upper(), 0)

    def _language_key(self, language: str, state: PipelineState) -> str:
        """Resolve the effective language for the discovery stage."""
        requested = str(language or "").strip().lower()
        if requested.startswith("it"):
            return "it"
        if requested.startswith("en"):
            return "en"

        resolved = resolve_language(
            language,
            text=" ".join(
                part
                for part in (
                    state.normalized_text,
                    state.raw_content,
                    state.article_title,
                    " ".join(str(claim.get("claim", "")) for claim in state.claims[:3]),
                )
                if part
            ),
            metadata=state.article_metadata,
        )
        return "it" if resolved.get("language") == "it" else "en"

    def _annotate_batch(
        self,
        evidence_batch: list[dict[str, Any]],
        claim: dict[str, Any],
        profile: dict[str, Any],
        channel: str,
        *,
        query: str = "",
        query_pool: list[str] | None = None,
    ) -> None:
        """Annotate retrieved evidence with discovery metadata and scoring."""
        for ev in evidence_batch:
            ev.setdefault("matched_claim_ids", [])
            ev.setdefault("discovery_channel", channel)
            ev.setdefault("source_role", "retrieved")
            ev.setdefault("source_role_rank", 2.0)
            if query:
                ev.setdefault("search_query", query)
            elif query_pool:
                ev.setdefault("search_query", query_pool[0])
            ev["discovery_reason"] = profile.get("reason", "")
            url = str(ev.get("url", "")).strip()
            if self._is_official_like_url(url):
                ev["source_type"] = "official"
                if channel in {"official_source", "cited_source"}:
                    ev["tier"] = "A"
            elif channel == "official_social" and self._is_social_domain(url):
                ev["source_type"] = "official"
                ev["source_platform"] = self._social_platform_from_url(url)
                ev["tier"] = "B" if ev.get("tier") != "A" else "A"
            ev["discovery_score"] = self._score_discovery_candidate(ev, claim, profile, channel)
            ev["search_target"] = profile.get("anchor", "") or profile.get("claim_type", "")

    def _rank_evidence_batch(
        self,
        evidence_batch: list[dict[str, Any]],
        claim: dict[str, Any],
        profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Sort evidence items so the strongest discovery candidates come first."""
        ranked = list(evidence_batch)
        for ev in ranked:
            if "discovery_score" not in ev:
                ev["discovery_score"] = self._score_discovery_candidate(
                    ev,
                    claim,
                    profile,
                    ev.get("discovery_channel", "gdelt_doc"),
                )
        ranked.sort(
            key=lambda ev: (
                ev.get("discovery_score", 0.0),
                self._tier_rank(ev.get("tier", "C")),
                ev.get("relevance_score", 0.0),
                ev.get("trust_score", 0.0),
            ),
            reverse=True,
        )
        return self._dedupe_evidence(ranked)

    def _score_discovery_candidate(
        self,
        evidence: dict[str, Any],
        claim: dict[str, Any],
        profile: dict[str, Any],
        channel: str,
    ) -> float:
        """Compute a discovery score describing how promising this source is."""
        source_type = str(evidence.get("source_type", "news")).lower()
        url = str(evidence.get("url", "")).strip()
        source_name = str(evidence.get("source_name", "")).strip()
        excerpt = str(evidence.get("excerpt", "")).strip()
        tier = str(evidence.get("tier", "C")).upper()

        type_score = self._source_type_weight(source_type)
        channel_score = self._channel_weight(channel)
        relevance = self._clamp_float(float(evidence.get("relevance_score", 0.5)))
        directness = self._estimate_directness_from_metadata(source_type, url, source_name, excerpt)
        recency = 0.65 if evidence.get("published_at") else 0.35
        match_bonus = self._match_bonus(evidence, claim, profile, channel)
        tier_bonus = {"A": 0.08, "B": 0.03, "C": -0.03}.get(tier, 0.0)

        score = (
            0.28 * type_score
            + 0.18 * channel_score
            + 0.20 * relevance
            + 0.16 * directness
            + 0.08 * recency
            + 0.10 * match_bonus
            + tier_bonus
        )
        return round(self._clamp_float(score), 3)

    def _match_bonus(
        self,
        evidence: dict[str, Any],
        claim: dict[str, Any],
        profile: dict[str, Any],
        channel: str,
    ) -> float:
        """Boost discovery score when the candidate matches the claim target well."""
        blob = self._normalize_for_match(
            " ".join(
                part
                for part in (
                    str(evidence.get("source_name", "")),
                    str(evidence.get("excerpt", "")),
                    str(evidence.get("url", "")),
                    str(evidence.get("search_query", "")),
                )
                if part
            )
        )
        anchor = self._normalize_for_match(profile.get("anchor", ""))
        topic = self._normalize_for_match(str(claim.get("topic", "")))
        claim_text = self._normalize_for_match(str(claim.get("claim", "")))
        bonus = 0.0

        if anchor and anchor in blob:
            bonus += 0.35
        if topic and topic in blob:
            bonus += 0.12
        if claim_text and claim_text[:40] and claim_text[:40] in blob:
            bonus += 0.18
        if channel == "official_social":
            bonus += 0.12 if self._is_social_domain(str(evidence.get("url", ""))) else 0.06
        if self._is_official_like_url(str(evidence.get("url", ""))):
            bonus += 0.12

        return min(1.0, bonus)

    def _estimate_directness_from_metadata(
        self,
        source_type: str,
        url: str,
        source_name: str,
        excerpt: str,
    ) -> float:
        """Estimate how directly a candidate answers the claim."""
        score = 0.35
        if source_type in {"official", "factcheck", "social_official"}:
            score += 0.35
        if self._is_official_like_url(url):
            score += 0.2
        if self._is_social_domain(url):
            score += 0.1
        if excerpt:
            score += 0.1
        if source_name:
            score += 0.05
        return self._clamp_float(score)

    def _source_type_weight(self, source_type: str) -> float:
        """Give each source type a broad reliability prior."""
        return {
            "official": 0.95,
            "factcheck": 0.92,
            "social_official": 0.72,
            "news": 0.65,
            "document": 0.58,
        }.get(source_type, 0.5)

    def _channel_weight(self, channel: str) -> float:
        """Weight channels based on how direct their retrieval path is."""
        return {
            "google_factcheck": 0.96,
            "official_source": 0.90,
            "official_social": 0.76,
            "gdelt_context": 0.74,
            "gdelt_doc": 0.68,
            "cited_source": 0.78,
        }.get(channel, 0.55)

    def _should_probe_official_social(
        self,
        claim: dict[str, Any],
        profile: dict[str, Any],
        state: PipelineState,
    ) -> bool:
        """Decide whether an official social search is worth probing."""
        entity_kind = profile.get("entity_kind", "unknown")
        claim_type = profile.get("claim_type", "")
        evidence_hints = {
            str(item).lower()
            for item in claim.get("requires_evidence_type", []) or []
        }

        if entity_kind not in {"institution", "company", "person", "media"}:
            return False
        if claim_type in {"quote", "institutional", "regulatory", "statistical"}:
            return True
        if claim_type in {"event", "causal", "technical"} and evidence_hints & {
            "official_statements",
            "original_source",
            "official_documents",
        }:
            return True
        topic = self._normalize_for_match(state.topic)
        if topic and any(t in topic for t in {"politic", "econom", "salute", "health", "defens", "difesa"}):
            return True
        return bool(profile.get("social_queries"))

    def _build_official_queries(
        self,
        anchor: str,
        claim: dict[str, Any],
        topic: str,
        language_key: str,
        entity_kind: str,
    ) -> list[str]:
        """Create official-source search queries from the claim target."""
        claim_type = str(claim.get("type", "")).strip().lower() or "event"
        hints = _OFFICIAL_QUERY_HINTS.get(language_key, _OFFICIAL_QUERY_HINTS["en"]).get(
            claim_type,
            _OFFICIAL_QUERY_HINTS.get(language_key, _OFFICIAL_QUERY_HINTS["en"])["event"],
        )
        queries: list[str] = []
        base = anchor or self._topic_fallback(topic, language_key)
        if base:
            for hint in hints:
                queries.append(f"{base} {hint}".strip())
        else:
            queries.extend(hints)

        if base and entity_kind in {"institution", "company", "person", "media"}:
            if language_key == "it":
                queries.extend(
                    [
                        f"{base} account ufficiale",
                        f"{base} profilo ufficiale",
                        f"{base} comunicato ufficiale",
                    ]
                )
            else:
                queries.extend(
                    [
                        f"{base} official account",
                        f"{base} verified account",
                        f"{base} official statement",
                    ]
                )
            slug = self._social_handle_slug(base)
            if slug:
                queries.extend(
                    [
                        f"@{slug}",
                        f"{base} @{slug}",
                    ]
                )

        if topic:
            topic_norm = self._normalize_for_match(topic)
            if topic_norm in {"economia", "economy", "finanza"}:
                queries.extend(["official statistics", "dati ufficiali", "central bank", "banca centrale"])
            elif topic_norm in {"politica", "politics"}:
                queries.extend(["government release", "comunicato governativo", "parliament record", "documenti parlamentari"])
            elif topic_norm in {"salute", "health"}:
                queries.extend(["health ministry", "ministero della salute", "official health data", "dati sanitari ufficiali"])

        return self._dedupe_preserve_order(queries)[:6]

    def _build_social_queries(
        self,
        anchor: str,
        claim: dict[str, Any],
        topic: str,
        language_key: str,
        entity_kind: str,
    ) -> list[str]:
        """Create social-account search queries from the claim target."""
        base = anchor or self._topic_fallback(topic, language_key)
        if not base:
            return []

        platforms = _SOCIAL_PLATFORM_HINTS.get(entity_kind, _SOCIAL_PLATFORM_HINTS["default"])
        queries: list[str] = []
        for platform in platforms:
            if language_key == "it":
                queries.extend(
                    [
                        f"{base} account ufficiale {platform}",
                        f"{base} profilo ufficiale {platform}",
                        f"{base} verificato {platform}",
                    ]
                )
            else:
                queries.extend(
                    [
                        f"{base} official account {platform}",
                        f"{base} verified {platform}",
                        f"{base} official {platform}",
                    ]
                )

        # If the claim is about an institution/company/person, also look for short
        # official-account style queries that are more likely to match indexed posts.
        if entity_kind in {"institution", "company", "person"}:
            if language_key == "it":
                queries.extend(
                    [
                        f"{base} account ufficiale",
                        f"{base} canale ufficiale",
                    ]
                )
            else:
                queries.extend(
                    [
                        f"{base} official account",
                        f"{base} official channel",
                    ]
                )
            slug = self._social_handle_slug(base)
            if slug:
                queries.extend(
                    [
                        f"@{slug}",
                        f"{base} @{slug}",
                    ]
                )

        return self._dedupe_preserve_order(queries)[:6]

    def _anchor_text(self, claim: dict[str, Any]) -> str:
        """Choose the best entity anchor for discovery queries."""
        parts = [
            str(claim.get("resolved_subject") or "").strip(),
            str(claim.get("subject") or "").strip(),
            str(claim.get("resolved_object") or "").strip(),
            str(claim.get("object") or "").strip(),
        ]
        for part in parts:
            if part and not self._is_pronoun_like(part):
                return part
        claim_text = str(claim.get("claim", "")).strip()
        entities = self._extract_entities(claim_text)
        return entities[0] if entities else ""

    def _infer_entity_kind(
        self,
        anchor: str,
        claim: dict[str, Any],
        topic: str,
        language_key: str,
    ) -> str:
        """Infer whether the search target is an institution, company, person, or media outlet."""
        text = self._normalize_for_match(
            " ".join(
                part
                for part in (
                    anchor,
                    str(claim.get("claim", "")),
                    topic,
                )
                if part
            )
        )

        if any(cue in text for cue in _INSTITUTION_CUES):
            return "institution"
        if any(cue in text for cue in _COMPANY_CUES):
            return "company"
        if any(cue in text for cue in _MEDIA_CUES):
            return "media"

        subject = self._normalize_for_match(str(claim.get("subject", "")))
        if self._looks_like_person(anchor, subject, text, language_key):
            return "person"

        if self._normalize_for_match(topic) in {"economia", "economy", "finanza", "politica", "politics", "salute", "health"}:
            return "institution"

        return "unknown"

    def _priority_for_claim(
        self,
        claim_type: str,
        entity_kind: str,
        topic: str,
        evidence_hints: set[str],
    ) -> str:
        """Choose whether the search should prioritize official, context, or broad coverage."""
        topic_norm = self._normalize_for_match(topic)
        if evidence_hints & {
            "official_statements",
            "official_statement",
            "official_documents",
            "official_document",
            "primary_source",
            "primary_sources",
            "official_data",
        }:
            return "official_first"
        if claim_type in {"statistical", "regulatory", "institutional"}:
            return "official_first"
        if claim_type == "quote":
            return "context_first"
        if claim_type == "causal":
            return "broad_coverage"
        if entity_kind in {"institution", "company"} and topic_norm in {"economia", "economy", "politica", "politics", "salute", "health", "difesa", "defense"}:
            return "official_first"
        if entity_kind == "person":
            return "context_first"
        return "broad_coverage"

    def _profile_reason(
        self,
        claim_type: str,
        entity_kind: str,
        topic: str,
        anchor: str,
        priority: str,
    ) -> str:
        """Build a short explanation for why this discovery profile was chosen."""
        topic_norm = self._normalize_for_match(topic) or "general"
        anchor_note = anchor or "topic"
        return f"{priority}:{claim_type}:{entity_kind}:{topic_norm}:{anchor_note}"

    def _topic_fallback(self, topic: str, language_key: str) -> str:
        """Generate a topic-based fallback anchor when the claim has no clear entity."""
        topic_norm = self._normalize_for_match(topic)
        if not topic_norm:
            return ""
        if language_key == "it":
            if topic_norm in {"economia", "economy", "finanza"}:
                return "dati ufficiali economia"
            if topic_norm in {"politica", "politics"}:
                return "governo parlamento"
            if topic_norm in {"salute", "health"}:
                return "ministero della salute"
            if topic_norm in {"difesa", "defense"}:
                return "ministero della difesa"
            if topic_norm in {"tecnologia", "technology"}:
                return "documentazione ufficiale tecnologia"
        else:
            if topic_norm in {"economia", "economy", "finanza"}:
                return "official economic data"
            if topic_norm in {"politica", "politics"}:
                return "government parliament"
            if topic_norm in {"salute", "health"}:
                return "health ministry"
            if topic_norm in {"difesa", "defense"}:
                return "defense ministry"
            if topic_norm in {"tecnologia", "technology"}:
                return "official technology documentation"
        return topic

    def _looks_like_person(self, anchor: str, subject: str, text: str, language_key: str) -> bool:
        """Heuristically decide whether the target looks like a person's name."""
        candidate = anchor or subject
        if not candidate:
            return False
        tokens = [token for token in re.split(r"\s+", candidate.strip()) if token]
        if not tokens or len(tokens) > 4:
            return False
        normalized = [self._normalize_for_match(token) for token in tokens]
        if any(token in _INSTITUTION_CUES or token in _COMPANY_CUES or token in _MEDIA_CUES for token in normalized):
            return False
        context = self._normalize_for_match(text)
        person_hints = _PERSON_ROLE_HINTS.get(language_key, set()) | _PERSON_ROLE_HINTS.get("en", set()) | _PERSON_ROLE_HINTS.get("it", set())
        if len(tokens) == 1 and any(hint in context for hint in person_hints):
            return True
        capitalized = sum(1 for token in tokens if token[:1].isupper())
        if capitalized >= 2:
            return True
        if language_key == "it" and normalized[0] in {"sig", "sigra", "dott", "prof"}:
            return True
        return False

    def _dedupe_evidence(self, evidence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicate evidence items by source id while preserving order."""
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in evidence_items:
            source_id = str(item.get("source_id", "")).strip()
            key = source_id or self._normalize_for_match(
                " ".join(
                    part
                    for part in (
                        str(item.get("source_name", "")),
                        str(item.get("url", "")),
                        str(item.get("excerpt", "")),
                    )
                    if part
                )
            )
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def _dedupe_preserve_order(self, items: list[str]) -> list[str]:
        """Remove duplicates from a string list while preserving the original order."""
        seen: set[str] = set()
        unique: list[str] = []
        for item in items:
            cleaned = " ".join(str(item).split()).strip()
            if not cleaned:
                continue
            key = self._normalize_for_match(cleaned)
            if key in seen:
                continue
            seen.add(key)
            unique.append(cleaned)
        return unique

    def _extract_entities(self, text: str) -> list[str]:
        """Extract a few candidate entities from the claim text."""
        if not text:
            return []
        candidates: list[str] = []
        for match in re.finditer(r"(?<![\w-])(?:[A-ZÀ-ÖØ-Ý][\w'’.-]*(?:\s+[A-ZÀ-ÖØ-Ý][\w'’.-]*)*)", text):
            candidate = " ".join(match.group(0).split())
            normalized = self._normalize_for_match(candidate)
            if not normalized:
                continue
            first = normalized.split()[0]
            if first in {"il", "la", "lo", "the", "a", "an", "di", "da"}:
                continue
            candidates.append(candidate)
        return self._dedupe_preserve_order(candidates)[:3]

    def _is_pronoun_like(self, text: str) -> bool:
        """Detect whether a text fragment is only a pronoun/reference."""
        normalized = self._normalize_for_match(text)
        if not normalized:
            return False
        pronouns = {
            "en": {"this", "that", "these", "those", "it", "he", "she", "they", "them", "which", "who", "whom"},
            "it": {"questo", "questa", "questi", "queste", "quello", "quella", "quelli", "quelle", "cio", "ciò", "lui", "lei", "loro", "essi", "esse"},
        }
        tokens = normalized.split()
        pool = pronouns["it"] | pronouns["en"]
        return normalized in pool or (tokens and tokens[0] in pool)

    def _is_official_like_url(self, url: str) -> bool:
        """Detect URLs that look like official or primary sources."""
        if not url:
            return False
        parsed = urlparse(url)
        host = self._normalize_for_match(parsed.netloc)
        path = self._normalize_for_match(parsed.path)
        if any(marker in host for marker in (".gov", ".edu", ".int", ".europa.eu")):
            return True
        if any(
            token in path
            for token in (
                "press",
                "press-release",
                "pressroom",
                "newsroom",
                "investor-relations",
                "official",
                "media",
                "communications",
                "comunicat",
                "stampa",
                "documenti",
                "document",
                "archive",
                "archiv",
            )
        ):
            return True
        return False

    def _is_social_domain(self, url: str) -> bool:
        """Detect common social media domains."""
        if not url:
            return False
        host = self._normalize_for_match(urlparse(url).netloc)
        return any(
            social in host
            for social in (
                "x.com",
                "twitter.com",
                "facebook.com",
                "instagram.com",
                "linkedin.com",
                "youtube.com",
                "tiktok.com",
                "threads.net",
                "telegram.me",
                "t.me",
            )
        )

    def _social_platform_from_url(self, url: str) -> str:
        """Infer the social platform from a URL."""
        if not url:
            return ""
        host = self._normalize_for_match(urlparse(url).netloc)
        mapping = {
            "x.com": "X",
            "twitter.com": "X",
            "facebook.com": "Facebook",
            "instagram.com": "Instagram",
            "linkedin.com": "LinkedIn",
            "youtube.com": "YouTube",
            "tiktok.com": "TikTok",
            "threads.net": "Threads",
            "telegram.me": "Telegram",
            "t.me": "Telegram",
        }
        for needle, platform in mapping.items():
            if needle in host:
                return platform
        return "social"

    def _normalize_for_match(self, text: str) -> str:
        """Lowercase and strip accents for resilient cue matching."""
        normalized = unicodedata.normalize("NFKD", text or "")
        stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return stripped.casefold()

    def _clamp_float(self, value: float) -> float:
        """Clamp a float to the [0, 1] range."""
        return max(0.0, min(1.0, value))
