"use client";

import { useState } from "react";

interface InputBoxProps {
  onSubmit: (content: string, inputType: "text" | "url") => void;
  loading: boolean;
}

export function InputBox({ onSubmit, loading }: InputBoxProps) {
  const [content, setContent] = useState("");
  const [inputType, setInputType] = useState<"text" | "url">("text");

  const handleSubmit = () => {
    if (!content.trim()) return;
    onSubmit(content.trim(), inputType);
  };

  return (
    <div
      style={{
        background: "#1e293b",
        borderRadius: 12,
        padding: "1.5rem",
        border: "1px solid #334155",
      }}
    >
      <div style={{ display: "flex", gap: "1rem", marginBottom: "0.75rem" }}>
        <button
          onClick={() => setInputType("text")}
          style={{
            padding: "0.4rem 1rem",
            borderRadius: 6,
            border: "1px solid #475569",
            background: inputType === "text" ? "#3b82f6" : "transparent",
            color: inputType === "text" ? "#fff" : "#94a3b8",
            cursor: "pointer",
            fontSize: "0.85rem",
          }}
        >
          Text
        </button>
        <button
          onClick={() => setInputType("url")}
          style={{
            padding: "0.4rem 1rem",
            borderRadius: 6,
            border: "1px solid #475569",
            background: inputType === "url" ? "#3b82f6" : "transparent",
            color: inputType === "url" ? "#fff" : "#94a3b8",
            cursor: "pointer",
            fontSize: "0.85rem",
          }}
        >
          URL
        </button>
      </div>

      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder={
          inputType === "url"
            ? "Paste an article URL..."
            : "Paste text or article content to verify..."
        }
        rows={5}
        style={{
          width: "100%",
          background: "#0f172a",
          border: "1px solid #334155",
          borderRadius: 8,
          padding: "0.75rem",
          color: "#e2e8f0",
          fontSize: "0.9rem",
          resize: "vertical",
          boxSizing: "border-box",
        }}
      />

      <button
        onClick={handleSubmit}
        disabled={loading || !content.trim()}
        style={{
          marginTop: "0.75rem",
          width: "100%",
          padding: "0.7rem",
          borderRadius: 8,
          border: "none",
          background: loading ? "#475569" : "#3b82f6",
          color: "#fff",
          fontSize: "0.95rem",
          fontWeight: 600,
          cursor: loading ? "not-allowed" : "pointer",
        }}
      >
        {loading ? "Analyzing..." : "Verify"}
      </button>
    </div>
  );
}
