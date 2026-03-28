# Truth Engine — Complete Coding Specification (Auto-Discovery Version)

## Purpose

Build a **text-first, explainable fact-checking system** for the Rheinmetall challenge.

This document is written for a coding LLM.
The implementation must prioritize:

- **claim decomposition**
- **automatic source discovery**
- **source and site scoring**
- **nuanced, explainable verdicts**
- **clear scoring**
- **full source traceability**
- **site forensics when the input is a link**
- **FEVER benchmark mode** for validation
- **integration of GDELT + Google Fact Check + Regolo**

The final system must **not** be a simple wrapper around APIs or an LLM.
LLMs can help with extraction and structuring, but the final verdict must come from **structured evidence, deterministic scoring, and explainable logic**.

The system must **not depend on a manual whitelist of verified sites**.
It may use **heuristics, discovery policies, and weak priors**, but it must discover and evaluate sources automatically.

---

# 1. Product definition

## What the system does

The system accepts:

- plain text
- pasted article text
- a URL

It returns:

- extracted **atomic claims**
- a list of **sources actually used**
- **source reliability scores**
- contradictions found across sources
- a **truth scale verdict**
- a **truth score**
- a **confidence score**
- a **structured explanation**
- optional **claim-by-claim partial verdicts**
- if input is a link: a **site forensic analysis**

---

# 2. Strategic positioning

This system should implement the strongest differentiators identified in the team's competitive analysis.

## Primary differentiators
- **Structured textual explanation** instead of a simple label
- **Source Reliability Score**
- **Nuanced truth scale**

## Secondary differentiators
- **Claim decomposition**
- **Temporal awareness**
- **Claim-level partial verdicts**
- **Site forensics for URL inputs**

The UI and backend must reflect these priorities.

---

# 3. Core modes

Use **2 modes**.

## 3.1 Live mode
Used in the demo and product flow.

Input:
- text or URL

Evidence comes from:
- automatically discovered official sources
- automatically discovered trusted news coverage
- Google Fact Check for already-verified claims
- GDELT for live/global coverage
- official social accounts if strongly attributable and necessary
- cited sources extracted from the input article if input is a URL

Goal:
- produce explainable verdicts on current text/news/article content

## 3.2 Benchmark mode
Used for validation and internal testing.

Dataset:
- **FEVER** dataset

Use FEVER as:
- a benchmark for claim retrieval
- a benchmark for stance classification
- a benchmark for verdict calibration

Important:
- FEVER is **not** the live source-of-truth layer
- FEVER is used to validate the core engine

### FEVER mapping
Map FEVER labels like this:

- `SUPPORTS` → `verified`
- `REFUTES` → `disputed`
- `NOT ENOUGH INFO` → `insufficient_evidence`

### FEVER usage
Use FEVER to:
- test retrieval quality
- test claim/evidence matching
- test verdict thresholds
- compute benchmark metrics

---

# 4. External systems and their roles

## 4.1 GDELT
Use GDELT as:
- **early warning / global retrieval layer**
- **temporal awareness support**
- **multilingual live coverage source**

Do **not** use GDELT as the final truth oracle.

## 4.2 Google Fact Check Tools API
Use Google Fact Check as:
- **claim matching layer**
- **shortcut for previously verified claims**
- **evidence for human-reviewed fact-check results**

Do **not** use it as the only decision layer.

## 4.3 Regolo
Use Regolo as:
- **semantic claim decomposition**
- **semantic normalization**
- **embeddings for deduplication**
- **reranking passages**
- optional classification support

Do **not** let Regolo alone decide the final verdict.

## 4.4 FEVER
Use FEVER as:
- **benchmark dataset**
- **validation dataset**
- **threshold calibration dataset**

Do **not** use FEVER as the runtime evidence base for current events.

---

# 5. Input types

## 5.1 Text input
User pastes plain text or article text.

## 5.2 URL input
User pastes an article or website URL.

If the input is a URL, run **two parallel tracks**:

### Track A — Content verification
- fetch article text
- extract claims
- discover evidence sources
- produce verdict

### Track B — Site forensics
- inspect the domain
- inspect site metadata
- inspect author metadata
- inspect the article structure
- inspect publication signals
- inspect article citations and source references

The final response must include both:
- **content truth analysis**
- **site trust analysis**

---

# 6. High-level architecture

Use **6 agents/modules** total.

## Agent 1 — Input Normalizer Agent
Responsibilities:
- detect input type (`text` or `url`)
- normalize encoding
- extract raw content from URL
- clean HTML and article body
- store metadata

## Agent 2 — Claim Decomposition Agent
Responsibilities:
- split text into atomic, independently checkable claims
- classify claim types
- resolve pronouns where possible
- mark causal claims separately
- output structured claims

## Agent 3 — Source Discovery Agent
Responsibilities:
- generate retrieval queries for each atomic claim
- discover relevant evidence sources automatically
- prioritize likely official / primary sources
- gather candidate evidence
- collect excerpts and metadata

## Agent 4 — Evidence & Source Analysis Agent
Responsibilities:
- classify stance of each evidence item:
  - supporting
  - contradicting
  - neutral
- compute source reliability scores
- compute evidence scores
- detect source weakness
- aggregate consensus/conflict signals
- detect temporal mismatch

## Agent 5 — Site Forensics Agent
Used only if input is a URL.

Responsibilities:
- inspect the domain and article source
- check author metadata
- check source references inside the article
- estimate site trust risk
- estimate whether the site is recently created or suspicious
- output a site forensics report

## Agent 6 — Judge / Report Agent
Responsibilities:
- combine all structured outputs
- assign a nuanced verdict
- assign confidence
- generate a structured explanation
- produce claim-by-claim partial verdicts
- return all sources used

---

# 7. Agent tool definitions

This section is mandatory.
Each agent must use explicit tools.

## 7.1 Input Normalizer Agent — tools

### `text_parser`
- normalize raw text
- remove broken whitespace
- preserve sentence boundaries

### `url_fetcher`
- fetch page HTML
- handle redirects
- collect final URL

### `article_extractor`
- extract readable article body from HTML
- extract title, author, date, metadata

### `metadata_extractor`
- extract domain, publication date, canonical URL, byline, source links, outgoing citations

---

## 7.2 Claim Decomposition Agent — tools

### `sentence_splitter`
- split text into sentences/paragraph segments

### `entity_extractor`
- detect organizations, persons, places, institutions

### `date_number_extractor`
- detect dates, periods, quantities, monetary amounts, percentages

### `causal_cue_detector`
- detect connectors like:
  - because
  - due to
  - despite
  - therefore
  - caused by

### `semantic_claim_decomposer`
- use Regolo / LLM only on complex sentences
- output structured atomic claims

### `claim_deduplicator`
- use embeddings or semantic similarity
- merge duplicate or near-duplicate claims

---

## 7.3 Source Discovery Agent — tools

### `query_builder`
- build search queries from each claim
- expand with entities, dates, numbers, synonyms, and domain hints

### `google_factcheck_search`
- query Google Fact Check Tools API
- use for already-verified claims
- return matched fact-checks and metadata

### `gdelt_doc_search`
- query GDELT DOC 2.0
- use for live/global article retrieval
- return candidate articles/snippets

### `gdelt_context_search`
- query GDELT Context 2.0
- use for quote/context retrieval

### `official_source_discovery`
- discover likely official sources automatically from entities in the claim
- examples:
  - government pages
  - ministry pages
  - regulator pages
  - statistical institutes
  - company investor-relations / official statements
  - legal / normative databases

### `cited_source_miner`
- if input is a URL, extract all sources cited by the article
- classify cited links as possible primary/secondary evidence candidates

### `news_source_discovery`
- discover broader journalistic coverage around the claim
- do not rely on a manual site whitelist
- use signals from article metadata, domain patterns, recurrence, and cross-coverage

### `official_social_discovery`
- discover official social accounts only if attributable to the involved institution/person/company
- never use non-official social as strong evidence without corroboration

### `passage_selector`
- select the most relevant passages from retrieved documents
- may use rerank

---

## 7.4 Evidence & Source Analysis Agent — tools

### `stance_classifier`
- classify evidence as:
  - supporting
  - contradicting
  - neutral

### `source_reliability_scorer`
- compute source reliability dimensions

### `evidence_scorer`
- compute per-evidence score

### `consensus_builder`
- aggregate supporting vs contradicting evidence

### `conflict_detector`
- detect explicit contradictions

### `temporal_validator`
- verify date consistency and possible decontextualization

### `independence_checker`
- estimate whether a source is independent or merely repeating another source

---

## 7.5 Site Forensics Agent — tools

### `domain_metadata_checker`
- inspect domain name, TLD, HTTPS, structure

### `site_age_checker`
- estimate whether domain/site appears recent or low-trust
- use allowed age heuristics when direct registration data is unavailable

### `brand_mimicry_checker`
- detect suspicious imitation of known brands/publishers

### `author_presence_checker`
- detect author name, byline, author page, author history

### `citation_checker`
- inspect outgoing references and cited sources
- count primary vs secondary sources
- detect circular sourcing

### `transparency_checker`
- check editorial policy, about page, contact page, ownership signals

### `headline_body_mismatch_checker`
- detect sensational headline vs weak body mismatch

---

## 7.6 Judge / Report Agent — tools

### `truth_score_calculator`
- compute deterministic truth score

### `verdict_mapper`
- map score + override rules to final label

### `partial_verdict_builder`
- compute claim-by-claim verdicts

### `explanation_builder`
- produce structured explanation

### `source_summary_builder`
- produce human-readable summary of why sources were trusted or downgraded

---

# 8. Claim decomposition

This is one of the core differentiators.

## Goal
Transform a complex sentence or article into a list of atomic, verifiable claims.

## Important rules
Each claim must be:
- atomic
- fact-like
- independently understandable
- independently searchable
- typed
- assigned a checkability score

## Claim types
Supported values:

- `statistical`
- `event`
- `quote`
- `institutional`
- `regulatory`
- `causal`
- `historical`
- `technical`

## Claim decomposition output schema

```json
[
  {
    "id": "c1",
    "claim": "The inflation rate in Italy is 2%.",
    "type": "statistical",
    "subject": "inflation rate in Italy",
    "predicate": "is",
    "object": "2%",
    "time_scope": "2025",
    "geo_scope": "Italy",
    "checkability_score": 0.95,
    "dependency_type": "standalone",
    "requires_evidence_type": ["official_statistics"],
    "original_sentence_index": 0
  }
]
```

## Special handling for causal claims
Causal claims must never be treated as ordinary factual claims.

Example:
- "Orders declined because of new regulations."

This must become:
- event claim: orders declined
- regulatory claim: new regulations exist
- causal claim: the decline was caused by those regulations

Causal claims usually have lower direct checkability and require stronger evidence.

---

# 9. Using semantic models in claim decomposition

Use a **hybrid approach**.

## Fast path
Use lightweight rules first:
- sentence splitting
- number extraction
- date extraction
- quote detection
- causal cue detection
- simple NER

## Semantic path
Use Regolo / LLM only for sentences that are:
- long
- multi-clause
- dense with facts
- causal
- ambiguous
- referential/pronominal

## Recommendation
Do **not** use a large semantic model on every sentence.
That would slow the workflow unnecessarily.

## Recommended usage of Regolo
Use Regolo for:
- semantic claim decomposition
- semantic normalization
- claim deduplication via embeddings
- optional reranking of claims/evidence

---

# 10. Automatic source discovery principles

This system must **not** rely on a fixed `sources.json` whitelist of trusted sites.

Instead, source discovery must be based on:

- claim entities
- claim type
- cited links inside the input article
- official-domain patterns
- regulator / institution discovery patterns
- recurrence across multiple independent sources
- transparency and metadata signals
- cross-source corroboration
- domain / article forensics

## Allowed weak priors
The system may use **general discovery rules**, such as:
- `.gov`, `.gov.*`, ministry/regulator patterns may indicate official sources
- investor-relations or newsroom sections on official company domains may indicate primary sources
- domains with clear bylines, timestamps, ownership, editorial pages, and citations may score higher

These are **heuristics**, not a manual site whitelist.

---

# 11. Source discovery policy files

We remove `sources.json` entirely.

Use policy/config files instead.

## `official_patterns.json`
Contains generic patterns and rules for identifying likely primary sources.

Examples:
- `.gov`, `.gov.it`, `.europa.eu`
- `/investors`, `/investor-relations`, `/press`, `/media`, `/newsroom`
- ministry / regulator / bureau patterns

## `discovery_rules.json`
Contains retrieval logic rules such as:
- when to prefer official discovery first
- when to expand with GDELT
- when to prioritize cited links from the input article
- when to search for official statistics or legal sources

## `topic_rules.json`
Contains topic-aware source discovery hints.

Examples:
- `economy` → prioritize statistics offices, central banks, market regulators, company IR pages
- `politics` → prioritize official government and parliamentary sources
- `defense` → prioritize official ministries, NATO/UE/ONU when relevant, official company statements

---

# 12. Evidence model

Every evidence item must be structured.

```json
{
  "source_id": "auto_generated_or_hash",
  "source_name": "Detected Source Name",
  "source_type": "official|news|document|social_official|factcheck",
  "url": "https://...",
  "tier": "A|B|C",
  "published_at": "2026-03-28T10:00:00Z",
  "stance": "supporting",
  "relevance_score": 0.88,
  "trust_score": 0.81,
  "excerpt": "Relevant passage here",
  "matched_claim_ids": ["c1", "c2"]
}
```

## Stance values
- `supporting`
- `contradicting`
- `neutral`

---

# 13. Dynamic source tiering

Source tier must be assigned dynamically, not looked up from a manual site list.

## Tier A — primary / official
Examples:
- official institution pages
- official regulator pages
- official statistics offices
- official company communications / investor relations
- official legal/normative databases

## Tier B — trusted secondary
Examples:
- independent journalistic coverage with good metadata and citations
- well-documented fact-check articles
- established reporting with clear sourcing

## Tier C — weak / indirect
Examples:
- anonymous blogs
- repost aggregators
- unattributed screenshots
- non-official social accounts
- low-transparency sites

Important:
- Tier is **derived from evidence features**, not hardcoded by domain name alone.

---

# 14. Source Reliability Score

One of the main differentiators.

The score must be **multidimensional**, not a single opaque number.

## Dimensions
For each source, compute:

### 14.1 Authority
- official primary source
- recognized secondary source
- weak or indirect source

### 14.2 Expertise
- how strong the source is on the specific topic/domain

### 14.3 Transparency
- author, methodology, citations, editorial signals

### 14.4 Independence
- whether the source is independent or just repeating another source

### 14.5 Recency
- whether the source is up to date for this claim

## Source Reliability Score formula

```text
source_reliability_score =
0.30 * authority +
0.20 * expertise +
0.20 * transparency +
0.15 * independence +
0.15 * recency
```

All components normalized to `[0, 1]`.

Return:
- per-dimension values
- total score
- explanation

---

# 15. Evidence scoring

Each evidence item must receive an `evidence_score`.

## Signals
- source reliability
- specificity of excerpt
- directness of support/contradiction
- semantic relevance to the claim
- temporal fit
- geographic fit

## Suggested formula

```text
evidence_score =
0.30 * source_reliability_score +
0.20 * relevance_score +
0.20 * directness_score +
0.15 * specificity_score +
0.10 * temporal_fit +
0.05 * geographic_fit
```

---

# 16. Linguistic risk analysis

This is useful but secondary.

It must never determine truth by itself.

## Signals
- sensationalism
- emotional intensity
- clickbait patterns
- vague attribution
- uncertainty markers
- manipulative rhetoric

## Output example

```json
{
  "linguistic_risk": {
    "sensationalism_score": 0.18,
    "emotional_tone_score": 0.22,
    "attribution_risk": 0.65,
    "uncertainty_score": 0.31,
    "manipulation_markers": [
      "according to some sources",
      "shocking revelation"
    ]
  }
}
```

---

# 17. Truth scale

Do not return a binary verdict.

Use a nuanced truth scale.

## Allowed final verdicts
- `verified`
- `mostly_verified`
- `mixed`
- `misleading`
- `decontextualized`
- `insufficient_evidence`
- `mostly_false`
- `false`

---

# 18. Truth Score

The final score must be deterministic and explainable.

## Inputs
Use:
- supporting evidence strength
- contradicting evidence strength
- consensus
- source quality
- temporal fit
- linguistic penalty (small weight only)
- site trust penalty (only for URL input, and only as a secondary signal)

## Suggested formula

```text
truth_score =
(0.28 * support_strength) +
(0.18 * consensus_score) +
(0.18 * average_source_reliability) +
(0.12 * temporal_validity_score) +
(0.10 * claim_checkability_score) +
(0.07 * evidence_coverage_score) -
(0.17 * contradiction_strength) -
(0.05 * linguistic_risk_penalty) -
(0.05 * site_trust_penalty_if_url)
```

All components normalized to `[0, 1]`.
Final score scaled to `0–100`.

## Notes
- contradiction must matter strongly
- linguistic risk must matter, but not dominate
- site trust must affect confidence, not replace factual analysis

---

# 19. Verdict mapping from score

Suggested mapping:

- `85–100` → `verified`
- `70–84` → `mostly_verified`
- `55–69` → `mixed`
- `40–54` → `misleading` or `decontextualized`
- `25–39` → `mostly_false`
- `0–24` → `false`

Override rule:
- if evidence is too weak, return `insufficient_evidence` regardless of score
- if context is missing but core fact is technically correct, prefer `decontextualized`

---

# 20. Required explainable output

The final output must always include:

- final verdict
- truth score
- confidence score
- structured explanation
- sources used
- claim-by-claim partial verdicts
- contradictions found
- site forensics if input was URL

## Mandatory explanation sections
The response explanation must include:

### 20.1 Summary verdict
A short human-readable conclusion.

### 20.2 Why this verdict
Plain-language explanation.

### 20.3 Supporting evidence
List the strongest evidence items.

### 20.4 Contradicting evidence
List conflicting evidence.

### 20.5 Source analysis
Explain why the main sources were trusted or downgraded.

### 20.6 Temporal context
Explain whether the claim is time-sensitive or outdated.

### 20.7 Caveats / unresolved issues
What remains uncertain.

---

# 21. Final API response schema

```json
{
  "input_type": "text",
  "mode": "live",
  "claims": [
    {
      "id": "c1",
      "claim": "The inflation rate in Italy is 2%.",
      "type": "statistical",
      "partial_verdict": "verified",
      "partial_score": 87,
      "checkability_score": 0.95
    }
  ],
  "sources_used": [
    {
      "source_id": "auto_hash_123",
      "source_name": "Detected Official Statistics Source",
      "source_type": "official",
      "url": "https://...",
      "tier": "A",
      "source_reliability_score": 0.93,
      "dimensions": {
        "authority": 1.0,
        "expertise": 0.95,
        "transparency": 0.90,
        "independence": 0.85,
        "recency": 0.95
      }
    }
  ],
  "evidence": [
    {
      "source_id": "auto_hash_123",
      "stance": "supporting",
      "evidence_score": 0.91,
      "excerpt": "..."
    }
  ],
  "contradictions": [],
  "linguistic_risk": {
    "sensationalism_score": 0.10,
    "attribution_risk": 0.05
  },
  "site_forensics": null,
  "truth_score": 88,
  "confidence_score": 0.86,
  "verdict": "verified",
  "explanation": {
    "summary": "The claim is supported by strong primary evidence.",
    "why": "A high-authority source directly supports the statistical value and no strong contradiction was found.",
    "supporting_evidence": [
      "Primary evidence confirms the reported value."
    ],
    "contradicting_evidence": [],
    "source_analysis": [
      "The strongest source is primary, transparent, and recent."
    ],
    "temporal_context": "The claim is time-sensitive and valid for the referenced reporting period.",
    "caveats": [
      "The metric may change in later reporting periods."
    ]
  }
}
```

---

# 22. FEVER integration details

Create a `benchmark_mode` pipeline.

## FEVER folder structure

```text
data/
  fever/
    train.jsonl
    dev.jsonl
    test.jsonl
    wiki_pages/
```

## FEVER preprocessing requirements
- parse JSONL
- map FEVER labels to local verdict labels
- store claim/evidence pairs
- support retrieval evaluation
- support verdict evaluation

## FEVER benchmark metrics
Implement:
- claim label accuracy
- evidence recall
- evidence precision
- partial retrieval hit-rate
- confusion matrix for verdicts

## FEVER mode API
Add:
- `/benchmark/fever/run`
- `/benchmark/fever/evaluate`

---

# 23. Repository structure

```text
truth-engine/
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Makefile
│
├── apps/
│   ├── backend/
│   │   ├── requirements.txt
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   │
│   │   │   ├── api/
│   │   │   │   ├── routes_health.py
│   │   │   │   ├── routes_verify.py
│   │   │   │   ├── routes_debug.py
│   │   │   │   └── routes_benchmark.py
│   │   │   │
│   │   │   ├── core/
│   │   │   │   ├── orchestrator.py
│   │   │   │   ├── state.py
│   │   │   │   ├── pipeline_live.py
│   │   │   │   ├── pipeline_benchmark.py
│   │   │   │   └── exceptions.py
│   │   │   │
│   │   │   ├── agents/
│   │   │   │   ├── input_normalizer_agent.py
│   │   │   │   ├── claim_decomposition_agent.py
│   │   │   │   ├── source_discovery_agent.py
│   │   │   │   ├── evidence_analysis_agent.py
│   │   │   │   ├── site_forensics_agent.py
│   │   │   │   └── judge_agent.py
│   │   │   │
│   │   │   ├── models/
│   │   │   │   ├── request_models.py
│   │   │   │   ├── response_models.py
│   │   │   │   ├── claim_models.py
│   │   │   │   ├── evidence_models.py
│   │   │   │   ├── source_models.py
│   │   │   │   ├── site_forensics_models.py
│   │   │   │   └── benchmark_models.py
│   │   │   │
│   │   │   ├── services/
│   │   │   │   ├── llm/
│   │   │   │   │   ├── regolo_client.py
│   │   │   │   │   ├── prompts.py
│   │   │   │   │   ├── embeddings.py
│   │   │   │   │   └── rerank.py
│   │   │   │   │
│   │   │   │   ├── discovery/
│   │   │   │   │   ├── query_builder.py
│   │   │   │   │   ├── official_source_discovery.py
│   │   │   │   │   ├── news_source_discovery.py
│   │   │   │   │   ├── cited_source_miner.py
│   │   │   │   │   ├── official_social_discovery.py
│   │   │   │   │   └── discovery_router.py
│   │   │   │   │
│   │   │   │   ├── connectors/
│   │   │   │   │   ├── google_factcheck_search.py
│   │   │   │   │   ├── gdelt_doc_search.py
│   │   │   │   │   └── gdelt_context_search.py
│   │   │   │   │
│   │   │   │   ├── parsing/
│   │   │   │   │   ├── html_parser.py
│   │   │   │   │   ├── article_extractor.py
│   │   │   │   │   ├── text_cleaner.py
│   │   │   │   │   ├── sentence_splitter.py
│   │   │   │   │   └── metadata_extractor.py
│   │   │   │   │
│   │   │   │   ├── scoring/
│   │   │   │   │   ├── source_reliability.py
│   │   │   │   │   ├── evidence_score.py
│   │   │   │   │   ├── truth_score.py
│   │   │   │   │   ├── verdict_mapping.py
│   │   │   │   │   ├── confidence_score.py
│   │   │   │   │   └── site_trust_score.py
│   │   │   │   │
│   │   │   │   ├── contradiction/
│   │   │   │   │   ├── number_conflicts.py
│   │   │   │   │   ├── date_conflicts.py
│   │   │   │   │   ├── entity_conflicts.py
│   │   │   │   │   ├── quote_conflicts.py
│   │   │   │   │   └── conflict_merger.py
│   │   │   │   │
│   │   │   │   ├── site_forensics/
│   │   │   │   │   ├── domain_checks.py
│   │   │   │   │   ├── author_checks.py
│   │   │   │   │   ├── citation_checks.py
│   │   │   │   │   ├── transparency_checks.py
│   │   │   │   │   ├── brand_mimicry_checks.py
│   │   │   │   │   └── site_age_checks.py
│   │   │   │   │
│   │   │   │   ├── benchmark/
│   │   │   │   │   ├── fever_loader.py
│   │   │   │   │   ├── fever_mapper.py
│   │   │   │   │   ├── fever_retrieval_eval.py
│   │   │   │   │   └── fever_verdict_eval.py
│   │   │   │   │
│   │   │   │   └── reporting/
│   │   │   │       ├── explanation_builder.py
│   │   │   │       ├── claim_annotation_builder.py
│   │   │   │       ├── source_summary_builder.py
│   │   │   │       └── executive_brief.py
│   │   │   │
│   │   │   ├── utils/
│   │   │   │   ├── logger.py
│   │   │   │   ├── dates.py
│   │   │   │   ├── urls.py
│   │   │   │   ├── hashing.py
│   │   │   │   └── validators.py
│   │   │   │
│   │   │   └── tests/
│   │   │       ├── test_claim_decomposition.py
│   │   │       ├── test_discovery.py
│   │   │       ├── test_source_reliability.py
│   │   │       ├── test_truth_score.py
│   │   │       ├── test_site_forensics.py
│   │   │       └── test_fever_eval.py
│   │   │
│   │   └── scripts/
│   │       ├── load_fever.py
│   │       ├── run_local_verify.py
│   │       └── run_benchmark.py
│   │
│   └── frontend/
│       ├── package.json
│       ├── src/
│       │   ├── app/
│       │   │   ├── page.tsx
│       │   │   └── layout.tsx
│       │   ├── components/
│       │   │   ├── InputBox.tsx
│       │   │   ├── ClaimList.tsx
│       │   │   ├── SourceCard.tsx
│       │   │   ├── VerdictCard.tsx
│       │   │   ├── ConflictPanel.tsx
│       │   │   ├── ExplanationPanel.tsx
│       │   │   ├── SiteForensicsCard.tsx
│       │   │   ├── SourceReliabilityPanel.tsx
│       │   │   └── TextAnnotationPanel.tsx
│       │   └── lib/
│       │       ├── api.ts
│       │       ├── types.ts
│       │       └── mock.ts
│
├── packages/
│   ├── shared/
│   │   ├── schemas/
│   │   │   ├── verify_request.schema.json
│   │   │   ├── verify_response.schema.json
│   │   │   ├── claim.schema.json
│   │   │   ├── evidence.schema.json
│   │   │   └── site_forensics.schema.json
│   │   └── constants/
│   │       ├── verdicts.py
│   │       ├── claim_types.py
│   │       └── source_tiers.py
│   │
│   └── prompts/
│       ├── claim_decomposition_prompt.txt
│       ├── evidence_analysis_prompt.txt
│       ├── judge_prompt.txt
│       └── site_forensics_prompt.txt
│
├── data/
│   ├── demo_cases/
│   │   ├── case_01.json
│   │   ├── case_02.json
│   │   └── case_03.json
│   ├── discovery_policies/
│   │   ├── official_patterns.json
│   │   ├── discovery_rules.json
│   │   └── topic_rules.json
│   └── fever/
│       ├── train.jsonl
│       ├── dev.jsonl
│       ├── test.jsonl
│       └── wiki_pages/
│
└── docs/
    ├── architecture.md
    ├── api_contract.md
    ├── scoring_logic.md
    ├── fever_benchmark.md
    ├── source_discovery.md
    ├── site_forensics.md
    └── demo_script.md
```

---

# 24. API contract

## Verify request

```json
{
  "input_type": "url",
  "content": "https://example.com/article",
  "language": "it",
  "country": "IT",
  "topic": "politics",
  "mode": "live"
}
```

## Verify response requirements
The response must always include:
- claims
- sources used
- evidence
- contradictions
- truth score
- verdict
- explanation

If input is URL, also include:
- site_forensics

---

# 25. Implementation priorities

## Phase 1
- project skeleton
- `/verify` endpoint
- request/response models
- frontend with mocked output

## Phase 2
- text input
- claim decomposition
- source discovery
- final verdict

## Phase 3
- source reliability scoring
- structured explanation
- partial verdicts

## Phase 4
- URL handling
- article extraction
- site forensics

## Phase 5
- FEVER benchmark mode
- evaluation metrics
- threshold calibration

## Phase 6
- GDELT + Google Fact Check connectors
- score explanations
- source traceability improvements

---

# 26. Coding constraints

## Required constraints
- use deterministic formulas for scores where possible
- do not let the LLM decide the final verdict alone
- every verdict must cite evidence
- every source must have metadata
- every score must be explainable
- keep the pipeline linear and debuggable
- optimize for demo clarity over research complexity
- do not depend on a manual list of verified sites

## Non-goals
- no audio/video in MVP
- no giant agent swarm
- no full search engine
- no heavy crawler infrastructure
- no public journalist ranking

---

# 27. Immediate implementation files

Backend first:
- `main.py`
- `routes_verify.py`
- `orchestrator.py`
- `state.py`
- `claim_decomposition_agent.py`
- `source_discovery_agent.py`
- `evidence_analysis_agent.py`
- `site_forensics_agent.py`
- `judge_agent.py`
- `truth_score.py`
- `source_reliability.py`
- `site_trust_score.py`
- `google_factcheck_search.py`
- `gdelt_doc_search.py`
- `official_source_discovery.py`
- `cited_source_miner.py`

Frontend first:
- `page.tsx`
- `InputBox.tsx`
- `VerdictCard.tsx`
- `ClaimList.tsx`
- `ExplanationPanel.tsx`
- `SiteForensicsCard.tsx`
- `SourceReliabilityPanel.tsx`

Discovery/data first:
- `official_patterns.json`
- `discovery_rules.json`
- `topic_rules.json`
- FEVER folder scaffold

---

# 28. Final instruction to coding LLM

Implement the project exactly as a **pragmatic, hackathon-ready MVP**.

Priority order:
1. end-to-end working flow
2. structured claims
3. automatic source discovery
4. explainable verdict
5. source reliability score
6. URL site forensics
7. FEVER benchmark mode
8. GDELT / Google Fact Check connectors

If time is short:
- keep the pipeline linear
- prefer simplified site-age heuristics over complex infrastructure
- keep scores interpretable
- do not remove explanation or source traceability
- do not introduce a hardcoded trusted-site whitelist
