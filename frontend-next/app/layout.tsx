import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import GlobalCommandBar from "@/components/GlobalCommandBar";

export const metadata: Metadata = {
  title: "RANKFORGE - Autonomous SEO Agent System",
  description: "10-Phase Autonomous SEO Content Engine & Rank Intelligence",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=DotGothic16&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <div className="app-shell">
          <Sidebar />
          <div className="main">
            <Topbar />
            <div className="page-wrap">{children}</div>
          </div>
        </div>
        <GlobalCommandBar />
      </body>
    </html>
  );
}
