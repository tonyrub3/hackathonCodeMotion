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

export interface DiscoveredSource {
  source_id?: string;
  source_name?: string;
  title?: string;
  source_type?: string;
  url: string;
  domain?: string;
  score?: number;
  claim_ids?: string[];
  query_hits?: Array<Record<string, unknown>>;
  answer_hints?: string[];
  selection_reason?: string;
  snippet?: string;
  raw_content?: string;
  published_at?: string;
  forensic_score?: number;
  forensic_flags?: string[];
  dimensions?: Record<string, number>;
}

export interface RejectedSource {
  source_id?: string;
  url?: string;
  reason: string;
  claim_id?: string;
}

export interface SourceForensics {
  source_id?: string;
  url?: string;
  domain: string;
  tld: string;
  https: boolean;
  canonical_origin?: string;
  brand_mimicry_risk: number;
  low_quality_risk?: number;
  author_present: boolean;
  author_name: string;
  citation_count: number;
  citation_density?: number;
  about_links?: number;
  contact_links?: number;
  editorial_links?: number;
  published_at?: string;
  forensic_score: number;
  dimensions?: Record<string, number>;
  flags?: string[];
}

export interface LinguisticRisk {
  sensationalism_score: number;
  emotional_tone_score: number;
  attribution_risk: number;
  uncertainty_score: number;
  manipulation_markers: string[];
}

export interface ClaimScoreResponse {
  claim_id: string;
  claim: string;
  support_score: number;
  contradiction_score: number;
  claim_coverage: number;
  source_diversity: number;
  temporal_alignment: number;
  forensic_support: number;
  confidence_score: number;
  partial_score: number;
  partial_verdict: string;
  direct_supporting_evidence: number;
  direct_contradicting_evidence: number;
  direct_evidence_count: number;
}

export interface VerifyResponse {
  input_type: string;
  mode: string;
  claims: ClaimResponse[];
  sources_used: SourceResponse[];
  all_sources_found: DiscoveredSource[];
  selected_sources: DiscoveredSource[];
  rejected_sources: RejectedSource[];
  source_forensics: SourceForensics[];
  claim_scores: ClaimScoreResponse[];
  evidence: EvidenceResponse[];
  contradictions: ContradictionResponse[];
  linguistic_risk: LinguisticRisk;
  site_forensics: SourceForensics | null;
  truth_score: number;
  confidence_score: number;
  verdict: string;
  explanation: ExplanationResponse;
  layer_outputs: Record<string, unknown>;
  errors: string[];
  timings: Record<string, number>;
}
