/** TypeScript types matching the backend API contract. */

export interface VerifyRequest {
  input_type: "text" | "url";
  content: string;
  language?: string;
  country?: string;
  topic?: string;
  mode?: "live" | "benchmark";
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

export interface SiteForensics {
  domain: string;
  tld: string;
  https: boolean;
  site_age_signal: string;
  brand_mimicry_risk: number;
  author_present: boolean;
  author_name: string;
  citation_count: number;
  primary_source_citations: number;
  secondary_source_citations: number;
  site_trust_score: number;
  headline_body_mismatch: number;
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
  mode: string;
  claims: ClaimResponse[];
  sources_used: SourceResponse[];
  evidence: EvidenceResponse[];
  contradictions: ContradictionResponse[];
  linguistic_risk: LinguisticRisk;
  site_forensics: SiteForensics | null;
  truth_score: number;
  confidence_score: number;
  verdict: string;
  explanation: ExplanationResponse;
  errors: string[];
  timings: Record<string, number>;
}
