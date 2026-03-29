"""LLM judge layer for whole-text verification with minimal guardrails."""

from __future__ import annotations

import logging
from typing import Any

from app.services.analysis.json_utils import parse_llm_json
from app.services.scoring.source_scoring import domain_from_url

logger = logging.getLogger(__name__)


CROSSCHECK_SYSTEM_TIER1 = """\
Sei un fact-checker rigoroso.

Riceverai:
- TESTO DA VERIFICARE: il contenuto completo da analizzare
- CLAIM ESTRATTI: affermazioni principali usate come contesto
- FONTI: risultati trovati sul web, soprattutto da fonti primarie o istituzionali

Il tuo compito:
- verificare il contenuto nel suo complesso
- usare i claim estratti solo come guida per leggere meglio il testo
- produrre un giudizio finale globale
- classificare ogni fonte come supporting, contradicting o neutral

Regole fondamentali:
- supporting solo se la fonte conferma davvero il fatto/predicato centrale
- se la fonte parla del soggetto ma non conferma il fatto, usa neutral
- se le fonti sono deboli o indirette, abbassa la confidence
- se non c'e evidenza diretta sufficiente, evita verdict troppo positivi
- scrivi tutti i campi di explanation in italiano
- non inventare informazioni non presenti nelle fonti
- l'explanation deve basarsi sui contenuti reali delle fonti fornite, non su frasi generiche
- in supporting_evidence e contradicting_evidence cita solo passaggi o fatti realmente presenti nelle fonti, indicando il numero della fonte quando utile
- non trattare una fonte irrilevante come contraddizione: se parla di un altro fatto, segnala che e irrilevante o non pertinente
- in source_analysis, per ogni fonte rilevante o mostrata, spiega brevemente se supporta, contraddice o e irrilevante rispetto al claim centrale
- evita caveat generici tipo "bisogna sempre verificare": usa solo limiti specifici del caso

Rispondi SOLO con JSON valido:
{
  "judgment_basis": {
    "main_claim_confirmed": <true|false>,
    "direct_support_level": "<none|weak|moderate|strong>",
    "contradiction_level": "<none|weak|moderate|strong>",
    "subject_only_match": <true|false>,
    "evidence_sufficiency": "<none|low|medium|high>",
    "source_agreement": "<low|medium|high>",
    "temporal_alignment": "<weak|medium|strong>"
  },
  "truth_score": <integer 0-100>,
  "confidence_score": <float 0.0-1.0>,
  "verdict": "<verified|mostly_verified|mixed|misleading|mostly_false|false|insufficient_evidence>",
  "explanation": {
    "summary": "<2-3 frasi in italiano>",
    "why": "<motivazione principale in italiano>",
    "supporting_evidence": ["<fatti o passaggi che supportano il testo>"],
    "contradicting_evidence": ["<fatti o passaggi che contraddicono il testo>"],
    "source_analysis": ["<una riga per fonte usata, in italiano>"],
    "temporal_context": "<contesto temporale se rilevante>",
    "caveats": ["<limiti della verifica>"]
  },
  "per_source": [
    {
      "source_index": <0-based>,
      "stance": "<supporting|contradicting|neutral>",
      "relevance": <0.0-1.0>,
      "key_excerpt": "<passaggio rilevante max 200 caratteri>"
    }
  ]
}"""


CROSSCHECK_SYSTEM_TIER2 = """\
Sei un fact-checker rigoroso.

Riceverai:
- TESTO DA VERIFICARE: il contenuto completo da analizzare
- CLAIM ESTRATTI: affermazioni principali usate come contesto
- FONTI: risultati trovati sul web da ricerca ampia (fonti locali, di nicchia o meno affidabili)

Il tuo compito:
- verificare il contenuto nel suo complesso
- usare i claim estratti come guida
- produrre un giudizio finale globale
- classificare ogni fonte come supporting, contradicting o neutral

Regole fondamentali:
- supporting solo se la fonte conferma davvero il fatto/predicato centrale
- se la fonte parla del soggetto ma non conferma il fatto, usa neutral
- queste fonti NON sono primarie: mantieni la confidence prudente
- scrivi tutti i campi di explanation in italiano
- evita verdict troppo positivi se le fonti sono deboli o non corroborate
- l'explanation deve basarsi sui contenuti reali delle fonti fornite, non su frasi generiche
- in supporting_evidence e contradicting_evidence cita solo passaggi o fatti realmente presenti nelle fonti, indicando il numero della fonte quando utile
- non trattare una fonte irrilevante come contraddizione: se parla di un altro fatto, segnala che e irrilevante o non pertinente
- in source_analysis, per ogni fonte rilevante o mostrata, spiega brevemente se supporta, contraddice o e irrilevante rispetto al claim centrale
- evita caveat generici tipo "bisogna sempre verificare": usa solo limiti specifici del caso

Rispondi SOLO con JSON valido:
{
  "judgment_basis": {
    "main_claim_confirmed": <true|false>,
    "direct_support_level": "<none|weak|moderate|strong>",
    "contradiction_level": "<none|weak|moderate|strong>",
    "subject_only_match": <true|false>,
    "evidence_sufficiency": "<none|low|medium|high>",
    "source_agreement": "<low|medium|high>",
    "temporal_alignment": "<weak|medium|strong>"
  },
  "truth_score": <integer 0-100>,
  "confidence_score": <float 0.0-0.65>,
  "verdict": "<verified|mostly_verified|mixed|misleading|mostly_false|false|insufficient_evidence>",
  "explanation": {
    "summary": "<2-3 frasi in italiano>",
    "why": "<motivazione principale in italiano>",
    "supporting_evidence": ["<fatti o passaggi che supportano il testo>"],
    "contradicting_evidence": ["<fatti o passaggi che contraddicono il testo>"],
    "source_analysis": ["<una riga per fonte usata, in italiano>"],
    "temporal_context": "<contesto temporale se rilevante>",
    "caveats": ["<limiti della verifica, includendo la debolezza delle fonti>"]
  },
  "per_source": [
    {
      "source_index": <0-based>,
      "stance": "<supporting|contradicting|neutral>",
      "relevance": <0.0-1.0>,
      "key_excerpt": "<passaggio rilevante max 200 caratteri>"
    }
  ]
}"""


class CrossCheckAnalysisLayer:
    """Run whole-text LLM judgment and return structured output."""

    def __init__(self, llm_client: Any) -> None:
        self.llm = llm_client

    async def run(
        self,
        text: str,
        results: list[dict[str, Any]],
        search_tier: str,
        claims: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        effective_claims = claims or [
            {"id": "c0", "claim": text[:500], "type": "other", "checkability_score": 0.50}
        ]
        prompt = self._build_prompt(text, results, search_tier, effective_claims)
        system_prompt = CROSSCHECK_SYSTEM_TIER1 if search_tier == "tier1" else CROSSCHECK_SYSTEM_TIER2

        try:
            raw = await self.llm.generate_text(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=2500,
                temperature=0.1,
            )
            parsed = parse_llm_json(raw)
            if isinstance(parsed, dict) and ("truth_score" in parsed or "judgment_basis" in parsed):
                return parsed
        except Exception as exc:
            logger.exception("    cross-check failed: %r", exc)
            raise

        raise RuntimeError("Cross-check returned no usable structured JSON")

    def _build_prompt(
        self,
        text: str,
        results: list[dict[str, Any]],
        search_tier: str,
        claims: list[dict[str, Any]],
    ) -> str:
        claims_block = self._build_claims_block(claims)
        sources_block = self._build_sources_block(results, search_tier)
        user_text = text[:5000]
        return (
            f"TESTO DA VERIFICARE:\n\"\"\"\n{user_text}\n\"\"\"\n\n"
            f"CLAIM ESTRATTI (contesto):\n{claims_block}\n\n"
            f"FONTI TROVATE SUL WEB:\n{sources_block}\n\n"
            "Produci il giudizio finale in JSON."
        )

    def _build_claims_block(self, claims: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for claim in claims[:10]:
            lines.append(f'- {claim.get("id", "")}: {claim.get("claim", "")}')
        return "\n".join(lines)

    def _build_sources_block(
        self,
        results: list[dict[str, Any]],
        search_tier: str,
    ) -> str:
        blocks: list[str] = []
        for index, result in enumerate(results):
            domain = domain_from_url(result.get("url", ""))
            tier_tag = "PRIMARIA" if result.get("_tier") != "tier2" and search_tier != "tier2" else "AMPIA"
            body = (result.get("raw_content") or result.get("content") or "")[:2000]
            blocks.append(
                f"\n--- FONTE {index} [{domain}] ({tier_tag}) ---\n"
                f"Titolo: {result.get('title', '')}\n"
                f"URL: {result.get('url', '')}\n"
                f"Contenuto:\n{body}\n"
            )
        return "".join(blocks)

    def _fallback(self, results: list[dict[str, Any]], search_tier: str) -> dict[str, Any]:
        if not results:
            return {
                "judgment_basis": {
                    "main_claim_confirmed": False,
                    "direct_support_level": "none",
                    "contradiction_level": "none",
                    "subject_only_match": False,
                    "evidence_sufficiency": "none",
                    "source_agreement": "low",
                    "temporal_alignment": "weak",
                },
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

        avg = sum(result.get("score", 0.5) for result in results) / len(results)
        truth_score = max(0, min(100, int(avg * 80 + 10)))
        confidence = round(min(len(results) / 5, 1.0) * 0.6, 2)
        if search_tier == "tier2":
            confidence = min(confidence, 0.65)
        verdict = "mixed" if truth_score >= 50 else "insufficient_evidence"
        return {
            "judgment_basis": {
                "main_claim_confirmed": False,
                "direct_support_level": "weak" if avg >= 0.65 else "none",
                "contradiction_level": "none",
                "subject_only_match": False,
                "evidence_sufficiency": "medium" if len(results) >= 3 else "low",
                "source_agreement": "medium" if len(results) >= 3 else "low",
                "temporal_alignment": "weak",
            },
            "truth_score": truth_score,
            "confidence_score": confidence,
            "verdict": verdict,
            "explanation": {
                "summary": f"Analisi di fallback costruita su {len(results)} fonti.",
                "why": "Il modello LLM non era disponibile, quindi e stato usato un riepilogo deterministico.",
                "supporting_evidence": [],
                "contradicting_evidence": [],
                "source_analysis": [
                    f"{domain_from_url(result.get('url', ''))}: score Tavily {result.get('score', 0):.2f}"
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
