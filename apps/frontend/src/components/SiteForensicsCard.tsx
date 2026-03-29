"use client";

import { SiteForensics } from "@/lib/types";

interface SiteForensicsCardProps {
  forensics: SiteForensics;
}

export function SiteForensicsCard({ forensics }: SiteForensicsCardProps) {
  const trustColor =
    forensics.site_trust_score >= 0.7
      ? "#22c55e"
      : forensics.site_trust_score >= 0.4
      ? "#eab308"
      : "#ef4444";

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
        Site Forensics
      </h2>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "0.75rem",
        }}
      >
        <Stat label="Domain" value={forensics.domain} />
        <Stat label="TLD" value={`.${forensics.tld}`} />
        <Stat
          label="HTTPS"
          value={forensics.https ? "Yes" : "No"}
          color={forensics.https ? "#22c55e" : "#ef4444"}
        />
        <Stat label="Site Age" value={forensics.site_age_signal} />
        <Stat
          label="Author"
          value={
            forensics.author_present
              ? forensics.author_name || "Present"
              : "Not found"
          }
          color={forensics.author_present ? "#22c55e" : "#f97316"}
        />
        <Stat
          label="Citations"
          value={`${forensics.citation_count} (${forensics.primary_source_citations} primary)`}
        />
        <Stat
          label="Brand Mimicry Risk"
          value={`${(forensics.brand_mimicry_risk * 100).toFixed(0)}%`}
          color={forensics.brand_mimicry_risk > 0.3 ? "#ef4444" : "#22c55e"}
        />
        <Stat
          label="Headline/Body Match"
          value={`${((1 - forensics.headline_body_mismatch) * 100).toFixed(0)}%`}
        />
      </div>

      <div
        style={{
          marginTop: "1rem",
          textAlign: "center",
          padding: "0.5rem",
          background: "#0f172a",
          borderRadius: 8,
        }}
      >
        <div style={{ fontSize: "1.4rem", fontWeight: 700, color: trustColor }}>
          {(forensics.site_trust_score * 100).toFixed(0)}%
        </div>
        <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
          Site Trust Score
        </div>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div>
      <div
        style={{ fontSize: "0.7rem", color: "#64748b", textTransform: "uppercase" }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: "0.9rem",
          color: color || "#e2e8f0",
          fontWeight: 500,
        }}
      >
        {value}
      </div>
    </div>
  );
}
