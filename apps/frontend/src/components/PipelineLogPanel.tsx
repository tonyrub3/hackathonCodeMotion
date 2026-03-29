"use client";

import { VerifyResponse } from "@/lib/types";

interface PipelineLogPanelProps {
  result: VerifyResponse;
}

export function PipelineLogPanel({ result }: PipelineLogPanelProps) {
  const allResults = result.all_tavily_results || [];
  const hints = result.tavily_answer_hints || [];
  const profile = result.tavily_search_profile || {};
  const temporal = (profile.temporal as Record<string, string> | undefined) || {};
  const trustedDomains = result.trusted_domains || {};

  return (
    <details
      style={{
        background: "#1e293b",
        borderRadius: 12,
        border: "1px solid #334155",
        overflow: "hidden",
      }}
    >
      <summary
        style={{
          listStyle: "none",
          cursor: "pointer",
          padding: "1rem 1.5rem",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "1rem",
        }}
      >
        <span
          style={{
            fontSize: "1.05rem",
            fontWeight: 600,
            color: "#f1f5f9",
          }}
        >
          Diagnostic Trace
        </span>
        <span
          style={{
            color: "#94a3b8",
            fontSize: "0.82rem",
          }}
        >
          Apri per vedere workflow, retrieval, scoring e whitelist domini
        </span>
      </summary>
      <div
        style={{
          padding: "0 1.5rem 1.5rem",
          borderTop: "1px solid #334155",
        }}
      >
      <h2
        style={{
          fontSize: "1.1rem",
          fontWeight: 600,
          color: "#f1f5f9",
          marginTop: 0,
          marginBottom: "0.25rem",
          paddingTop: "1rem",
        }}
      >
        Pipeline Trace
      </h2>
      <p
        style={{
          color: "#94a3b8",
          fontSize: "0.9rem",
          marginTop: 0,
          marginBottom: "1rem",
          lineHeight: 1.5,
        }}
      >
        Vista operativa dei layer eseguiti dal backend. E utile soprattutto sugli URL
        per capire cosa e stato estratto, cosa e stato cercato e quali fonti sono
        entrate nel cross-check.
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <LogSection title="[INPUT]" accent="#38bdf8">
          <LogRow label="Input type" value={result.input_type} />
          <LogRow label="Mode" value={result.mode} />
          {result.input_type === "url" && (
            <>
              <LogRow label="Source URL" value={result.source_url || "n/a"} mono />
              <LogRow label="Article title" value={result.article_title || "n/a"} />
              <LogRow label="Article author" value={result.article_author || "n/a"} />
              <LogRow label="Article date" value={result.article_date || "n/a"} />
              <LogRow label="Cited links" value={String(result.cited_links.length)} />
              {result.cited_links.length > 0 && (
                <LinkList links={result.cited_links.slice(0, 10)} />
              )}
            </>
          )}
        </LogSection>

        <LogSection title="[CLAIMS]" accent="#14b8a6">
          <LogRow label="Extracted claims" value={String(result.claims.length)} />
          {result.claims.length > 0 ? (
            <Subsection title="Claim decomposition">
              {result.claims.map((claim) => (
                <TraceCard
                  key={claim.id}
                  title={`${claim.id} · ${claim.type}`}
                  subtitle={`checkability ${(claim.checkability_score * 100).toFixed(0)}%`}
                  body={claim.claim}
                />
              ))}
            </Subsection>
          ) : (
            <MutedText>No claim decomposition available for this input.</MutedText>
          )}
        </LogSection>

        <LogSection title="[QUERY]" accent="#22c55e">
          <LogRow label="Generated queries" value={String(result.generated_queries.length)} />
          {result.generated_queries.length > 0 ? (
            <ol style={listStyle}>
              {result.generated_queries.map((query, index) => (
                <li key={`${query}-${index}`} style={listItemStyle}>
                  <code style={codeStyle}>{query}</code>
                </li>
              ))}
            </ol>
          ) : (
            <MutedText>No query data available.</MutedText>
          )}
        </LogSection>

        <LogSection title="[RETRIEVAL]" accent="#f59e0b">
          <LogRow label="Topic" value={String(profile.topic || "n/a")} />
          <LogRow label="Country" value={String(profile.country || "n/a")} />
          <LogRow
            label="Temporal filters"
            value={Object.keys(temporal).length ? JSON.stringify(temporal) : "none"}
            mono
          />
          <LogRow label="All Tavily results" value={String(allResults.length)} />
          <LogRow label="Answer hints" value={String(hints.length)} />

          {hints.length > 0 && (
            <Subsection title="Answer hints">
              {hints.map((hint, index) => (
                <TraceCard
                  key={`hint-${index}`}
                  title={String(hint.query || `hint-${index + 1}`)}
                  subtitle={`${hint.tier || "unknown"} · ${hint.topic || "n/a"}`}
                  body={String(hint.answer || "")}
                />
              ))}
            </Subsection>
          )}

          {allResults.length > 0 && (
            <Subsection title="Raw Tavily results">
              {allResults.slice(0, 12).map((item, index) => (
                <TraceCard
                  key={`result-${index}`}
                  title={String(item.title || item.url || `result-${index + 1}`)}
                  subtitle={[
                    String(item._retrieval_tier || "tier?"),
                    `score ${(Number(item.score || 0) * 100).toFixed(0)}%`,
                    item._query ? `query: ${String(item._query)}` : "",
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                  body={String(item.url || "")}
                  mono
                />
              ))}
            </Subsection>
          )}

          {Object.keys(trustedDomains).length > 0 && (
            <Subsection title="Trusted domain whitelist">
              {Object.entries(trustedDomains).map(([groupName, domains]) => (
                <TraceCard
                  key={groupName}
                  title={groupName.replace(/_/g, " ")}
                  subtitle={`${domains.length} domain${domains.length === 1 ? "" : "s"}`}
                  body={domains.join(", ")}
                  mono
                />
              ))}
            </Subsection>
          )}
        </LogSection>

        <LogSection title="[SCORING + ANALYSIS]" accent="#a78bfa">
          <LogRow label="Selected sources" value={String(result.sources_used.length)} />
          <LogRow label="Evidence items" value={String(result.evidence.length)} />
          <LogRow label="Contradictions" value={String(result.contradictions.length)} />

          {result.sources_used.length > 0 && (
            <Subsection title="Selected sources">
              {result.sources_used.map((source) => (
                <TraceCard
                  key={source.source_id}
                  title={source.source_name || source.source_id}
                  subtitle={[
                    source.tier ? `tier ${source.tier}` : "",
                    `trust ${(source.source_reliability_score * 100).toFixed(0)}%`,
                    source.source_type,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                  body={source.url}
                  footer={
                    <DimensionChips dimensions={source.dimensions} />
                  }
                  mono
                />
              ))}
            </Subsection>
          )}

          {result.evidence.length > 0 && (
            <Subsection title="Evidence trace">
              {result.evidence.map((evidence, index) => (
                <TraceCard
                  key={`${evidence.source_id}-${index}`}
                  title={`${evidence.source_id} · ${evidence.stance}`}
                  subtitle={`evidence ${(evidence.evidence_score * 100).toFixed(0)}%`}
                  body={evidence.excerpt || "No excerpt"}
                />
              ))}
            </Subsection>
          )}
        </LogSection>

        <LogSection title="[OUTPUT]" accent="#f43f5e">
          <LogRow label="Verdict" value={result.verdict} />
          <LogRow label="Truth score" value={result.truth_score.toFixed(0)} />
          <LogRow label="Confidence" value={`${(result.confidence_score * 100).toFixed(0)}%`} />
          <LogRow
            label="Timings"
            value={Object.keys(result.timings).length ? JSON.stringify(result.timings) : "none"}
            mono
          />
          <LogRow label="Errors" value={String(result.errors.length)} />
          {result.errors.length > 0 && (
            <ul style={listStyle}>
              {result.errors.map((error, index) => (
                <li key={`error-${index}`} style={{ ...listItemStyle, color: "#fca5a5" }}>
                  {error}
                </li>
              ))}
            </ul>
          )}
        </LogSection>
      </div>
      </div>
    </details>
  );
}

function LogSection({
  title,
  accent,
  children,
}: {
  title: string;
  accent: string;
  children: React.ReactNode;
}) {
  return (
    <section
      style={{
        background: "#0f172a",
        borderRadius: 10,
        padding: "1rem",
        borderLeft: `4px solid ${accent}`,
      }}
    >
      <h3
        style={{
          marginTop: 0,
          marginBottom: "0.85rem",
          color: accent,
          fontSize: "0.9rem",
          letterSpacing: "0.06em",
        }}
      >
        {title}
      </h3>
      {children}
    </section>
  );
}

function Subsection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginTop: "0.9rem" }}>
      <div
        style={{
          color: "#94a3b8",
          fontSize: "0.78rem",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: "0.5rem",
        }}
      >
        {title}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>{children}</div>
    </div>
  );
}

function LogRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "180px 1fr",
        gap: "0.75rem",
        marginBottom: "0.4rem",
        alignItems: "start",
      }}
    >
      <div style={{ color: "#64748b", fontSize: "0.78rem", textTransform: "uppercase" }}>
        {label}
      </div>
      <div
        style={{
          color: "#e2e8f0",
          fontSize: "0.9rem",
          fontFamily: mono ? "ui-monospace, SFMono-Regular, Menlo, monospace" : "inherit",
          overflowWrap: "anywhere",
        }}
      >
        {value}
      </div>
    </div>
  );
}

function TraceCard({
  title,
  subtitle,
  body,
  footer,
  mono = false,
}: {
  title: string;
  subtitle: string;
  body: string;
  footer?: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div
      style={{
        background: "#111827",
        borderRadius: 8,
        padding: "0.75rem 0.85rem",
        border: "1px solid #1f2937",
      }}
    >
      <div style={{ color: "#f8fafc", fontSize: "0.86rem", fontWeight: 600, marginBottom: "0.2rem" }}>
        {title}
      </div>
      <div style={{ color: "#94a3b8", fontSize: "0.74rem", marginBottom: "0.35rem" }}>{subtitle}</div>
      <div
        style={{
          color: "#cbd5e1",
          fontSize: "0.84rem",
          lineHeight: 1.5,
          fontFamily: mono ? "ui-monospace, SFMono-Regular, Menlo, monospace" : "inherit",
          overflowWrap: "anywhere",
        }}
      >
        {body}
      </div>
      {footer ? <div style={{ marginTop: "0.5rem" }}>{footer}</div> : null}
    </div>
  );
}

function DimensionChips({ dimensions }: { dimensions: Record<string, number> }) {
  const entries = Object.entries(dimensions || {});
  if (!entries.length) return null;
  return (
    <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
      {entries.map(([key, value]) => (
        <span
          key={key}
          style={{
            fontSize: "0.65rem",
            background: "#1e293b",
            padding: "2px 6px",
            borderRadius: 999,
            color: "#93c5fd",
          }}
        >
          {key}: {(value * 100).toFixed(0)}%
        </span>
      ))}
    </div>
  );
}

function LinkList({ links }: { links: string[] }) {
  return (
    <div style={{ marginTop: "0.5rem" }}>
      {links.map((link, index) => (
        <div key={`${link}-${index}`} style={{ marginBottom: "0.25rem" }}>
          <a
            href={link}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: "#60a5fa",
              fontSize: "0.83rem",
              overflowWrap: "anywhere",
            }}
          >
            {link}
          </a>
        </div>
      ))}
    </div>
  );
}

function MutedText({ children }: { children: React.ReactNode }) {
  return <div style={{ color: "#94a3b8", fontSize: "0.86rem" }}>{children}</div>;
}

const listStyle: React.CSSProperties = {
  margin: 0,
  paddingLeft: "1.2rem",
};

const listItemStyle: React.CSSProperties = {
  color: "#cbd5e1",
  fontSize: "0.85rem",
  marginBottom: 6,
};

const codeStyle: React.CSSProperties = {
  color: "#86efac",
  fontSize: "0.82rem",
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
  overflowWrap: "anywhere",
};
