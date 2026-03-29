"""LLM cross-check layer for whole-text verification."""

from __future__ import annotations

import logging
from typing import Any

from app.services.analysis.json_utils import parse_llm_json
from app.services.scoring.source_scoring import domain_from_url

logger = logging.getLogger(__name__)


CROSSCHECK_SYSTEM_TIER1 = """\
You are a rigorous fact-checker. You will receive:
- TEXT: the full article or statement to verify
- SOURCES: evidence from PRIMARY/INSTITUTIONAL web sources

Your job: compare the TEXT against the SOURCES and determine the overall truthfulness.
Analyze the text AS A WHOLE — do NOT split it into individual claims.
Check every verifiable fact (names, numbers, dates, events) against the sources.
If some facts are confirmed and others are not, reflect that in the score.
Write every field inside "explanation" in Italian.

Respond with ONLY valid JSON (no markdown, no extra text):
{
  "truth_score": <integer 0-100>,
  "confidence_score": <float 0.0-1.0>,
  "verdict": "<verified|mostly_verified|mixed|misleading|mostly_false|false|insufficient_evidence>",
  "explanation": {
    "summary": "<2-3 sentence overall verdict>",
    "why": "<main reasons for the verdict>",
    "supporting_evidence": ["<facts confirmed by sources>"],
    "contradicting_evidence": ["<facts contradicted by sources>"],
    "source_analysis": ["<one-line assessment per source used>"],
    "temporal_context": "<time-related context if relevant>",
    "caveats": ["<limitations>"]
  },
  "per_source": [
    {
      "source_index": <0-based>,
      "stance": "<supporting|contradicting|neutral>",
      "relevance": <0.0-1.0>,
      "key_excerpt": "<most relevant quote, max 200 chars>"
    }
  ]
}"""


CROSSCHECK_SYSTEM_TIER2 = """\
You are a rigorous fact-checker. You will receive:
- TEXT: the full article or statement to verify
- SOURCES: evidence from BROAD web search (local newspapers, niche sites, blogs, lesser-known outlets)

Your job: compare the TEXT against the SOURCES and determine the overall truthfulness.
Analyze the text AS A WHOLE — do NOT split it into individual claims.

Because these are NOT primary sources, also evaluate each source's tone:
- Factual news report (dateline, quotes, attribution) → more reliable
- Opinion/editorial/blog → less reliable
- Local outlet covering a local event → can be reliable for local facts
Write every field inside "explanation" in Italian.

Confidence rules:
- Cap confidence_score at 0.65 max (only non-primary sources available)
- ALWAYS add this caveat: "Confirmed by local/sector sources only; not yet corroborated by major media."

Respond with ONLY valid JSON (no markdown, no extra text):
{
  "truth_score": <integer 0-100>,
  "confidence_score": <float 0.0-0.65>,
  "verdict": "<verified|mostly_verified|mixed|misleading|mostly_false|false|insufficient_evidence>",
  "explanation": {
    "summary": "<2-3 sentence verdict — mention source tier>",
    "why": "<main reasons, noting source quality>",
    "supporting_evidence": ["<facts confirmed>"],
    "contradicting_evidence": ["<facts contradicted>"],
    "source_analysis": ["<per source: name, type, tone, reliability>"],
    "temporal_context": "<time context>",
    "caveats": ["Confirmed by local/sector sources only; not yet corroborated by major media."]
  },
  "per_source": [
    {
      "source_index": <0-based>,
      "stance": "<supporting|contradicting|neutral>",
      "relevance": <0.0-1.0>,
      "key_excerpt": "<most relevant quote, max 200 chars>"
    }
  ]
}"""
class CrossCheckAnalysisLayer:
    """Run whole-text cross-check and provide a deterministic fallback."""

    def __init__(self, llm_client: Any) -> None:
        self.llm = llm_client

    async def run(
        self,
        text: str,
        results: list[dict[str, Any]],
        search_tier: str,
    ) -> dict[str, Any]:
        prompt = self.build_prompt(text, results, search_tier)
        system_prompt = CROSSCHECK_SYSTEM_TIER1 if search_tier == "tier1" else CROSSCHECK_SYSTEM_TIER2

        try:
            raw = await self.llm.generate_text(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=2000,
                temperature=0.1,
            )
            parsed = parse_llm_json(raw)
            if isinstance(parsed, dict) and "truth_score" in parsed:
                return parsed
        except Exception as exc:
            logger.error("    cross-check failed: %s", exc)

        return self.fallback(results)

    def build_prompt(
        self,
        text: str,
        results: list[dict[str, Any]],
        search_tier: str,
    ) -> str:
        sources_block = self.build_sources_block(results, search_tier)
        user_text = text[:4000]
        return (
            f"TEXT TO VERIFY:\n\"\"\"\n{user_text}\n\"\"\"\n\n"
            f"SOURCES FROM WEB SEARCH:\n{sources_block}\n\n"
            "Produce your fact-check verdict as JSON."
        )

    def build_sources_block(
        self,
        results: list[dict[str, Any]],
        search_tier: str,
    ) -> str:
        blocks: list[str] = []
        for index, result in enumerate(results):
            domain = domain_from_url(result.get("url", ""))
            tier_tag = "PRIMARY" if result.get("_tier") != "tier2" and search_tier != "tier2" else "BROAD"
            body = (result.get("raw_content") or result.get("content") or "")[:2000]
            blocks.append(
                f"\n--- SOURCE {index} [{domain}] ({tier_tag}) ---\n"
                f"Title: {result.get('title', '')}\n"
                f"URL: {result.get('url', '')}\n"
                f"Content:\n{body}\n"
            )
        return "".join(blocks)

    def fallback(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        if not results:
            return {
                "truth_score": 0,
                "confidence_score": 0.0,
                "verdict": "insufficient_evidence",
                "explanation": {
                    "summary": "Impossibile verificare: nessuna fonte disponibile.",
                    "why": "La ricerca non ha restituito risultati utili.",
                    "supporting_evidence": [],
                    "contradicting_evidence": [],
                    "source_analysis": [],
                    "temporal_context": "",
                    "caveats": ["Analisi LLM non disponibile."],
                },
                "per_source": [],
            }

        average_score = sum(result.get("score", 0.5) for result in results) / len(results)
        truth_score = max(0, min(100, int(average_score * 80 + 10)))
        verdict = "false"
        for threshold, candidate in [
            (85, "verified"),
            (70, "mostly_verified"),
            (55, "mixed"),
            (40, "misleading"),
            (25, "mostly_false"),
            (0, "false"),
        ]:
            if truth_score >= threshold:
                verdict = candidate
                break

        return {
            "truth_score": truth_score,
            "confidence_score": round(min(len(results) / 5, 1.0) * 0.6, 2),
            "verdict": verdict,
            "explanation": {
                "summary": f"Analisi di fallback costruita su {len(results)} fonti.",
                "why": "Il modello LLM non era disponibile, quindi e stato usato un riepilogo deterministico.",
                "supporting_evidence": [],
                "contradicting_evidence": [],
                "source_analysis": [
                    f"{domain_from_url(result.get('url', ''))}: {result.get('score', 0):.2f}"
                    for result in results
                ],
                "temporal_context": "",
                "caveats": ["Punteggio prodotto in modalita di fallback."],
            },
            "per_source": [
                {
                    "source_index": index,
                    "stance": "neutral",
                    "relevance": result.get("score", 0.5),
                    "key_excerpt": "",
                }
                for index, result in enumerate(results)
            ],
        }
