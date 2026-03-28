"use client";

import { useState } from "react";
import { VerifyResponse } from "@/lib/types";
import { verifyContent } from "@/lib/api";
import { MOCK_RESPONSE } from "@/lib/mock";
import { InputBox } from "@/components/InputBox";
import { VerdictCard } from "@/components/VerdictCard";
import { ClaimList } from "@/components/ClaimList";
import { SourceReliabilityPanel } from "@/components/SourceReliabilityPanel";
import { ExplanationPanel } from "@/components/ExplanationPanel";
import { SiteForensicsCard } from "@/components/SiteForensicsCard";
import { ConflictPanel } from "@/components/ConflictPanel";

export default function Home() {
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [useMock, setUseMock] = useState(false);

  const handleSubmit = async (content: string, inputType: "text" | "url") => {
    setError("");
    setLoading(true);
    try {
      if (useMock) {
        setResult(MOCK_RESPONSE);
      } else {
        const resp = await verifyContent({
          input_type: inputType,
          content,
        });
        setResult(resp);
      }
    } catch (e: any) {
      setError(e.message || "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: "2rem 1rem" }}>
      <header style={{ textAlign: "center", marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "2rem", fontWeight: 700, color: "#f1f5f9" }}>
          Truth Engine
        </h1>
        <p style={{ color: "#94a3b8", fontSize: "0.95rem" }}>
          Explainable, source-traced fact-checking
        </p>
        <label
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            marginTop: 8,
            fontSize: "0.8rem",
            color: "#64748b",
            cursor: "pointer",
          }}
        >
          <input
            type="checkbox"
            checked={useMock}
            onChange={(e) => setUseMock(e.target.checked)}
          />
          Use mock data (demo)
        </label>
      </header>

      <InputBox onSubmit={handleSubmit} loading={loading} />

      {error && (
        <div
          style={{
            background: "#7f1d1d",
            color: "#fca5a5",
            padding: "0.75rem 1rem",
            borderRadius: 8,
            marginTop: "1rem",
          }}
        >
          {error}
        </div>
      )}

      {result && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem", marginTop: "1.5rem" }}>
          <VerdictCard
            verdict={result.verdict}
            truthScore={result.truth_score}
            confidenceScore={result.confidence_score}
          />

          <ClaimList claims={result.claims} />

          <SourceReliabilityPanel sources={result.sources_used} />

          {result.contradictions.length > 0 && (
            <ConflictPanel contradictions={result.contradictions} />
          )}

          {result.site_forensics && (
            <SiteForensicsCard forensics={result.site_forensics} />
          )}

          <ExplanationPanel explanation={result.explanation} />
        </div>
      )}
    </main>
  );
}
