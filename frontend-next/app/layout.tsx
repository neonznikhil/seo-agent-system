import type { Metadata } from "next";
import "./globals.css";
import { IBM_Plex_Mono } from "next/font/google";
import { Sidebar } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";

const plex = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  title: "RANKFORGE",
  description: "Autonomous SEO Agent System",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={plex.className}>
        <div className="app-shell">
          <Sidebar />
          <div className="main">
            <Topbar />
            <div className="page-wrap">{children}</div>
          </div>
        </div>
      </body>
    </html>
  );
}
