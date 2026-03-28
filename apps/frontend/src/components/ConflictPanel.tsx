"use client";

import { ContradictionResponse } from "@/lib/types";

interface ConflictPanelProps {
  contradictions: ContradictionResponse[];
}

export function ConflictPanel({ contradictions }: ConflictPanelProps) {
  if (!contradictions.length) return null;

  return (
    <div
      style={{
        background: "#1e293b",
        borderRadius: 12,
        padding: "1.5rem",
        border: "1px solid #7f1d1d",
      }}
    >
      <h2
        style={{
          fontSize: "1.1rem",
          fontWeight: 600,
          color: "#fca5a5",
          marginTop: 0,
          marginBottom: "1rem",
        }}
      >
        Contradictions ({contradictions.length})
      </h2>

      {contradictions.map((c, i) => (
        <div
          key={i}
          style={{
            background: "#0f172a",
            borderRadius: 8,
            padding: "0.75rem 1rem",
            borderLeft: "4px solid #ef4444",
            marginBottom: "0.5rem",
          }}
        >
          <div style={{ fontSize: "0.75rem", color: "#64748b" }}>
            {c.claim_id} &middot; {c.type}
          </div>
          <div style={{ fontSize: "0.9rem", color: "#cbd5e1" }}>
            {c.description}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#f87171", marginTop: 4 }}>
            Severity: {(c.severity * 100).toFixed(0)}%
          </div>
        </div>
      ))}
    </div>
  );
}
