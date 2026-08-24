"use client";

import { useEffect, useState, useRef } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId, setCurrentWebsiteId } from "@/lib/website";

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/dashboard": "Dashboard",
  "/generate": "Generate Article",
  "/writer": "Autonomous Writer",
  "/content": "Content Studio",
  "/approvals": "Approval Queue",
  "/brain": "Brand Brain & Memory",
  "/knowledge": "Knowledge Base",
  "/wordpress": "WordPress Manager",
  "/backlinks": "Backlinks & Authority",
  "/tech-seo": "Technical SEO",
  "/monitoring": "24/7 Monitoring",
  "/workforce": "Autonomous Workforce",
  "/calendar": "Publishing Calendar",
  "/llms-txt": "LLMs.txt & GEO",
  "/connectors": "Connectors & Integrations",
  "/settings": "System Settings",
  "/websites": "Websites",
};

const sectionMap: Record<string, string> = {
  "/generate": "Core",
  "/writer": "Core",
  "/content": "Core",
  "/approvals": "Core",
  "/backlinks": "SEO Studio",
  "/tech-seo": "SEO Studio",
  "/monitoring": "SEO Studio",
  "/calendar": "SEO Studio",
  "/workforce": "AI Intelligence",
  "/brain": "AI Intelligence",
  "/knowledge": "AI Intelligence",
  "/llms-txt": "AI Intelligence",
  "/wordpress": "Integrations",
  "/connectors": "Integrations",
  "/settings": "System",
};

interface HealthData {
  health_score: number;
  checks: {
    nvidia_nim: string;
    supabase: string;
    serper: string;
    wordpress: string;
    slack: string;
    scheduler: string;
  };
  jobs_today: {
    due: number;
    completed: number;
    failed: number;
  };
  auto_fixes_applied: number;
  last_check: string;
  next_check: string;
  issues: string[];
  auto_fixed: string[];
}

export function Topbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [websites, setWebsites] = useState<any[]>([]);
  const [selectedWebsiteId, setSelectedWebsiteId] = useState<string>(getCurrentWebsiteId());

  // Dynamic Health Panel State
  const [health, setHealth] = useState<HealthData>({
    health_score: 100,
    checks: {
      nvidia_nim: "ok",
      supabase: "ok",
      serper: "ok",
      wordpress: "ok",
      slack: "ok",
      scheduler: "ok",
    },
    jobs_today: {
      due: 8,
      completed: 8,
      failed: 0,
    },
    auto_fixes_applied: 0,
    last_check: new Date().toISOString(),
    next_check: new Date().toISOString(),
    issues: [],
    auto_fixed: [],
  });
  const [showHealthPanel, setShowHealthPanel] = useState(false);
  const [runningHealthCheck, setRunningHealthCheck] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const pageTitle = pageTitles[pathname] || "Dashboard";
  const section = sectionMap[pathname];

  // Poll autonomous health every 60 seconds
  const fetchHealth = async () => {
    try {
      const data = await get("/api/health/autonomous");
      if (data && typeof data.health_score === "number") {
        setHealth(data);
      }
    } catch {
      // Keep existing state on error
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 60000);
    return () => clearInterval(interval);
  }, []);

  // Load connected websites
  useEffect(() => {
    async function loadWebsites() {
      try {
        let res = await get("/api/websites");
        if (!Array.isArray(res) || res.length === 0) {
          res = await get("/websites");
        }
        const sites = Array.isArray(res) ? res : res?.websites || [];
        setWebsites(sites);

        const current = getCurrentWebsiteId();
        const exists = sites.some((s: any) => s.id === current);
        if (!exists && sites[0]) {
          setSelectedWebsiteId(sites[0].id);
          setCurrentWebsiteId(sites[0].id);
        } else if (current) {
          setSelectedWebsiteId(current);
        }
      } catch {
        setWebsites([]);
      }
    }
    loadWebsites();
    const handleWChange = (e: any) => {
      if (e?.detail) setSelectedWebsiteId(e.detail);
      loadWebsites();
    };
    window.addEventListener("website-changed", handleWChange);
    return () => window.removeEventListener("website-changed", handleWChange);
  }, []);

  const handleWebsiteChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    if (value === "+ Add Website") {
      router.push("/websites");
      return;
    }
    setSelectedWebsiteId(value);
    setCurrentWebsiteId(value);
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("website-changed", { detail: value }));
    }
  };

  const handleRunFullCheck = async () => {
    setRunningHealthCheck(true);
    try {
      const res = await post("/api/health/autonomous/run", {});
      if (res.health) {
        setHealth(res.health);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setRunningHealthCheck(false);
    }
  };

  const score = health.health_score;
  const isGreen = score >= 80;
  const isYellow = score >= 50 && score < 80;

  return (
    <div className="topbar relative z-40">
      <div className="topbar-left flex items-center gap-2">
        <span>RankForge</span>
        {section && (
          <>
            <span className="breadcrumb-sq"></span>
            <span>{section}</span>
          </>
        )}
        <span className="breadcrumb-sq"></span>
        <span className="topbar-title">{pageTitle}</span>
      </div>

      <div className="topbar-right flex items-center gap-3">
        {/* DYNAMIC MASTER AUTONOMOUS HEALTH INDICATOR */}
        <div className="relative" ref={panelRef}>
          <button
            type="button"
            onClick={() => setShowHealthPanel(!showHealthPanel)}
            className={`live-pill cursor-pointer transition-all border ${
              isGreen
                ? "border-emerald-500/40 hover:border-emerald-500 bg-emerald-950/30"
                : isYellow
                ? "border-amber-500/50 hover:border-amber-500 bg-amber-950/30"
                : "border-red-500/50 hover:border-red-500 bg-red-950/30"
            }`}
            title="Click to view full autonomous system health diagnostics"
          >
            <span
              className={`live-dot ${
                isGreen ? "bg-emerald-400" : isYellow ? "bg-amber-400" : "bg-red-500"
              }`}
            />
            <span
              className={`font-mono text-[10px] font-bold uppercase tracking-wider ${
                isGreen ? "text-emerald-400" : isYellow ? "text-amber-400" : "text-red-400"
              }`}
            >
              {isGreen ? `LIVE (${score}%)` : isYellow ? `DEGRADED (${score}%)` : `ISSUES (${score}%)`}
            </span>
          </button>

          {/* FLOATING MASTER HEALTH DIAGNOSTIC PANEL */}
          {showHealthPanel && (
            <div className="absolute right-0 mt-2 w-84 sm:w-96 bg-[#111111] border border-[#333333] shadow-2xl rounded-xl p-5 z-50 text-white animate-fadeIn space-y-4">
              {/* Header */}
              <div className="flex items-center justify-between border-b border-[#222222] pb-3">
                <div className="flex items-center gap-2">
                  <span className="text-lg">📡</span>
                  <div>
                    <div className="font-bold text-sm text-white">Autonomous Health Monitor</div>
                    <div className="font-mono text-[10px] text-neutral-400">
                      Auto-checking every 15 mins
                    </div>
                  </div>
                </div>

                <div
                  className={`px-2.5 py-1 font-mono text-xs font-bold rounded ${
                    isGreen
                      ? "bg-emerald-950 text-emerald-400 border border-emerald-500/40"
                      : isYellow
                      ? "bg-amber-950 text-amber-400 border border-amber-500/40"
                      : "bg-red-950 text-red-400 border border-red-500/40"
                  }`}
                >
                  Score: {score}/100
                </div>
              </div>

              {/* Subsystems 6-Check Grid */}
              <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
                {Object.entries(health.checks).map(([service, status]) => (
                  <div
                    key={service}
                    className="p-2.5 bg-[#0a0a0a] border border-[#222222] rounded flex items-center justify-between"
                  >
                    <span className="text-neutral-400 capitalize">
                      {service.replace("_", " ")}:
                    </span>
                    <span
                      className={`font-bold ${
                        status === "ok"
                          ? "text-emerald-400"
                          : status === "degraded"
                          ? "text-amber-400"
                          : status === "not_configured"
                          ? "text-neutral-500"
                          : "text-red-400"
                      }`}
                    >
                      {status === "ok"
                        ? "OK ✓"
                        : status === "degraded"
                        ? "SLOW"
                        : status === "not_configured"
                        ? "OPT"
                        : "DOWN ✕"}
                    </span>
                  </div>
                ))}
              </div>

              {/* Today's Jobs & Auto-Fixes */}
              <div className="bg-[#0a0a0a] border border-[#222222] p-3 rounded space-y-1.5 font-mono text-xs">
                <div className="flex justify-between">
                  <span className="text-neutral-400">Jobs Completed Today:</span>
                  <span className="text-white font-bold">
                    {health.jobs_today?.completed ?? 0} / {health.jobs_today?.due ?? 8}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-400">Auto-Fixes Applied:</span>
                  <span className="text-emerald-400 font-bold">
                    {health.auto_fixes_applied ?? 0}
                  </span>
                </div>
              </div>

              {/* Auto-Fixed Log Items if any */}
              {health.auto_fixed && health.auto_fixed.length > 0 && (
                <div className="p-2.5 bg-emerald-950/30 border border-emerald-500/30 rounded font-mono text-[10px] text-emerald-300 space-y-1">
                  <div className="font-bold">Recent Auto-Heals:</div>
                  {health.auto_fixed.slice(0, 3).map((item, idx) => (
                    <div key={idx}>• {item}</div>
                  ))}
                </div>
              )}

              {/* Issues if any */}
              {health.issues && health.issues.length > 0 && (
                <div className="p-2.5 bg-red-950/30 border border-red-500/30 rounded font-mono text-[10px] text-red-300 space-y-1">
                  <div className="font-bold">Open Alerts:</div>
                  {health.issues.slice(0, 2).map((iss, idx) => (
                    <div key={idx}>• {iss}</div>
                  ))}
                </div>
              )}

              {/* Full Check Trigger Button */}
              <div className="pt-1 flex items-center justify-between border-t border-[#222222]">
                <button
                  type="button"
                  onClick={() => setShowHealthPanel(false)}
                  className="font-mono text-[11px] text-neutral-500 hover:text-neutral-300"
                >
                  Close
                </button>

                <button
                  type="button"
                  onClick={handleRunFullCheck}
                  disabled={runningHealthCheck}
                  className="px-3.5 py-1.5 bg-[#ff4500] hover:bg-[#cc3700] disabled:opacity-50 text-white font-mono text-xs font-bold rounded transition-colors flex items-center gap-1.5"
                >
                  {runningHealthCheck ? "Checking Subsystems..." : "Run Full Check Now →"}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Website Selector Dropdown */}
        <select className="site-select" value={selectedWebsiteId} onChange={handleWebsiteChange}>
          {websites.length === 0 ? (
            <option value="">+ Connect your website</option>
          ) : (
            websites.map((site: any) => (
              <option key={site.id} value={site.id}>
                {site.domain}
              </option>
            ))
          )}
          <option value="+ Add Website">+ Add Website</option>
        </select>
      </div>
    </div>
  );
}
