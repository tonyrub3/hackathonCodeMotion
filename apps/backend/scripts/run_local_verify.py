"""Quick script to test the verify endpoint locally."""

import asyncio
import json
from app.config import load_settings
from app.core.orchestrator import Orchestrator


async def main():
    settings = load_settings()
    orchestrator = Orchestrator(settings)

    # Example text input
    state = await orchestrator.verify(
        content="The inflation rate in Italy reached 2% in 2026, according to ISTAT.",
        input_type="text",
        language="en",
        topic="economy",
    )

    print(json.dumps({
        "verdict": state.verdict,
        "truth_score": state.truth_score,
        "confidence": state.confidence_score,
        "claims": len(state.claims),
        "evidence": len(state.scored_evidence),
        "errors": state.errors,
        "timings": state.timings,
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
