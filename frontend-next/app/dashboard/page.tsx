"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { get, createSSE } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";
import Link from "next/link";

interface HealthStatus {
  status: string;
  checks: Record<string, string>;
  degraded_reasons?: string[];
}

interface ROIMetrics {
  impressions_last_30d: number;
  blogs_published_last_30d: number;
  technical_health_score: number;
  backlinks_total: number;
  backlinks_new_7d: number;
  impressions_change_pct: number;
}

interface AEOScore {
  score: number;
  improvements?: string[];
  featured_snippet_opportunities?: string[];
}

interface GSCKeyword {
  query: string;
  clicks: number;
  impressions: number;
  position: number;
  ctr: number;
}

interface GSCData {
  website_id: string;
  keywords: GSCKeyword[];
  total_clicks: number;
  total_impressions: number;
}

interface Alert {
  id: string;
  website_id: string;
  severity: string;
  alert_type: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

interface TechSEO {
  health_score: number;
  issues: string[];
  audit?: any;
}

interface ContentItem {
  id: string;
  website_id: string;
  title: string;
  status: string;
  content_type: string;
  created_at: string;
}

function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "K";
  return String(n);
}

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [roiData, setRoiData] = useState<ROIMetrics | null>(null);
  const [aeoScore, setAeoScore] = useState<AEOScore | null>(null);
  const [gscData, setGscData] = useState<GSCData | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [techSEO, setTechSEO] = useState<TechSEO | null>(null);
  const [contentItems, setContentItems] = useState<ContentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [liveMessages, setLiveMessages] = useState<string[]>([]);
  const [theme, setTheme] = useState("light");

  const websiteId = getCurrentWebsiteId();
  const sseRef = useRef<EventSource | null>(null);

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
  };

  useEffect(() => {
    const saved = localStorage.getItem("theme");
    if (saved) {
      setTheme(saved);
      document.documentElement.setAttribute("data-theme", saved);
    } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      setTheme("dark");
      document.documentElement.setAttribute("data-theme", "dark");
    }
  }, []);

  const fetchData = useCallback(async () => {
    setError(null);
    try {
      const results = await Promise.allSettled([
        get("/health"),
        get(`/roi/${websiteId}`),
        get(`/aeo-score/${websiteId}`),
        get(`/gsc/keywords/${websiteId}`),
        get(`/monitoring/${websiteId}/alerts?filter=unread`),
        get(`/tech-seo/${websiteId}`),
        get(`/content?website_id=${websiteId}&limit=5`),
      ]);

      const healthRes = results[0].status === "fulfilled" ? results[0].value : null;
      const roiRes = results[1].status === "fulfilled" ? results[1].value : null;
      const aeoRes = results[2].status === "fulfilled" ? results[2].value : null;
      const gscRes = results[3].status === "fulfilled" ? results[3].value : null;
      const alertsRes = results[4].status === "fulfilled" ? results[4].value : null;
      const techRes = results[5].status === "fulfilled" ? results[5].value : null;
      const contentRes = results[6].status === "fulfilled" ? results[6].value : null;

      setHealth(healthRes);
      setRoiData(roiRes || null);
      setAeoScore(aeoRes || null);
      setGscData(gscRes || null);
      setAlerts(Array.isArray(alertsRes) ? alertsRes : []);
      setTechSEO(techRes || null);
      setContentItems(Array.isArray(contentRes) ? contentRes : []);
      setLastUpdated(new Date());

      const failures = results.filter(r => r.status === "rejected");
      if (failures.length > 0 && !healthRes) {
        setError("Backend offline - start uvicorn backend.main:app --reload");
      }
    } catch (e: any) {
      setError(e.message || "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  useEffect(() => {
    if (loading) return;
    sseRef.current = createSSE(`/monitoring/${websiteId}/live`, (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        setLiveMessages(prev => {
          const msg = typeof data === "string" ? data : (data.message || JSON.stringify(data));
          const next = [msg, ...prev].slice(0, 20);
          return next;
        });
      } catch {
        setLiveMessages(prev => [event.data, ...prev].slice(0, 20));
      }
    });
    return () => {
      if (sseRef.current) sseRef.current.close();
    };
  }, [websiteId, loading]);

  const backendOffline = !health && error;
  const gscConnected = health?.checks?.gsc === "ok";

  const topKeywords = (gscData?.keywords || []).sort((a, b) => b.clicks - a.clicks).slice(0, 5);
  const techIssues = alerts.filter(a => a.alert_type?.startsWith("tech_") || a.alert_type?.includes("tech") || a.alert_type?.includes("broken") || a.alert_type?.includes("schema") || a.alert_type?.includes("slow"));
  const recentActivity = alerts.slice(0, 5);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-[11px] text-muted">
            <span className="w-2 h-2 bg-accent rounded-full" />
            <span>Dashboard</span>
          </div>
        </div>
        <div className="kpi-strip">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="kpi-cell">
              <div className="kpi-label">Loading...</div>
              <div className="h-6 w-16 bg-line animate-pulse mt-2" />
            </div>
          ))}
        </div>
        <div className="dash-grid">
          <div className="space-y-4">
            <div className="panel"><div className="panel-head"><span className="panel-label">Loading...</span></div><div className="p-4 space-y-2">{[...Array(3)].map((_, i) => <div key={i} className="h-8 bg-line animate-pulse" />)}</div></div>
          </div>
          <div className="space-y-4">
            <div className="panel"><div className="panel-head"><span className="panel-label">Loading...</span></div><div className="p-4 space-y-2">{[...Array(3)].map((_, i) => <div key={i} className="h-8 bg-line animate-pulse" />)}</div></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {backendOffline && (
        <div className="bg-stone border border-red-500 p-4">
          <div className="text-[11px] mono-font text-red-500">
            Backend offline at http://localhost:8000 - Run: uvicorn backend.main:app --reload
          </div>
        </div>
      )}

      {health?.status === "degraded" && health.degraded_reasons && (
        <div className="bg-stone border border-amber-500 p-4">
          <div className="text-[11px] mono-font text-amber-500">
            Degraded: {health.degraded_reasons.join(", ")}
          </div>
        </div>
      )}

      {/* HEADER */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[11px] text-muted">
          <span className="w-2 h-2 bg-accent rounded-full" />
          <span>Dashboard</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[9px] text-muted mono-font">Updated {timeAgo(lastUpdated)}</span>
          <button onClick={toggleTheme} className="text-[9px] mono-font uppercase tracking-widest border border-ink px-2 py-1 hover:bg-paper">
            {theme === "light" ? "Dark" : "Light"}
          </button>
        </div>
      </div>

      {/* KPI STRIP */}
      <div className="kpi-strip">
        <div className="kpi-cell">
          <div className="kpi-label">Organic Traffic</div>
          <div className="kpi-val">{formatNumber(roiData?.impressions_last_30d ?? 0)}</div>
          <div className={`kpi-delta ${(roiData?.impressions_change_pct ?? 0) < 0 ? 'neg' : ''}`}>
            {(roiData?.impressions_change_pct ?? 0) >= 0 ? '↑' : '↓'} {Math.abs(roiData?.impressions_change_pct ?? 0).toFixed(1)}%
          </div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Ranked Keywords</div>
          <div className="kpi-val">{gscData?.keywords?.length ?? 0}</div>
          <div className="kpi-delta">GSC live</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Avg Position</div>
          <div className="kpi-val">
            {gscData?.keywords?.length ? Math.round(gscData.keywords.reduce((s, k) => s + k.position, 0) / gscData.keywords.length) : "—"}
          </div>
          <div className="kpi-delta">Live</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Backlinks</div>
          <div className="kpi-val">{formatNumber(roiData?.backlinks_total ?? 0)}</div>
          <div className="kpi-delta">↑ {roiData?.backlinks_new_7d ?? 0} new (7d)</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Domain Authority</div>
          <div className="kpi-val">{techSEO?.health_score ?? "—"}</div>
          <div className="kpi-delta">Tech health</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">CTR</div>
          <div className="kpi-val">
            {gscData?.keywords?.length ? (gscData.keywords.reduce((s, k) => s + k.ctr, 0) / gscData.keywords.length * 100).toFixed(1) + "%" : "—"}
          </div>
          <div className="kpi-delta">Avg</div>
        </div>
      </div>

      {/* DASH GRID */}
      <div className="dash-grid">
        <div className="space-y-4">
          {/* ACTIVE AI AGENTS / LIVE ACTIVITY */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Live Agent Activity</span>
              <span className="badge badge-green">LIVE</span>
            </div>
            <div style={{ padding: "10px 14px" }}>
              {liveMessages.length === 0 ? (
                <div className="text-[11px] text-muted mono-font py-2">Monitoring offline - Start backend</div>
              ) : (
                liveMessages.slice(0, 6).map((msg, i) => (
                  <div key={i} className="activity-row">
                    <div className="act-left"><span className="act-sq"></span>{msg}</div>
                    <span className="act-time">{i === 0 ? "now" : `${i * 2}m ago`}</span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* RECENT ACTIVITY */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Recent Activity</span>
              <span className="act-time">Last 24h</span>
            </div>
            <div className="panel-body">
              {recentActivity.length === 0 ? (
                <div className="text-[11px] text-muted mono-font py-2">No recent alerts</div>
              ) : (
                recentActivity.map((act) => (
                  <div key={act.id} className="activity-row">
                    <div className="act-left">
                      <span className={`act-sq ${act.severity === 'critical' ? 'bg-red-500' : act.severity === 'high' ? 'bg-amber-500' : ''}`}></span>
                      {act.message}
                    </div>
                    <span className="act-time">{new Date(act.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          {/* TOP KEYWORDS */}
          <div className="panel">
            <div className="panel-head"><span className="panel-label">Top Keywords</span></div>
            <div style={{ padding: "6px 14px" }}>
              {topKeywords.length === 0 ? (
                <div className="text-[11px] text-muted mono-font py-4">No GSC data - Connect GSC</div>
              ) : (
                topKeywords.map((kw, i) => (
                  <div key={i} className="rank-row">
                    <span className="rank-num">{i + 1}</span>
                    <span className="rank-kw">{kw.query}</span>
                    <span className="rank-pos">{Math.round(kw.position)}</span>
                    <span className={`rank-ch ${kw.position > kw.clicks ? 'neg' : ''}`}>↑{kw.clicks}</span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* TRAFFIC 30 DAYS */}
          <div className="panel">
            <div className="panel-head"><span className="panel-label">Traffic — 30 Days</span></div>
            <div className="panel-body">
              {gscData?.keywords?.length ? (
                <>
                  <MiniChart keywords={gscData.keywords} />
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: "6px" }}>
                    <span style={{ fontSize: "9px", color: "var(--muted)" }}>30d ago</span>
                    <span style={{ fontSize: "9px", color: "var(--muted)" }}>Today</span>
                  </div>
                </>
              ) : (
                <div className="text-[11px] text-muted mono-font py-8">Connect GSC to see trend</div>
              )}
            </div>
          </div>

          {/* SEO HEALTH */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">SEO Health</span>
              <span style={{ fontFamily: "'DotGothic16',sans-serif", fontSize: "18px", color: "var(--accent)" }}>
                {techSEO?.health_score ?? "—"}/100
              </span>
            </div>
            <div className="panel-body">
              {techSEO?.issues?.length ? (
                techSEO.issues.slice(0, 4).map((issue, i) => (
                  <div key={i} className="prog-row">
                    <div className="prog-label"><span>{issue}</span></div>
                  </div>
                ))
              ) : (
                <div className="text-[11px] text-muted mono-font py-2">Run tech audit to see health breakdown</div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* BOTTOM TICKER */}
      <div className="bticker">
        <span className="bticker-inner">
          <span className="bt-sq"></span>RANKFORGE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>AI/LLM OPTIMISED <span className="bt-sep">/</span>
          <span className="bt-sq"></span>AEO ACTIVE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>GEO READY <span className="bt-sep">/</span>
          <span className="bt-sq"></span>HUMAN APPROVAL REQUIRED &nbsp;&nbsp;&nbsp;&nbsp;
          <span className="bt-sq"></span>RANKFORGE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>AI/LLM OPTIMISED <span className="bt-sep">/</span>
          <span className="bt-sq"></span>AEO ACTIVE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>GEO READY <span className="bt-sep">/</span>
          <span className="bt-sq"></span>HUMAN APPROVAL REQUIRED
        </span>
      </div>
    </div>
  );
}

function MiniChart({ keywords }: { keywords: GSCKeyword[] }) {
  const vals = keywords.map(k => Math.max(1, k.clicks));
  const max = Math.max(...vals, 1);
  return (
    <div className="mini-chart">
      {vals.slice(0, 30).map((v, i) => (
        <div key={i} className="bar" style={{ height: (v / max * 44) + "px" }} title={`${keywords[i]?.query}: ${v} clicks`} />
      ))}
    </div>
  );
}

function timeAgo(date: Date): string {
  const diff = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}
