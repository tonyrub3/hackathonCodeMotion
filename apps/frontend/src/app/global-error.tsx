"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          backgroundColor: "#ffffff",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
        }}
      >
        <div style={{ textAlign: "center", padding: "2rem" }}>
          <h2 style={{ fontSize: "1.5rem", color: "#b91c1c" }}>
            Something went wrong
          </h2>
          <p style={{ color: "#64748b" }}>{error.message}</p>
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
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
