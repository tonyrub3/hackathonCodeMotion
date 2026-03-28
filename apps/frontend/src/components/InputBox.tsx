"use client";

import { useState, useRef } from "react";

const PRIMARY_GREEN = "#00e676";

interface InputBoxProps {
  onSubmit: (content: string, inputType: "text" | "url") => void;
  loading: boolean;
}

export function InputBox({ onSubmit, loading }: InputBoxProps) {
  const [content, setContent] = useState("");
  const [inputType, setInputType] = useState<"text" | "url" | "image">("text");
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = () => {
    if (inputType === "image") {
      if (!uploadedFile) return;
      // TODO: handle image upload submission
      return;
    }
    if (!content.trim()) return;
    onSubmit(content.trim(), inputType);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleImageSelect = () => {
    setInputType("image");
    fileInputRef.current?.click();
  };

  const canSubmit =
    inputType === "image" ? !!uploadedFile : !!content.trim();

  return (
    <div
      style={{
        position: "relative",
        borderRadius: 24,
        padding: 2,
      }}
    >
      {/* Animated glow border */}
      <div
        style={{
          position: "absolute",
          inset: -3,
          borderRadius: 27,
          background: `conic-gradient(from var(--glow-angle, 0deg), transparent 0%, ${PRIMARY_GREEN}99 10%, transparent 20%, transparent 45%, ${PRIMARY_GREEN}66 55%, transparent 65%, transparent 90%, ${PRIMARY_GREEN}88 100%)`,
          animation: "glowRotate 6s linear infinite",
          filter: "blur(6px)",
          zIndex: 0,
        }}
      />

      {/* Inner box */}
      <div
        style={{
          position: "relative",
          background: "#f5f5f5",
          borderRadius: 24,
          padding: "0.75rem 1rem",
          border: "1.5px solid #555555",
          display: "flex",
          alignItems: "flex-end",
          gap: "0.5rem",
          zIndex: 1,
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          style={{ display: "none" }}
          onChange={(e) => {
            const file = e.target.files?.[0] || null;
            setUploadedFile(file);
            if (!file) setInputType("text");
          }}
        />

        {inputType === "image" && uploadedFile ? (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.5rem 0.25rem",
              color: "#000000",
              fontSize: "0.95rem",
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={PRIMARY_GREEN} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <polyline points="21 15 16 10 5 21" />
            </svg>
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {uploadedFile.name}
            </span>
            <button
              onClick={() => {
                setUploadedFile(null);
                setInputType("text");
                if (fileInputRef.current) fileInputRef.current.value = "";
              }}
              style={{
                background: "none",
                border: "none",
                color: "#999",
                cursor: "pointer",
                fontSize: "1.1rem",
                padding: "0 4px",
                lineHeight: 1,
              }}
            >
              ×
            </button>
          </div>
        ) : (
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              inputType === "url"
                ? "Incolla un URL da verificare..."
                : "Incolla un testo o un articolo da verificare..."
            }
            rows={1}
            style={{
              flex: 1,
              background: "transparent",
              border: "none",
              outline: "none",
              padding: "0.5rem 0.25rem",
              color: "#000000",
              fontSize: "0.95rem",
              resize: "none",
              lineHeight: 1.5,
              fontFamily: "inherit",
            }}
          />
        )}

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            flexShrink: 0,
            paddingBottom: "0.25rem",
          }}
        >
          {(["text", "url", "image"] as const).map((type) => {
            const isActive = inputType === type;
            return (
              <button
                key={type}
                onClick={() => {
                  if (type === "image") {
                    handleImageSelect();
                  } else {
                    setInputType(type);
                    setUploadedFile(null);
                    if (fileInputRef.current) fileInputRef.current.value = "";
                  }
                }}
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: "50%",
                  border: "none",
                  background: isActive ? PRIMARY_GREEN : "#e0e0e0",
                  color: isActive ? "#ffffff" : "#999999",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  transition: "all 0.25s ease",
                  boxShadow: isActive
                    ? `0 0 12px ${PRIMARY_GREEN}88, 0 0 4px ${PRIMARY_GREEN}66`
                    : "none",
                }}
                aria-label={type === "text" ? "Testo" : type === "url" ? "URL" : "Immagine"}
              >
                {type === "text" ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 7V4h16v3" />
                    <line x1="12" y1="4" x2="12" y2="20" />
                    <line x1="8" y1="20" x2="16" y2="20" />
                  </svg>
                ) : type === "url" ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
                  </svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                    <circle cx="8.5" cy="8.5" r="1.5" />
                    <polyline points="21 15 16 10 5 21" />
                  </svg>
                )}
              </button>
            );
          })}

          <button
            onClick={handleSubmit}
            disabled={loading || !canSubmit}
            style={{
              width: 36,
              height: 36,
              borderRadius: "50%",
              border: "none",
              background: loading || !canSubmit ? "#cccccc" : PRIMARY_GREEN,
              color: "#ffffff",
              fontSize: "1.2rem",
              cursor: loading || !canSubmit ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              transition: "background 0.2s",
            }}
            aria-label="Invia"
          >
            {loading ? (
              <span
                style={{
                  display: "inline-block",
                  width: 16,
                  height: 16,
                  border: "2px solid #ffffff",
                  borderTopColor: "transparent",
                  borderRadius: "50%",
                  animation: "spin 0.6s linear infinite",
                }}
              />
            ) : (
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="12" y1="19" x2="12" y2="5" />
                <polyline points="5 12 12 5 19 12" />
              </svg>
            )}
          </button>
        </div>
      </div>

      <style>{`
        @property --glow-angle {
          syntax: "<angle>";
          initial-value: 0deg;
          inherits: false;
        }
        @keyframes glowRotate {
          to { --glow-angle: 360deg; }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
