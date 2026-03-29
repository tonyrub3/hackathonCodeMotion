"use client";

import { useState, useEffect } from "react";
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
import { PipelineLogPanel } from "@/components/PipelineLogPanel";

const FULL_TEXT = "Project: Aletheia";
const TYPING_SPEED = 100; // ms per character
const PAUSE_VISIBLE = 5000; // ms to stay fully visible
const PAUSE_HIDDEN = 500; // ms to stay empty before retyping
const PRIMARY_GREEN = "#00e676";

type Phase = "typing" | "visible" | "deleting" | "hidden";

function TypingTitle() {
  const [displayedCount, setDisplayedCount] = useState(0);
  const [phase, setPhase] = useState<Phase>("typing");

  useEffect(() => {
    if (phase === "typing") {
      if (displayedCount < FULL_TEXT.length) {
        const t = setTimeout(() => setDisplayedCount((c) => c + 1), TYPING_SPEED);
        return () => clearTimeout(t);
      } else {
        setPhase("visible");
      }
    } else if (phase === "visible") {
      const t = setTimeout(() => setPhase("deleting"), PAUSE_VISIBLE);
      return () => clearTimeout(t);
    } else if (phase === "deleting") {
      if (displayedCount > 0) {
        const t = setTimeout(() => setDisplayedCount((c) => c - 1), TYPING_SPEED);
        return () => clearTimeout(t);
      } else {
        setPhase("hidden");
      }
    } else if (phase === "hidden") {
      const t = setTimeout(() => setPhase("typing"), PAUSE_HIDDEN);
      return () => clearTimeout(t);
    }
  }, [displayedCount, phase]);

  const prefixEnd = Math.min(displayedCount, 9); // "Project: " is 9 chars
  const prefix = FULL_TEXT.slice(0, prefixEnd);
  const greenPart = displayedCount > 9 ? FULL_TEXT.slice(9, displayedCount) : "";
  const showCursor = phase !== "visible";

  return (
    <h1
      style={{
        fontSize: "3.5rem",
        fontWeight: 700,
        letterSpacing: "-0.02em",
        margin: 0,
        lineHeight: 1.2,
        minHeight: "4.2rem",
      }}
    >
      <span style={{ color: "#000000" }}>{prefix}</span>
      <span style={{ color: PRIMARY_GREEN }}>{greenPart}</span>
      <span
        style={{
          display: "inline-block",
          width: "3px",
          height: "3.5rem",
          backgroundColor: PRIMARY_GREEN,
          marginLeft: "2px",
          verticalAlign: "text-bottom",
          animation: showCursor ? "blink 0.7s step-end infinite" : "none",
          opacity: showCursor ? 1 : 0,
        }}
      />
      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </h1>
  );
}

export default function Home() {
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [useMock] = useState(false);

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
    <main
      style={{
        maxWidth: 960,
        margin: "0 auto",
        padding: "2rem 1rem",
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Title - top area */}
      <div style={{ textAlign: "center", paddingTop: "15vh" }}>
        <TypingTitle />
      </div>

      {/* Search area */}
      <div
        style={{
          marginTop: "5vh",
          width: "100%",
          textAlign: "center",
        }}
      >
        <p
          style={{
            color: "#000000",
            fontSize: "1.1rem",
            marginBottom: "1rem",
            fontWeight: 500,
          }}
        >
          Chiedimi qualcosa...
        </p>
        <InputBox onSubmit={handleSubmit} loading={loading} />
      </div>

      {error && (
        <div
          style={{
            background: "#fde8e8",
            color: "#b91c1c",
            padding: "0.75rem 1rem",
            borderRadius: 8,
            marginTop: "1rem",
          }}
        >
          {error}
        </div>
      )}

      {result && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "1.5rem",
            marginTop: "1.5rem",
          }}
        >
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

          <PipelineLogPanel result={result} />
        </div>
      )}
    </main>
  );
}
