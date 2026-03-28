"use client";

import { SourceResponse } from "@/lib/types";

interface SourceReliabilityPanelProps {
  sources: SourceResponse[];
}

export function SourceReliabilityPanel({
  sources,
}: SourceReliabilityPanelProps) {
  if (!sources.length) return null;

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
        Sources ({sources.length})
      </h2>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        {sources.map((src) => (
          <SourceCard key={src.source_id} source={src} />
        ))}
      </div>
    </div>
  );
}

function SourceCard({ source }: { source: SourceResponse }) {
  const tierColor =
    source.tier === "A"
      ? "#22c55e"
      : source.tier === "B"
      ? "#eab308"
      : "#ef4444";

  const dims = source.dimensions || {};

  return (
    <div
      style={{
        background: "#0f172a",
        borderRadius: 8,
        padding: "0.75rem 1rem",
        borderLeft: `4px solid ${tierColor}`,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: "0.3rem",
        }}
      >
        <span style={{ fontWeight: 600, color: "#f1f5f9", fontSize: "0.9rem" }}>
          {source.source_name || source.source_id}
        </span>
        <span
          style={{
            fontSize: "0.75rem",
            color: tierColor,
            fontWeight: 600,
          }}
        >
          Tier {source.tier} &middot;{" "}
          {(source.source_reliability_score * 100).toFixed(0)}%
        </span>
      </div>

      <div style={{ fontSize: "0.75rem", color: "#64748b", marginBottom: "0.5rem" }}>
        {source.source_type} &middot;{" "}
        {source.url ? (
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "#60a5fa" }}
          >
            {source.url.slice(0, 60)}
          </a>
        ) : (
          "No URL"
        )}
      </div>

      {Object.keys(dims).length > 0 && (
        <div
          style={{
            display: "flex",
            gap: "0.5rem",
            flexWrap: "wrap",
            marginTop: "0.3rem",
          }}
        >
          {Object.entries(dims).map(([key, val]) => (
            <span
              key={key}
              style={{
                fontSize: "0.65rem",
                background: "#1e293b",
                padding: "2px 6px",
                borderRadius: 4,
                color: "#94a3b8",
              }}
            >
              {key}: {((val as number) * 100).toFixed(0)}%
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
