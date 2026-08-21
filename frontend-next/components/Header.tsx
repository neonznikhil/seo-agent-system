"use client";

import { usePathname } from "next/navigation";

const pageNames: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/proposals": "Proposals",
  "/websites": "Websites",
  "/memory": "Memory",
  "/llms-txt": "LLMs.txt",
  "/tech-seo": "Tech SEO",
  "/backlinks": "Backlinks",
};

export function Header() {
  const pathname = usePathname();
  const pageTitle = pageNames[pathname] || "Dashboard";

  return (
    <header className="h-[46px] bg-paper border-b border-ink flex items-center justify-between px-5 sticky top-0 z-50">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider mono-font text-muted">
        <span>RankForge</span>
        <span className="w-[4px] h-[4px] bg-muted flex-shrink-0" />
        <span className="text-ink font-semibold">{pageTitle}</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1 text-[10px] uppercase tracking-wider mono-font text-muted">
          <span className="w-[6px] h-[6px] bg-accent flex-shrink-0" style={{ animation: 'pulse-sq 1.4s ease-in-out infinite' }} />
          <span>Live</span>
        </div>
        <button className="px-3 py-1 text-[10px] uppercase tracking-wider mono-font bg-stone border border-ink text-ink cursor-pointer">
          Select Website ▾
        </button>
      </div>
    </header>
  );
}