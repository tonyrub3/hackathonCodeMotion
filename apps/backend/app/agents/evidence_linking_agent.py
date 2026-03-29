"""Agent 6 - link claims to passages and classify evidence type."""

from __future__ import annotations

import logging

from app.config import Settings
from app.core.state import PipelineState

from ._agent_utils import contradiction_hit, domain_from_url, overlap_ratio, split_sentences, temporal_alignment_score, tokenize

logger = logging.getLogger(__name__)


class EvidenceLinkingAgent:
    """Classify passages as direct/indirect/context/irrelevant for each claim."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, state: PipelineState) -> PipelineState:
        linked: list[dict[str, object]] = []
        for source in state.selected_sources:
            text = source.get("raw_content") or source.get("snippet") or source.get("title") or ""
            chunks = self._candidate_chunks(str(text))
            if not chunks:
                chunks = [str(text)[:500]]

            for claim in state.claims:
                best = self._best_chunk_for_claim(claim, source, chunks, state)
                if best:
                    linked.append(best)

        state.evidence_items = linked
        state.layer_outputs["evidence_linking"] = {
            "evidence_items": linked,
        }
        logger.info("    evidence linked: %d item(s)", len(linked))
        return state

    def _candidate_chunks(self, text: str) -> list[str]:
        sentences = split_sentences(text)
        if not sentences:
            return []
        chunks: list[str] = []
        current: list[str] = []
        for sentence in sentences:
            current.append(sentence)
            if len(" ".join(current)) > 280 or len(current) >= 2:
                chunks.append(" ".join(current))
                current = []
        if current:
            chunks.append(" ".join(current))
        return chunks[:8]

    def _best_chunk_for_claim(
        self,
        claim: dict,
        source: dict,
        chunks: list[str],
        state: PipelineState,
    ) -> dict[str, object] | None:
        language = state.language if state.language in {"it", "en"} else "en"
        claim_tokens = tokenize(claim["claim"], language)
        best: dict[str, object] | None = None
        best_overlap = 0.0
        for chunk in chunks:
            chunk_tokens = tokenize(chunk, language)
            overlap = overlap_ratio(claim_tokens, chunk_tokens)
            if overlap > best_overlap:
                best_overlap = overlap
                best = {
                    "source_id": source["source_id"],
                    "url": source["url"],
                    "source_name": source.get("source_name") or domain_from_url(source["url"]),
                    "source_type": "web",
                    "tier": source.get("tier", "C"),
                    "claim_id": claim["id"],
                    "claim": claim["claim"],
                    "excerpt": chunk[:500],
                    "tavily_score": float(source.get("score", 0.0)),
                    "overlap": overlap,
                    "forensic_score": float(source.get("forensic_score", 0.5)),
                    "published_at": source.get("published_at", ""),
                    "temporal_alignment": temporal_alignment_score(claim, source.get("published_at", "")),
                }

        if not best:
            return None
        overlap = float(best["overlap"])
        if overlap >= 0.62:
            evidence_type = "direct"
        elif overlap >= 0.38:
            evidence_type = "indirect"
        elif overlap >= 0.18:
            evidence_type = "context"
        else:
            evidence_type = "irrelevant"

        stance = "neutral"
        if evidence_type == "direct":
            stance = "contradicting" if contradiction_hit(str(best["excerpt"]), language) else "supporting"
        elif evidence_type == "indirect" and contradiction_hit(str(best["excerpt"]), language):
            stance = "contradicting"

        best["evidence_type"] = evidence_type
        best["stance"] = stance
        best["matched_claim_ids"] = [claim["id"]]
        best["relevance_score"] = round(overlap, 3)
        best["evidence_score"] = round(
            min(
                1.0,
                0.45 * overlap
                + 0.25 * float(best["forensic_score"])
                + 0.20 * float(best["tavily_score"])
                + 0.10 * float(best["temporal_alignment"]),
            ),
            3,
        )
        return best
