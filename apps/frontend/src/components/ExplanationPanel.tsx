"use client";

import { ExplanationResponse } from "@/lib/types";

interface ExplanationPanelProps {
  explanation: ExplanationResponse;
}

export function ExplanationPanel({ explanation }: ExplanationPanelProps) {
  return (
    <div
      style={{
        background: "#1e293b",
        borderRadius: 12,
        padding: "1.5rem",
        border: "1px solid #334155",
      }}
    >
      <h2
        style={{
          fontSize: "1.1rem",
          fontWeight: 600,
          color: "#f1f5f9",
          marginTop: 0,
          marginBottom: "1rem",
        }}
      >
        Explanation
      </h2>

      <Section title="Summary">{explanation.summary}</Section>
      <Section title="Why this verdict">{explanation.why}</Section>

      {explanation.supporting_evidence.length > 0 && (
        <Section title="Supporting evidence">
          <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
            {explanation.supporting_evidence.map((e, i) => (
              <li key={i} style={{ color: "#22c55e", fontSize: "0.85rem", marginBottom: 4 }}>
                <span style={{ color: "#cbd5e1" }}>{e}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {explanation.contradicting_evidence.length > 0 && (
        <Section title="Contradicting evidence">
          <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
            {explanation.contradicting_evidence.map((e, i) => (
              <li key={i} style={{ color: "#ef4444", fontSize: "0.85rem", marginBottom: 4 }}>
                <span style={{ color: "#cbd5e1" }}>{e}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {explanation.source_analysis.length > 0 && (
        <Section title="Source analysis">
          <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
            {explanation.source_analysis.map((s, i) => (
              <li key={i} style={{ fontSize: "0.85rem", color: "#cbd5e1", marginBottom: 4 }}>
                {s}
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Temporal context">{explanation.temporal_context}</Section>

      {explanation.caveats.length > 0 && (
        <Section title="Caveats">
          <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
            {explanation.caveats.map((c, i) => (
              <li key={i} style={{ fontSize: "0.85rem", color: "#fbbf24", marginBottom: 4 }}>
                {c}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: "1rem" }}>
      <h3
        style={{
          fontSize: "0.85rem",
          fontWeight: 600,
          color: "#94a3b8",
          marginBottom: "0.3rem",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        {title}
      </h3>
      <div style={{ fontSize: "0.9rem", color: "#cbd5e1", lineHeight: 1.5 }}>
        {children}
      </div>
    </div>
  );
}
