"""Agent 3 - query planning with LLM-assisted retrieval hints."""

from __future__ import annotations

import json
import logging
import re

from app.config import Settings
from app.connectors.regolo_client import RegoloClient
from app.core.state import PipelineState

from ._agent_utils import normalize_text

logger = logging.getLogger(__name__)


QUERY_PLANNING_SYSTEM = """\
You are a retrieval planner for fact-checking.
Generate up to 4 short search queries for the claim.
Rules:
- prioritize entities, dates, numbers, locations, official names
- include one literal query close to the claim
- include one broader disambiguation query
- return JSON only
Schema:
{
  "queries": ["...", "..."]
}"""


class QueryPlanningAgent:
    """Generate per-claim search plans."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = RegoloClient(
            api_key=settings.regolo_api_key,
            base_url=settings.regolo_base_url,
            llm_model=settings.regolo_model,
        )

    async def run(self, state: PipelineState) -> PipelineState:
        plans: list[dict[str, object]] = []
        for claim in state.claims:
            queries = await self._llm_queries(claim["claim"])
            if not queries:
                queries = self._fallback_queries(claim["claim"], state.article_title)
            plan = {
                "claim_id": claim["id"],
                "claim": claim["claim"],
                "queries": queries[:4],
            }
            plans.append(plan)
        state.query_plan = plans
        state.layer_outputs["query_planning"] = {"plans": plans}
        logger.info("    query plans: %d", len(plans))
        return state

    async def _llm_queries(self, claim_text: str) -> list[str]:
        if not self.settings.regolo_api_key:
            return []
        try:
            raw = await self.llm.generate_text(
                prompt=f'Claim:\n"""\n{claim_text}\n"""',
                system_prompt=QUERY_PLANNING_SYSTEM,
                max_tokens=250,
                temperature=0.1,
            )
            payload = self._extract_json(raw)
            queries = payload.get("queries", []) if isinstance(payload, dict) else []
            return [str(item).strip() for item in queries if str(item).strip()]
        except Exception as exc:
            logger.warning("    query planner LLM failed: %s", exc)
            return []

    def _fallback_queries(self, claim_text: str, article_title: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", claim_text).strip()
        keywords = normalize_text(claim_text).split()[:8]
        broader = " ".join(keywords[:5])
        queries = [normalized]
        if broader and broader.lower() != normalized.lower():
            queries.append(broader)
        if article_title:
            queries.append(f"{article_title} {broader}".strip())
        queries.append(f'"{claim_text[:120]}"')
        deduped: list[str] = []
        seen: set[str] = set()
        for query in queries:
            key = query.lower()
            if query and key not in seen:
                seen.add(key)
                deduped.append(query)
        return deduped

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
