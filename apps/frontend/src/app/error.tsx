"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "50vh",
        padding: "2rem",
        textAlign: "center",
      }}
    >
      <h2 style={{ fontSize: "1.5rem", marginBottom: "1rem", color: "#b91c1c" }}>
        Something went wrong
      </h2>
      <p style={{ color: "#64748b", marginBottom: "1.5rem", maxWidth: 500 }}>
        {error.message || "An unexpected error occurred."}
      </p>
      <button
        onClick={reset}
        style={{
          padding: "0.6rem 1.5rem",
          background: "#00e676",
          color: "#000",
          border: "none",
          borderRadius: 8,
          fontWeight: 600,
          cursor: "pointer",
          fontSize: "0.95rem",
        }}
      >
        Try again
      </button>
    </div>
  );
}
