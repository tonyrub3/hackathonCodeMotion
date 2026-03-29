"""Agent 2 - claim-centric decomposition for short statements and long URLs."""

from __future__ import annotations

import json
import logging
import re

from app.config import Settings
from app.connectors.regolo_client import RegoloClient
from app.core.state import PipelineState

from ._agent_utils import detect_recent_claim, infer_claim_type, split_sentences, stable_id

logger = logging.getLogger(__name__)


CLAIM_DECOMPOSITION_SYSTEM = """\
You decompose a statement or article into atomic fact-checkable claims.
Rules:
- keep only verifiable factual claims
- skip opinions, rhetorical text, and repeated statements
- one claim per item
- return JSON only
Schema:
{
  "claims": [
    {
      "claim": "...",
      "type": "event|statistical|institutional|quote|causal",
      "checkability_score": 0.0-1.0
    }
  ]
}"""


class ClaimDecompositionAgent:
    """Decompose the normalized text into claims with a safe heuristic fallback."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = RegoloClient(
            api_key=settings.regolo_api_key,
            base_url=settings.regolo_base_url,
            llm_model=settings.regolo_model,
        )

    async def run(self, state: PipelineState) -> PipelineState:
        text = state.normalized_text or state.raw_content
        if not text.strip():
            state.claims = []
            return state

        claims = await self._llm_claims(text)
        if not claims:
            claims = self._heuristic_claims(text)

        claims = claims[: self.settings.max_claims_per_request]
        state.claims = [
            {
                "id": f"c{i+1}",
                "claim": claim["claim"],
                "type": claim["type"],
                "checkability_score": claim["checkability_score"],
                "time_sensitive": detect_recent_claim(claim["claim"]),
            }
            for i, claim in enumerate(claims)
        ]
        state.layer_outputs["claim_decomposition"] = {
            "claim_count": len(state.claims),
            "claims": state.claims,
        }
        logger.info("    decomposed into %d claim(s)", len(state.claims))
        return state

    async def _llm_claims(self, text: str) -> list[dict[str, object]]:
        if not self.settings.regolo_api_key:
            return []
        snippet = text[:3500]
        try:
            raw = await self.llm.generate_text(
                prompt=f'Text:\n"""\n{snippet}\n"""',
                system_prompt=CLAIM_DECOMPOSITION_SYSTEM,
                max_tokens=900,
                temperature=0.1,
            )
            payload = self._extract_json(raw)
        except Exception as exc:
            logger.warning("    claim decomposition LLM failed: %s", exc)
            return []

        claims = payload.get("claims", []) if isinstance(payload, dict) else []
        out: list[dict[str, object]] = []
        for item in claims:
            if not isinstance(item, dict):
                continue
            claim = str(item.get("claim", "")).strip()
            if len(claim) < 8:
                continue
            out.append(
                {
                    "claim": claim,
                    "type": str(item.get("type", infer_claim_type(claim))),
                    "checkability_score": float(item.get("checkability_score", 0.65)),
                }
            )
        return out

    def _heuristic_claims(self, text: str) -> list[dict[str, object]]:
        sentences = split_sentences(text)
        if not sentences:
            sentences = [text.strip()]
        claims: list[dict[str, object]] = []
        seen: set[str] = set()
        for sentence in sentences:
            normalized = re.sub(r"\s+", " ", sentence).strip()
            if len(normalized) < 8:
                continue
            key = stable_id("claim", normalized)
            if key in seen:
                continue
            seen.add(key)
            claims.append(
                {
                    "claim": normalized,
                    "type": infer_claim_type(normalized),
                    "checkability_score": 0.8 if any(ch.isdigit() for ch in normalized) else 0.65,
                }
            )
        return claims or [{"claim": text.strip(), "type": infer_claim_type(text), "checkability_score": 0.6}]

    def _extract_json(self, raw: str) -> dict:
        raw = (raw or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    return {}
        return {}
