# Truth Engine

Explainable, source-traced fact-checking system built for the Rheinmetall Hackathon challenge.

Truth Engine accepts text or URLs, decomposes content into atomic claims, discovers evidence sources automatically, scores their reliability, and produces nuanced, explainable verdicts with full source traceability.

---

## Tech Stack

### Backend

| Technology | Version | Role |
|---|---|---|
| **Python** | 3.11+ | Core language |
| **FastAPI** | 0.109+ | REST API framework |
| **Uvicorn** | 0.27+ | ASGI server |
| **Pydantic** | 2.5+ | Data validation and serialization |
| **httpx** | 0.26+ | Async HTTP client for external APIs |
| **trafilatura** | 1.8+ | HTML article extraction |
| **python-dotenv** | 1.0+ | Environment variable management |
| **pytest** | 8.0+ | Testing framework |
| **pytest-asyncio** | 0.23+ | Async test support |

### Frontend

| Technology | Version | Role |
|---|---|---|
| **Next.js** | 14 | React framework |
| **React** | 18 | UI library |
| **TypeScript** | 5.3+ | Type-safe frontend code |

### External APIs

| Service | Role | Key Required |
|---|---|---|
| **Regolo** (Llama 3.1 70B Instruct) | Claim decomposition, stance classification | Yes |
| **Regolo** (Qwen3 Embedding 8B) | Semantic embeddings for deduplication | Yes |
| **GDELT** (DOC 2.0 + Context 2.0) | Live global news retrieval, temporal awareness | No (public API) |
| **Google Fact Check Tools API** | Matching against already-verified fact-checks | Yes (optional) |

---

## Architecture

```
User Input (text / URL)
         |
         v
+------------------+
| Input Normalizer |  Detect type, fetch HTML, extract article, clean text
+------------------+
         |
         v
+----------------------+
| Claim Decomposition  |  Split into atomic claims (regex + Llama 70B for complex sentences)
+----------------------+
         |
         v
+-------------------+
| Source Discovery   |  Google Fact Check, GDELT, official source heuristics, cited source mining
+-------------------+
         |
         v
+---------------------+
| Evidence Analysis   |  Stance classification (LLM), source reliability scoring, contradiction detection
+---------------------+
         |
         v
+------------------+       (URL input only)
| Site Forensics   |  Domain checks, author, citations, transparency, brand mimicry
+------------------+
         |
         v
+--------+
| Judge  |  Deterministic truth score, verdict mapping, explanation generation
+--------+
         |
         v
    API Response
```

### 6 Pipeline Agents

| # | Agent | What it does |
|---|-------|---|
| 1 | **Input Normalizer** | Detect text/URL, fetch HTML, extract article body + metadata |
| 2 | **Claim Decomposition** | Split into atomic claims using hybrid approach (fast regex + LLM for complex) |
| 3 | **Source Discovery** | Query GDELT, Google Fact Check, official source heuristics, mine cited links |
| 4 | **Evidence Analysis** | Classify stance, score source reliability, score evidence, detect contradictions |
| 5 | **Site Forensics** | (URL only) Domain age, brand mimicry, author, citations, transparency |
| 6 | **Judge** | Deterministic truth score, verdict mapping, partial verdicts, explanation |

---

## Key Design Principles

- **Deterministic scoring** — truth score, source reliability, evidence scores use explicit weighted formulas, not LLM judgment
- **No hardcoded whitelist** — source trust is computed from heuristic patterns and evidence features, not a `sources.json` of approved domains
- **LLM only for extraction** — Regolo/Llama is used for claim decomposition and stance classification, never for deciding the final verdict
- **Explainable verdicts** — every verdict comes with structured explanation, source analysis, and per-claim partial verdicts
- **Source traceability** — every evidence item is linked to its source with reliability dimensions

---

## Scoring Formulas

### Source Reliability Score (per source)

```
source_reliability = 0.30 * authority
                   + 0.20 * expertise
                   + 0.20 * transparency
                   + 0.15 * independence
                   + 0.15 * recency
```

### Evidence Score (per evidence item)

```
evidence_score = 0.30 * source_reliability
               + 0.20 * relevance
               + 0.20 * directness
               + 0.15 * specificity
               + 0.10 * temporal_fit
               + 0.05 * geographic_fit
```

### Truth Score (global, 0-100)

```
truth_score = 0.28 * support_strength
            + 0.18 * consensus
            + 0.18 * avg_source_reliability
            + 0.12 * temporal_validity
            + 0.10 * claim_checkability
            + 0.07 * evidence_coverage
            - 0.17 * contradiction_strength
            - 0.05 * linguistic_risk
            - 0.05 * site_trust_penalty
```

### Verdict Mapping

| Score | Verdict |
|---|---|
| 85-100 | `verified` |
| 70-84 | `mostly_verified` |
| 55-69 | `mixed` |
| 40-54 | `misleading` / `decontextualized` |
| 25-39 | `mostly_false` |
| 0-24 | `false` |
| (too few sources) | `insufficient_evidence` |

---

## Repository Structure

```
truth-engine/
  apps/
    backend/
      app/
        main.py                  # FastAPI entry point
        config.py                # Environment-based settings
        api/                     # Route handlers
        core/                    # Orchestrator, pipeline state
        agents/                  # 6 pipeline agents
        models/                  # Pydantic request/response models
        services/
          llm/                   # Regolo client, prompts, embeddings
          discovery/             # Source discovery (official, news, cited, social)
          connectors/            # GDELT, Google Fact Check
          parsing/               # HTML, article extraction, sentence splitting
          scoring/               # Source reliability, evidence, truth, verdict, confidence
          site_forensics/        # Domain, author, citation, transparency checks
          benchmark/             # FEVER loader, mapper, evaluation
          reporting/             # Explanation, source summary, executive brief
          contradiction/         # Number, date, entity, quote conflict detection
        utils/                   # Logger, dates, URLs, hashing
        tests/                   # Unit tests
    frontend/
      src/
        app/                     # Next.js pages
        components/              # React UI components
        lib/                     # API client, types, mock data
  packages/
    shared/                      # JSON schemas, verdict/claim/tier constants
    prompts/                     # LLM prompt templates
  data/
    discovery_policies/          # official_patterns.json, discovery_rules.json, topic_rules.json
    demo_cases/                  # Sample verification inputs
    fever/                       # FEVER benchmark dataset (not included)
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/verify` | Run full verification pipeline |
| `POST` | `/api/benchmark/fever/run` | Run FEVER benchmark (stub) |
| `POST` | `/api/benchmark/fever/evaluate` | Evaluate FEVER results (stub) |
| `GET` | `/api/debug/config` | Debug endpoint |

---

## Quick Start

See [QUICKSTART.md](QUICKSTART.md) for setup instructions, API examples, and curl commands.
