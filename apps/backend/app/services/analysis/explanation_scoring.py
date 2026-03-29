"""LLM-based scoring derived from the explanation text."""

from __future__ import annotations

import logging
from typing import Any

from app.services.analysis.json_utils import parse_llm_json

logger = logging.getLogger(__name__)


EXPLANATION_SCORING_SYSTEM = """\
Sei un calibratore di fact-checking.

Riceverai SOLO l'explanation strutturata prodotta dal fact-checker.
Il tuo compito e trasformarla in un giudizio numerico coerente.

Regole:
- basa il punteggio solo su cio che l'explanation afferma davvero
- se l'explanation dice che le fonti non confermano il claim principale, NON produrre verdict positivi
- se l'explanation parla solo del soggetto ma non del fatto, considera il caso come insufficient_evidence o al massimo mixed
- usa un tono prudente: la confidence deve riflettere quanta evidenza viene descritta
- non inventare fatti aggiuntivi

Rispondi SOLO con JSON valido:
{
  "truth_score": <float 0-100>,
  "confidence_score": <float 0.0-1.0>,
  "verdict": "<verified|mostly_verified|mixed|misleading|mostly_false|false|insufficient_evidence>",
  "reasoning": "<breve frase tecnica in italiano sul perche del punteggio>"
}
"""


class ExplanationScoringLayer:
    """Ask an LLM to derive numeric scoring from the explanation."""

    def __init__(self, llm_client: Any) -> None:
        self.llm = llm_client

    async def run(
        self,
        explanation: dict[str, Any] | None,
        *,
        search_tier: str,
    ) -> dict[str, Any]:
        if not explanation:
            raise RuntimeError("Explanation scoring requires a non-empty explanation")

        prompt = self._build_prompt(explanation, search_tier=search_tier)
        try:
            raw = await self.llm.generate_text(
                prompt=prompt,
                system_prompt=EXPLANATION_SCORING_SYSTEM,
                max_tokens=500,
                temperature=0.0,
            )
            parsed = parse_llm_json(raw)
            if isinstance(parsed, dict) and {"truth_score", "confidence_score", "verdict"}.issubset(parsed.keys()):
                return parsed
        except Exception as exc:
            logger.exception("explanation scoring failed: %r", exc)
            raise
        raise RuntimeError("Explanation scoring returned no usable structured JSON")

    def _build_prompt(self, explanation: dict[str, Any], *, search_tier: str) -> str:
        return (
            f"TIER DI RICERCA: {search_tier}\n\n"
            f"SUMMARY: {explanation.get('summary', '')}\n"
            f"WHY: {explanation.get('why', '')}\n"
            f"SUPPORTING_EVIDENCE: {explanation.get('supporting_evidence', [])}\n"
            f"CONTRADICTING_EVIDENCE: {explanation.get('contradicting_evidence', [])}\n"
            f"SOURCE_ANALYSIS: {explanation.get('source_analysis', [])}\n"
            f"TEMPORAL_CONTEXT: {explanation.get('temporal_context', '')}\n"
            f"CAVEATS: {explanation.get('caveats', [])}\n"
        )
