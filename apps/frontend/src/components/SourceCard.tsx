"use client";

import { SourceResponse } from "@/lib/types";

/** Standalone SourceCard – re-exported for flexibility. */
export function SourceCard({ source }: { source: SourceResponse }) {
  const tierColor =
    source.tier === "A" ? "#22c55e" : source.tier === "B" ? "#eab308" : "#ef4444";

  return (
    <div
      style={{
        background: "#0f172a",
        borderRadius: 8,
        padding: "0.75rem 1rem",
        borderLeft: `4px solid ${tierColor}`,
      }}
    >
      <div style={{ fontWeight: 600, color: "#f1f5f9", fontSize: "0.9rem" }}>
        {source.source_name || source.source_id}
      </div>
      <div style={{ fontSize: "0.75rem", color: "#64748b" }}>
        {source.source_type} | Tier {source.tier} |{" "}
        Reliability: {(source.source_reliability_score * 100).toFixed(0)}%
      </div>
    </div>
  );
}
