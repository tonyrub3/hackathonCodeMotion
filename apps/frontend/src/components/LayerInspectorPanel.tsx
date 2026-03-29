"use client";

import type { CSSProperties, ReactNode } from "react";

import {
  ClaimScoreResponse,
  DiscoveredSource,
  EvidenceResponse,
  RejectedSource,
  SourceForensics,
} from "@/lib/types";

interface LayerInspectorPanelProps {
  queryPlans: Array<Record<string, unknown>>;
  allSourcesFound: DiscoveredSource[];
  selectedSources: DiscoveredSource[];
  rejectedSources: RejectedSource[];
  sourceForensics: SourceForensics[];
  claimScores: ClaimScoreResponse[];
  evidence: EvidenceResponse[];
  layerOutputs: Record<string, unknown>;
}

const shellStyle: CSSProperties = {
  background: "#1e293b",
  borderRadius: 12,
  padding: "1.5rem",
  border: "1px solid #334155",
};

const badgeStyle: CSSProperties = {
  background: "#0f172a",
  borderRadius: 999,
  padding: "0.35rem 0.7rem",
  fontSize: "0.75rem",
  color: "#cbd5e1",
  border: "1px solid #334155",
};

export function LayerInspectorPanel({
  queryPlans,
  allSourcesFound,
  selectedSources,
  rejectedSources,
  sourceForensics,
  claimScores,
  evidence,
  layerOutputs,
}: LayerInspectorPanelProps) {
  return (
    <div style={shellStyle}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: "1rem",
          alignItems: "flex-start",
          marginBottom: "1rem",
          flexWrap: "wrap",
        }}
      >
        <div>
          <h2
            style={{
              fontSize: "1.1rem",
              fontWeight: 600,
              color: "#f1f5f9",
              marginTop: 0,
              marginBottom: "0.35rem",
            }}
          >
            Pipeline Audit
          </h2>
          <div style={{ fontSize: "0.9rem", color: "#94a3b8" }}>
            Ispeziona discovery, forensic analysis, evidence linking e regole finali del verdict.
          </div>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <span style={badgeStyle}>Found: {allSourcesFound.length}</span>
          <span style={badgeStyle}>Selected: {selectedSources.length}</span>
          <span style={badgeStyle}>Rejected: {rejectedSources.length}</span>
          <span style={badgeStyle}>Claims: {claimScores.length}</span>
          <span style={badgeStyle}>Evidence: {evidence.length}</span>
        </div>
      </div>

      <InspectorSection title="Query Planning" defaultOpen>
        {queryPlans.length ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            {queryPlans.map((plan, index) => {
              const claim = stringify(plan.claim);
              const queries = Array.isArray(plan.queries) ? plan.queries : [];
              return (
                <div
                  key={`${stringify(plan.claim_id) || "plan"}-${index}`}
                  style={{
                    background: "#0f172a",
                    borderRadius: 8,
                    padding: "0.9rem 1rem",
                    borderLeft: "4px solid #22c55e",
                  }}
                >
                  <div style={{ fontSize: "0.78rem", color: "#64748b", marginBottom: "0.35rem" }}>
                    {stringify(plan.claim_id) || `claim_${index + 1}`}
                  </div>
                  <div style={{ color: "#e2e8f0", fontSize: "0.92rem", marginBottom: "0.5rem" }}>{claim}</div>
                  <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap" }}>
                    {queries.map((query, queryIndex) => (
                      <span key={queryIndex} style={badgeStyle}>
                        {String(query)}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyState label="Nessun query plan disponibile." />
        )}
      </InspectorSection>

      <InspectorSection title="Discovery">
        <AuditSourceTable title="All Sources Found" items={allSourcesFound} accent="#38bdf8" />
        <AuditSourceTable title="Selected Sources" items={selectedSources} accent="#22c55e" />
        <RejectedSourceTable items={rejectedSources} />
      </InspectorSection>

      <InspectorSection title="Source Forensics">
        {sourceForensics.length ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.75rem" }}>
            {sourceForensics.map((item, index) => (
              <div
                key={`${item.source_id || item.url || item.domain}-${index}`}
                style={{
                  background: "#0f172a",
                  borderRadius: 8,
                  padding: "0.85rem 1rem",
                  borderLeft: `4px solid ${scoreColor(item.forensic_score)}`,
                }}
              >
                <div style={{ color: "#f1f5f9", fontWeight: 600, fontSize: "0.92rem" }}>
                  {item.domain || item.url || `source_${index + 1}`}
                </div>
                <div style={{ color: "#94a3b8", fontSize: "0.78rem", marginTop: "0.2rem" }}>
                  Score {(item.forensic_score * 100).toFixed(0)}% · {item.https ? "https" : "no https"}
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", marginTop: "0.6rem" }}>
                  <span style={miniTagStyle()}>citations {item.citation_count}</span>
                  <span style={miniTagStyle()}>brand risk {toPercent(item.brand_mimicry_risk)}</span>
                  <span style={miniTagStyle()}>quality risk {toPercent(item.low_quality_risk)}</span>
                </div>
                {item.flags && item.flags.length > 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", marginTop: "0.6rem" }}>
                    {item.flags.map((flag) => (
                      <span key={flag} style={miniTagStyle("#7f1d1d", "#fecaca")}>
                        {flag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <EmptyState label="Nessun forensic score disponibile." />
        )}
      </InspectorSection>

      <InspectorSection title="Evidence Linking">
        {evidence.length ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            {evidence.map((item, index) => (
              <div
                key={`${item.source_id}-${index}`}
                style={{
                  background: "#0f172a",
                  borderRadius: 8,
                  padding: "0.85rem 1rem",
                  borderLeft: `4px solid ${item.stance === "contradicting" ? "#ef4444" : item.stance === "supporting" ? "#22c55e" : "#64748b"}`,
                }}
              >
                <div style={{ fontSize: "0.78rem", color: "#94a3b8", marginBottom: "0.35rem" }}>
                  {item.source_id} · {item.stance} · {toPercent(item.evidence_score)}
                </div>
                <div style={{ color: "#e2e8f0", fontSize: "0.9rem", lineHeight: 1.5 }}>{item.excerpt}</div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState label="Nessun evidence excerpt disponibile." />
        )}
      </InspectorSection>

      <InspectorSection title="Claim Scoring">
        {claimScores.length ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "0.75rem" }}>
            {claimScores.map((item) => (
              <div
                key={item.claim_id}
                style={{
                  background: "#0f172a",
                  borderRadius: 8,
                  padding: "0.95rem 1rem",
                  borderLeft: `4px solid ${scoreColor(item.confidence_score)}`,
                }}
              >
                <div style={{ fontSize: "0.78rem", color: "#94a3b8", marginBottom: "0.35rem" }}>
                  {item.claim_id} · {item.partial_verdict}
                </div>
                <div style={{ fontSize: "0.9rem", color: "#e2e8f0", lineHeight: 1.5 }}>{item.claim}</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.45rem", marginTop: "0.75rem" }}>
                  <Metric label="Support" value={toPercent(item.support_score)} />
                  <Metric label="Contradiction" value={toPercent(item.contradiction_score)} />
                  <Metric label="Coverage" value={toPercent(item.claim_coverage)} />
                  <Metric label="Diversity" value={toPercent(item.source_diversity)} />
                  <Metric label="Temporal" value={toPercent(item.temporal_alignment)} />
                  <Metric label="Confidence" value={toPercent(item.confidence_score)} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState label="Nessun claim score disponibile." />
        )}
      </InspectorSection>

      <InspectorSection title="Consistency And Raw Layer Outputs">
        <JsonBlock data={layerOutputs} />
      </InspectorSection>
    </div>
  );
}

function InspectorSection({
  title,
  children,
  defaultOpen = false,
}: {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details
      open={defaultOpen}
      style={{
        background: "#111827",
        borderRadius: 10,
        border: "1px solid #334155",
        marginBottom: "0.9rem",
        overflow: "hidden",
      }}
    >
      <summary
        style={{
          cursor: "pointer",
          color: "#f8fafc",
          fontWeight: 600,
          fontSize: "0.92rem",
          padding: "0.9rem 1rem",
          listStyle: "none",
        }}
      >
        {title}
      </summary>
      <div style={{ padding: "0 1rem 1rem 1rem" }}>{children}</div>
    </details>
  );
}

function AuditSourceTable({
  title,
  items,
  accent,
}: {
  title: string;
  items: DiscoveredSource[];
  accent: string;
}) {
  return (
    <div style={{ marginBottom: "1rem" }}>
      <div style={{ color: "#cbd5e1", fontWeight: 600, marginBottom: "0.5rem" }}>
        {title} ({items.length})
      </div>
      {items.length ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.55rem" }}>
          {items.map((item, index) => (
            <div
              key={`${item.source_id || item.url}-${index}`}
              style={{
                background: "#0f172a",
                borderRadius: 8,
                padding: "0.85rem 1rem",
                borderLeft: `4px solid ${accent}`,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
                <div style={{ color: "#f1f5f9", fontWeight: 600, fontSize: "0.9rem" }}>
                  {item.source_name || item.title || item.domain || item.url}
                </div>
                <div style={{ color: "#93c5fd", fontSize: "0.78rem" }}>
                  Tavily {item.score !== undefined ? item.score.toFixed(2) : "n/a"}
                </div>
              </div>
              <div style={{ fontSize: "0.78rem", color: "#94a3b8", marginTop: "0.25rem" }}>
                {item.url}
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", marginTop: "0.55rem" }}>
                {item.claim_ids?.map((claimId) => (
                  <span key={claimId} style={miniTagStyle()}>
                    {claimId}
                  </span>
                ))}
                {item.selection_reason && <span style={miniTagStyle("#052e16", "#bbf7d0")}>{item.selection_reason}</span>}
                {item.forensic_score !== undefined && (
                  <span style={miniTagStyle()}>forensic {toPercent(item.forensic_score)}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState label="Nessuna fonte disponibile." />
      )}
    </div>
  );
}

function RejectedSourceTable({ items }: { items: RejectedSource[] }) {
  return (
    <div>
      <div style={{ color: "#cbd5e1", fontWeight: 600, marginBottom: "0.5rem" }}>
        Rejected Sources ({items.length})
      </div>
      {items.length ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.55rem" }}>
          {items.map((item, index) => (
            <div
              key={`${item.source_id || item.url || item.reason}-${index}`}
              style={{
                background: "#0f172a",
                borderRadius: 8,
                padding: "0.85rem 1rem",
                borderLeft: "4px solid #f59e0b",
              }}
            >
              <div style={{ color: "#f8fafc", fontSize: "0.9rem" }}>{item.url || item.source_id || "unknown source"}</div>
              <div style={{ color: "#fbbf24", fontSize: "0.78rem", marginTop: "0.25rem" }}>{item.reason}</div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState label="Nessuna fonte rifiutata." />
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: "#111827", borderRadius: 6, padding: "0.45rem 0.55rem" }}>
      <div style={{ color: "#64748b", fontSize: "0.7rem", textTransform: "uppercase" }}>{label}</div>
      <div style={{ color: "#f8fafc", fontWeight: 600, fontSize: "0.86rem" }}>{value}</div>
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return <div style={{ color: "#64748b", fontSize: "0.85rem" }}>{label}</div>;
}

function JsonBlock({ data }: { data: unknown }) {
  return (
    <pre
      style={{
        margin: 0,
        padding: "0.9rem 1rem",
        borderRadius: 8,
        background: "#020617",
        color: "#cbd5e1",
        fontSize: "0.74rem",
        overflowX: "auto",
        lineHeight: 1.55,
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      }}
    >
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

function toPercent(value?: number) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return `${(value * 100).toFixed(0)}%`;
}

function scoreColor(value?: number) {
  if ((value || 0) >= 0.75) {
    return "#22c55e";
  }
  if ((value || 0) >= 0.5) {
    return "#eab308";
  }
  return "#ef4444";
}

function stringify(value: unknown) {
  return typeof value === "string" ? value : "";
}

function miniTagStyle(background = "#1e293b", color = "#cbd5e1"): CSSProperties {
  return {
    fontSize: "0.68rem",
    background,
    color,
    padding: "0.2rem 0.45rem",
    borderRadius: 999,
    border: "1px solid #334155",
  };
}
