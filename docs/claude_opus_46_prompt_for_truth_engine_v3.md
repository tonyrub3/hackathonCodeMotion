# Prompt for Claude Opus 4.6 — Implement Truth Engine MVP (Auto-Discovery Version)

Use the attached markdown specification file named:

`truth_engine_complete_coding_spec_v3.md`

Your job is to act as a **senior staff engineer + solution architect** and generate the first production-grade MVP implementation of the project described there.

## What I need from you

Read the markdown spec carefully and follow it strictly.

I want you to:

1. **Summarize the architecture briefly**
2. **Generate the repository skeleton**
3. **Generate the backend first**
4. **Generate the shared schemas and models**
5. **Generate the core pipeline/orchestrator**
6. **Generate the agent interfaces and tool interfaces**
7. **Generate the discovery layer**
8. **Generate the scoring modules**
9. **Generate the `/verify` endpoint**
10. **Generate a minimal frontend**
11. **Explain every important implementation choice**

## Critical implementation rules

You must follow these rules:

- The final verdict must **not** be decided only by the LLM
- The system must use:
  - claim decomposition
  - automatic source discovery
  - source reliability scoring
  - evidence scoring
  - truth score
  - structured explanation
- If input is a URL, include:
  - article extraction
  - site forensics
  - citation/source extraction from the article
- FEVER must be included as **benchmark mode**
- GDELT and Google Fact Check must be treated as **retrieval/matching connectors**, not as the proprietary truth engine
- Regolo must be used only where appropriate:
  - claim decomposition
  - embeddings
  - rerank
  - optional semantic normalization
- **Do not rely on a manual whitelist of trusted sites**
- You may use **discovery heuristics and pattern files**, but not a static `sources.json` of pre-approved domains

## Output format I want from you

Work in this order:

### Phase 1 — Architecture summary
Explain:
- modules
- agent responsibilities
- tool responsibilities
- data flow
- where deterministic logic lives
- where LLM inference lives
- how automatic source discovery works without a manual trusted-site registry

### Phase 2 — Repository scaffold
Generate the complete folder/file tree.

### Phase 3 — Backend foundation
Generate:
- `main.py`
- `config.py`
- `routes_verify.py`
- `routes_health.py`
- `orchestrator.py`
- `state.py`

### Phase 4 — Models and schemas
Generate:
- request/response models
- claim models
- evidence models
- source models
- site forensics models
- benchmark models

Use Pydantic.

### Phase 5 — Core agents
Generate minimal but working versions of:
- `input_normalizer_agent.py`
- `claim_decomposition_agent.py`
- `source_discovery_agent.py`
- `evidence_analysis_agent.py`
- `site_forensics_agent.py`
- `judge_agent.py`

Each agent must expose:
- a clear input contract
- a clear output contract
- internal tools used
- docstrings

### Phase 6 — Discovery/tool layer
Generate the interfaces/stubs for:
- `google_factcheck_search.py`
- `gdelt_doc_search.py`
- `gdelt_context_search.py`
- `official_source_discovery.py`
- `news_source_discovery.py`
- `cited_source_miner.py`
- `official_social_discovery.py`
- `passage_selector.py`
- site forensic tool files

Important:
If real integration code is too long, create clean, well-documented adapters/stubs with TODOs and request/response contracts.

### Phase 7 — Scoring modules
Generate:
- `source_reliability.py`
- `evidence_score.py`
- `truth_score.py`
- `verdict_mapping.py`
- `confidence_score.py`
- `site_trust_score.py`

Use the formulas and logic from the markdown spec.

### Phase 8 — Explanation layer
Generate:
- `explanation_builder.py`
- `claim_annotation_builder.py`
- `source_summary_builder.py`
- `executive_brief.py`

The output must always include:
- verdict
- truth score
- confidence score
- sources used
- explanation
- partial verdicts
- site forensics if URL input

### Phase 9 — FEVER benchmark mode
Generate:
- FEVER loader
- FEVER label mapper
- simple evaluation utilities
- benchmark route skeleton

### Phase 10 — Minimal frontend
Generate a minimal frontend that can:
- submit text or URL
- render verdict
- render claims
- render evidence
- render source reliability
- render site forensics
- render explanation

Keep it clean and simple.

## Coding style requirements

- Use Python for backend
- Use FastAPI
- Use type hints everywhere
- Use docstrings everywhere
- Keep functions small and modular
- Use deterministic utilities where possible
- Keep the code hackathon-ready but clean
- Prefer explicit over clever
- Add TODO comments for integration points
- Avoid unnecessary framework complexity

## Important behavior constraints

- Do not invent features outside the markdown spec
- Do not remove FEVER
- Do not remove GDELT or Google Fact Check connectors
- Do not turn the project into a chatbot
- Do not make the output only a binary label
- Do not omit explanation
- Do not omit source traceability
- Do not omit site checks for URL input
- Do not introduce a `sources.json` trusted-domain whitelist
- Do not hardcode ANSA/Reuters/AP/etc as the only usable sources
- Use heuristics and scoring, not manual approval lists

## Very important final instruction

Do **not** reply with only a plan.

Start implementing immediately.

Generate code in coherent chunks, beginning from the backend foundation and schemas.
For every chunk:
- explain what you are generating
- then provide the code

If the response becomes too long, continue in the next message without losing structure.

The goal is to end with a usable MVP codebase consistent with the markdown specification.
