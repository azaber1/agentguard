import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentGuard",
  description: "Test AI agents for reliability, security and policy compliance.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
