/** TypeScript types matching the backend API contract. */

export interface VerifyRequest {
  input_type: "text" | "url";
  content: string;
  language?: string;
  country?: string;
  topic?: string;
}

export interface ClaimResponse {
  id: string;
  claim: string;
  type: string;
  partial_verdict: string;
  partial_score: number;
  checkability_score: number;
}

export interface SourceResponse {
  source_id: string;
  source_name: string;
  source_type: string;
  url: string;
  tier: string;
  source_reliability_score: number;
  dimensions: Record<string, number>;
}

export interface EvidenceResponse {
  source_id: string;
  stance: string;
  evidence_score: number;
  excerpt: string;
}

export interface ContradictionResponse {
  claim_id: string;
  type: string;
  description: string;
  severity: number;
}

export interface ExplanationResponse {
  summary: string;
  why: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  source_analysis: string[];
  temporal_context: string;
  caveats: string[];
}

export interface LinguisticRisk {
  sensationalism_score: number;
  emotional_tone_score: number;
  attribution_risk: number;
  uncertainty_score: number;
  manipulation_markers: string[];
}

export interface VerifyResponse {
  input_type: string;
  source_url: string;
  article_title: string;
  article_author: string;
  article_date: string;
  cited_links: string[];
  trusted_domains: Record<string, string[]>;
  claims: ClaimResponse[];
  generated_queries: string[];
  sources_used: SourceResponse[];
  all_tavily_results: Record<string, any>[];
  tavily_answer_hints: Record<string, any>[];
  tavily_search_profile: Record<string, any>;
  evidence: EvidenceResponse[];
  contradictions: ContradictionResponse[];
  linguistic_risk: LinguisticRisk;
  truth_score: number;
  confidence_score: number;
  verdict: string;
  explanation: ExplanationResponse;
  errors: string[];
  timings: Record<string, number>;
}
