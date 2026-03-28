"use client";

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

interface VerdictCardProps {
  verdict: string;
  truthScore: number;
  confidenceScore: number;
}

export function VerdictCard({
  verdict,
  truthScore,
  confidenceScore,
}: VerdictCardProps) {
  const color = VERDICT_COLORS[verdict] || "#6b7280";
  const label = verdict.replace(/_/g, " ").toUpperCase();

  return (
    <div
      style={{
        background: "#1e293b",
        borderRadius: 12,
        padding: "1.5rem",
        border: `2px solid ${color}`,
        textAlign: "center",
      }}
    >
      <div
        style={{
          fontSize: "1.6rem",
          fontWeight: 800,
          color,
          marginBottom: "0.5rem",
        }}
      >
        {label}
      </div>

      <div
        style={{
          display: "flex",
          justifyContent: "center",
          gap: "2rem",
          marginTop: "0.75rem",
        }}
      >
        <div>
          <div style={{ fontSize: "2rem", fontWeight: 700, color: "#f1f5f9" }}>
            {truthScore.toFixed(0)}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
            Truth Score
          </div>
        </div>
        <div>
          <div style={{ fontSize: "2rem", fontWeight: 700, color: "#f1f5f9" }}>
            {(confidenceScore * 100).toFixed(0)}%
          </div>
          <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
            Confidence
          </div>
        </div>
      </div>
    </div>
  );
}
