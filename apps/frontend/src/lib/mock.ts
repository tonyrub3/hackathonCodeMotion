import { VerifyResponse } from "./types";

/** Mock response for development without backend. */
export const MOCK_RESPONSE: VerifyResponse = {
  input_type: "text",
  mode: "live",
  source_url: "",
  article_title: "",
  article_author: "",
  article_date: "",
  cited_links: [],
  trusted_domains: {
    news_general: ["ansa.it", "reuters.com", "apnews.com", "bbc.com", "corriere.it"],
    finance_statistical: [
      "ilsole24ore.com",
      "bloomberg.com",
      "ft.com",
      "wsj.com",
      "bancaditalia.it",
      "istat.it",
    ],
    fact_checking: ["pagellapolitica.it", "facta.news", "snopes.com", "politifact.com"],
    institutional: ["governo.it", "gazzettaufficiale.it", "europa.eu"],
  },
  claims: [
    {
      id: "c1",
      claim: "The inflation rate in Italy is 2%.",
      type: "statistical",
      partial_verdict: "verified",
      partial_score: 87,
      checkability_score: 0.95,
    },
    {
      id: "c2",
      claim: "The European Central Bank raised interest rates.",
      type: "institutional",
      partial_verdict: "mostly_verified",
      partial_score: 72,
      checkability_score: 0.85,
    },
    {
      id: "c3",
      claim: "This caused a decline in consumer spending.",
      type: "causal",
      partial_verdict: "mixed",
      partial_score: 55,
      checkability_score: 0.4,
    },
  ],
  generated_queries: [
    "italy inflation rate february 2026 istat",
    "BCE rialzo tassi marzo 2026",
    "ECB rate hike italy inflation consumer spending 2026",
  ],
  sources_used: [
    {
      source_id: "src_001",
      source_name: "ISTAT Official Statistics",
      source_type: "official",
      url: "https://www.istat.it",
      tier: "A",
      source_reliability_score: 0.93,
      dimensions: {
        authority: 1.0,
        expertise: 0.95,
        transparency: 0.9,
        independence: 0.85,
        recency: 0.95,
      },
    },
    {
      source_id: "src_002",
      source_name: "Reuters News",
      source_type: "news",
      url: "https://reuters.com",
      tier: "B",
      source_reliability_score: 0.78,
      dimensions: {
        authority: 0.7,
        expertise: 0.8,
        transparency: 0.75,
        independence: 0.85,
        recency: 0.9,
      },
    },
  ],
  all_tavily_results: [
    {
      url: "https://www.istat.it",
      title: "ISTAT inflation release",
      score: 0.91,
      _query: "italy inflation rate february 2026 istat",
      _retrieval_tier: "tier1",
      _search_topic: "finance",
    },
    {
      url: "https://reuters.com",
      title: "ECB coverage",
      score: 0.78,
      _query: "ECB rate hike italy inflation consumer spending 2026",
      _retrieval_tier: "tier1",
      _search_topic: "finance",
    },
  ],
  tavily_answer_hints: [
    {
      query: "italy inflation rate february 2026 istat",
      answer: "Italian inflation was reported at 2.0% in preliminary estimates.",
      tier: "tier1",
      topic: "finance",
      country: "italy",
    },
  ],
  tavily_search_profile: {
    topic: "finance",
    country: "italy",
    temporal: {},
  },
  evidence: [
    {
      source_id: "src_001",
      stance: "supporting",
      evidence_score: 0.91,
      excerpt:
        "Annual consumer price inflation was 2.0% in February 2026, according to ISTAT preliminary estimates.",
    },
    {
      source_id: "src_002",
      stance: "supporting",
      evidence_score: 0.74,
      excerpt:
        "The ECB confirmed a rate hike at its March meeting, raising the main refinancing rate by 25 basis points.",
    },
  ],
  contradictions: [],
  linguistic_risk: {
    sensationalism_score: 0.1,
    emotional_tone_score: 0.08,
    attribution_risk: 0.05,
    uncertainty_score: 0.15,
    manipulation_markers: [],
  },
  site_forensics: null,
  truth_score: 78,
  confidence_score: 0.76,
  verdict: "mostly_verified",
  explanation: {
    summary:
      "The content is largely supported, with minor caveats. (Truth score: 78/100, 3 claims analyzed, 2 evidence items)",
    why: "2 supporting evidence item(s) found (avg score: 0.83). The causal claim has limited direct evidence.",
    supporting_evidence: [
      "Annual consumer price inflation was 2.0% in February 2026, according to ISTAT preliminary estimates.",
      "The ECB confirmed a rate hike at its March meeting.",
    ],
    contradicting_evidence: [],
    source_analysis: [
      "ISTAT Official Statistics (official, tier A): reliability 0.93 (high reliability)",
      "Reuters News (news, tier B): reliability 0.78 (high reliability)",
    ],
    temporal_context: "1 claim(s) are time-sensitive. 2 evidence item(s) have publication dates.",
    caveats: [
      "The causal link between rate hikes and consumer spending decline requires more evidence.",
    ],
  },
  errors: [],
  timings: {
    input_normalizer: 0.01,
    claim_decomposition: 0.15,
    source_discovery: 1.2,
    evidence_analysis: 0.8,
    judge: 0.05,
  },
};
