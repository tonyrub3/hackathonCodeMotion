import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Project: Aletheia",
  description: "Explainable, source-traced fact-checking system",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          backgroundColor: "#ffffff",
          color: "#000000",
          minHeight: "100vh",
        }}
      >
        {children}
      </body>
    </html>
  );
}
