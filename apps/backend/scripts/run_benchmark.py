"""Script to run FEVER benchmark evaluation."""

import asyncio
import json
from app.config import load_settings
from app.services.benchmark.fever_loader import load_fever_claims
from app.services.benchmark.fever_mapper import verdict_to_fever_label
from app.services.benchmark.fever_verdict_eval import evaluate_verdicts
from app.core.pipeline_benchmark import run_benchmark_claim


async def main():
    settings = load_settings()
    claims = load_fever_claims(f"{settings.fever_data_dir}/dev.jsonl", limit=20)

    predictions = []
    for claim in claims:
        state = await run_benchmark_claim(claim["claim"], settings)
        predictions.append({
            "claim_id": claim["id"],
            "verdict": state.verdict,
        })
        print(f"  [{claim['label']}] -> [{state.verdict}] {claim['claim'][:60]}")

    gold = [{"claim_id": c["id"], "label": c["label"]} for c in claims]
    result = evaluate_verdicts(predictions, gold)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
