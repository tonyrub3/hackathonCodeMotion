"use client";

import { ClaimResponse } from "@/lib/types";

const VERDICT_COLORS: Record<string, string> = {
  verified: "#22c55e",
  mostly_verified: "#84cc16",
  mixed: "#eab308",
  misleading: "#f97316",
  decontextualized: "#a855f7",
  insufficient_evidence: "#6b7280",
  mostly_false: "#ef4444",
  false: "#dc2626",
};

interface ClaimListProps {
  claims: ClaimResponse[];
}

export function ClaimList({ claims }: ClaimListProps) {
  if (!claims.length) return null;

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
        Claims ({claims.length})
      </h2>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        {claims.map((claim) => {
          const color =
            VERDICT_COLORS[claim.partial_verdict] || "#6b7280";
          return (
            <div
              key={claim.id}
              style={{
                background: "#0f172a",
                borderRadius: 8,
                padding: "0.75rem 1rem",
                borderLeft: `4px solid ${color}`,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "0.3rem",
                }}
              >
                <span
                  style={{
                    fontSize: "0.7rem",
                    color: "#64748b",
                    textTransform: "uppercase",
                  }}
                >
                  {claim.type} &middot; {claim.id}
                </span>
                <span
                  style={{
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    color,
                  }}
                >
                  {claim.partial_verdict.replace(/_/g, " ")} ({claim.partial_score.toFixed(0)})
                </span>
              </div>
              <div style={{ fontSize: "0.9rem", color: "#cbd5e1" }}>
                {claim.claim}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
