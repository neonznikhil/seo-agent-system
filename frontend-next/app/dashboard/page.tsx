"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, put } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface RoiData {
  website_id: string;
  start_date?: string;
  end_date?: string;
  total_clicks?: number;
  total_impressions?: number;
  estimated_traffic_value?: number;
  articles_published?: number;
  organic_growth_rate?: number;
  keywords?: Array<{
    keyword: string;
    clicks: number;
    impressions: number;
    position: number;
    ctr: number;
  }>;
}

interface AutonomyData {
  knowledge_base_docs: number;
  brain_memories: number;
  published_this_week: number;
  refreshed_recently: number;
  jobs: Record<string, { status: string; run_at: string; result?: any; error?: string }>;
  automation: Record<string, string>;
}

interface AutonomyLog {
  id: string;
  job_type: string;
  status: string;
  result?: any;
  error?: string;
  run_at: string;
}

interface ApprovalStats {
  pending: number;
  published_today: number;
  autonomous_jobs_last_run: string | null;
}

const JOB_LABELS: Record<string, string> = {
  daily_search: "Daily Search (9AM IST)",
  daily_knowledge_sync: "Knowledge Sync (9:30AM IST)",
  daily_content_refresh: "Refresh Analysis (10AM IST)",
  auto_page_pipeline: "New Page Drafts (11AM IST)",
};

function timeAgo(iso?: string): string {
  if (!iso) return "never";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hr ago`;
  return `${Math.floor(hrs / 24)} days ago`;
}

export default function DashboardPage() {
  const [roiData, setRoiData] = useState<RoiData | null>(null);
  const [stats, setStats] = useState<any>(null);
  const [autonomy, setAutonomy] = useState<AutonomyData | null>(null);
  const [logs, setLogs] = useState<AutonomyLog[]>([]);
  const [approvalStats, setApprovalStats] = useState<ApprovalStats | null>(null);
  const [togglingAutomation, setTogglingAutomation] = useState(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [websiteId, setWebsiteId] = useState<string>("");

  const loadDashboard = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);
    if (!wid) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const [roiRes, statsRes, autoRes, logsRes, apprRes] = await Promise.allSettled([
        get(`/api/roi/${wid}`),
        get(`/api/stats?website_id=${wid}`),
        get(`/api/autonomy?website_id=${wid}`),
        get(`/api/autonomy/logs?website_id=${wid}&limit=12`),
        get(`/api/approvals/stats?website_id=${wid}`),
      ]);

      if (roiRes.status === "fulfilled" && roiRes.value) {
        setRoiData(roiRes.value);
      } else {
        setRoiData(null);
      }

      if (statsRes.status === "fulfilled" && statsRes.value) {
        setStats(statsRes.value);
      }
      if (autoRes.status === "fulfilled" && autoRes.value) {
        setAutonomy(autoRes.value);
      }
      if (logsRes.status === "fulfilled" && Array.isArray(logsRes.value)) {
        setLogs(logsRes.value);
      }
      if (apprRes.status === "fulfilled" && apprRes.value) {
        setApprovalStats(apprRes.value);
      }
    } catch (e: any) {
      setError(e.message || "Failed to load ROI and dashboard performance");
    } finally {
      setLoading(false);
    }
  }, []);

  const toggleAutomate = useCallback(async () => {
    if (!autonomy) return;
    const current = autonomy.automation?.automate_seo === "on";
    setTogglingAutomation(true);
    try {
      await put("/api/automation", { automate_seo: current ? "off" : "on" });
      await loadDashboard();
    } catch {
      // silent - toggle state reloads on next refresh
    } finally {
      setTogglingAutomation(false);
    }
  }, [autonomy, loadDashboard]);

  useEffect(() => {
    loadDashboard();
    const handleChanged = () => loadDashboard();
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [loadDashboard]);

  if (loading) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px auto" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Loading ROI and search performance...
        </p>
      </div>
    );
  }

  if (!websiteId) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">SEO ROI & Growth</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No data yet — add a website first.</strong> Select or configure your website in the Websites section to start computing ROI metrics.
            <div style={{ marginTop: "10px" }}>
              <Link href="/websites" className="btn btn-accent" style={{ textDecoration: "none", fontSize: "11px", padding: "4px 10px" }}>
                + Add Website
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      <div className="page-heading">SEO ROI & Performance</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Organic Search Yield · Business Value · Live Keyword Impact
        {error && (
          <span className="badge badge-amber" style={{ marginLeft: "12px" }}>
            {error}
          </span>
        )}
      </div>

      {/* AUTONOMY CONTROL CENTER */}
      <div className="panel" style={{ marginTop: "20px", borderColor: "var(--accent)" }}>
        <div className="panel-head">
          <span className="panel-label">Autonomous SEO Control</span>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            {/* Notification bell: pending approvals */}
            <Link
              href="/approvals"
              title="Pending approvals"
              style={{
                position: "relative",
                textDecoration: "none",
                fontSize: "16px",
                lineHeight: 1,
                padding: "4px 8px",
                border: (approvalStats?.pending ?? 0) > 0 ? "1px solid var(--accent)" : "1px solid var(--line)",
                borderRadius: 3,
                background: (approvalStats?.pending ?? 0) > 0 ? "rgba(255,77,18,0.10)" : "transparent",
              }}
            >
              🔔
              {(approvalStats?.pending ?? 0) > 0 && (
                <span
                  style={{
                    position: "absolute",
                    top: -7,
                    right: -7,
                    background: "var(--accent)",
                    color: "#fff",
                    borderRadius: 8,
                    fontSize: 10,
                    fontWeight: 700,
                    padding: "1px 5px",
                    minWidth: 16,
                    textAlign: "center",
                  }}
                >
                  {approvalStats!.pending}
                </span>
              )}
            </Link>
            <span className="mono-font" style={{ fontSize: "11px", color: "var(--muted)" }}>
              {autonomy?.automation?.automate_seo === "on" ? "AUTOMATION ON" : "AUTOMATION OFF"}
            </span>
            <button
              onClick={toggleAutomate}
              disabled={togglingAutomation || !websiteId}
              style={{
                cursor: "pointer",
                padding: "6px 16px",
                fontSize: "12px",
                fontWeight: 700,
                border: "1px solid var(--accent)",
                background: autonomy?.automation?.automate_seo === "on" ? "var(--accent)" : "transparent",
                color: autonomy?.automation?.automate_seo === "on" ? "#fff" : "var(--accent)",
                borderRadius: "3px",
              }}
            >
              {togglingAutomation
                ? "..."
                : `Automate SEO: ${(autonomy?.automation?.automate_seo || "on").toUpperCase()}`}
            </button>
          </div>
        </div>
        <div className="panel-body" style={{ padding: "10px 14px 0 14px", fontSize: "11px", color: "var(--muted)" }}>
          Auto-generate: <b style={{ color: "var(--green)" }}>ON</b> (creates drafts for approval) &nbsp;·&nbsp;
          Auto-publish: <b style={{ color: "var(--red)" }}>OFF</b> (WordPress posts always require human approval) &nbsp;·&nbsp;
          <Link href="/approvals" style={{ color: "var(--accent)" }}>
            {approvalStats?.pending ?? 0} post(s) waiting for approval
          </Link>
        </div>
        <div className="panel-body" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "14px", padding: "14px" }}>
          <div>
            <div className="kpi-label">Knowledge Base Docs</div>
            <div className="kpi-val">{autonomy?.knowledge_base_docs ?? "-"}</div>
            <div className="kpi-delta">Business facts + competitor intel</div>
          </div>
          <div>
            <div className="kpi-label">Brain Memories</div>
            <div className="kpi-val">{autonomy?.brain_memories ?? "-"}</div>
            <div className="kpi-delta">What worked / what failed</div>
          </div>
          <div>
            <div className="kpi-label">Published This Week</div>
            <div className="kpi-val" style={{ color: "var(--green)" }}>{autonomy?.published_this_week ?? "-"}</div>
            <div className="kpi-delta">Auto-created pages (gate-passed)</div>
          </div>
          <div>
            <div className="kpi-label">Refreshed Recently</div>
            <div className="kpi-val" style={{ color: "var(--green)" }}>{autonomy?.refreshed_recently ?? "-"}</div>
            <div className="kpi-delta">Old blogs updated on WP</div>
          </div>
        </div>
        <div className="panel-body" style={{ borderTop: "1px solid var(--line)", padding: "14px" }}>
          {["daily_search", "daily_knowledge_sync", "daily_content_refresh", "auto_page_pipeline"].map((jt) => {
            const job = autonomy?.jobs?.[jt];
            const ok = job?.status === "completed";
            return (
              <div key={jt} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "5px 0", fontSize: "12px" }}>
                <span>{JOB_LABELS[jt] || jt}</span>
                <span className={`badge ${ok ? "badge-accent" : "badge-amber"}`}>
                  {job ? `${job.status} · ${timeAgo(job.run_at)}` : "not run yet"}
                </span>
              </div>
            );
          })}
          <Link href="/monitoring" style={{ fontSize: "11px", color: "var(--accent)" }}>
            Full monitoring →
          </Link>
        </div>
      </div>

      {/* KPI METRICS */}
      <div className="kpi-strip">
        <div className="kpi-cell">
          <div className="kpi-label">Organic Clicks</div>
          <div className="kpi-val">{roiData?.total_clicks ?? 0}</div>
          <div className="kpi-delta">Search console verified</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Total Impressions</div>
          <div className="kpi-val">{roiData?.total_impressions ?? 0}</div>
          <div className="kpi-delta">Search visibility</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Articles Published</div>
          <div className="kpi-val" style={{ color: "var(--green)" }}>{stats?.total_articles ?? 0}</div>
          <div className="kpi-delta">Active SEO assets</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">SEO Health</div>
          <div className="kpi-val">{stats?.health_score !== null && stats?.health_score !== undefined ? `${stats.health_score}%` : "Pending"}</div>
          <div className="kpi-delta">System audit status</div>
        </div>
      </div>

      {/* KEYWORDS IMPACT TABLE */}
      <div className="panel" style={{ marginTop: "20px" }}>
        <div className="panel-head">
          <span className="panel-label">High-Impact Ranked Keywords</span>
          <button className="panel-action" onClick={loadDashboard}>
            Refresh
          </button>
        </div>
        <div className="panel-body" style={{ padding: "0" }}>
          {roiData?.keywords && roiData.keywords.length > 0 ? (
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "12px" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--line)", color: "var(--muted)", textTransform: "uppercase", fontSize: "10px" }}>
                  <th style={{ padding: "10px 14px" }}>Keyword</th>
                  <th style={{ padding: "10px 14px" }}>Position</th>
                  <th style={{ padding: "10px 14px" }}>Clicks</th>
                  <th style={{ padding: "10px 14px" }}>Impressions</th>
                  <th style={{ padding: "10px 14px" }}>CTR</th>
                </tr>
              </thead>
              <tbody>
                {roiData.keywords.map((kw, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid var(--line)" }}>
                    <td style={{ padding: "10px 14px", fontWeight: 600 }}>{kw.keyword}</td>
                    <td style={{ padding: "10px 14px" }}>
                      <span className="badge badge-accent">#{kw.position?.toFixed(1) || "-"}</span>
                    </td>
                    <td style={{ padding: "10px 14px" }}>{kw.clicks}</td>
                    <td style={{ padding: "10px 14px" }}>{kw.impressions}</td>
                    <td style={{ padding: "10px 14px" }}>{(kw.ctr * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ padding: "24px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              No keyword ranking data available yet. Connect Google Search Console or run keyword discovery in Research.
              <div style={{ marginTop: "12px" }}>
                <Link href="/research" className="btn btn-accent" style={{ textDecoration: "none", fontSize: "11px", display: "inline-block" }}>
                  Explore Keywords
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* LIVE AUTONOMY LOGS */}
      <div className="panel" style={{ marginTop: "20px" }}>
        <div className="panel-head">
          <span className="panel-label">Live Autonomous Job Logs</span>
          <button className="panel-action" onClick={loadDashboard}>
            Refresh
          </button>
        </div>
        <div className="panel-body" style={{ padding: "0" }}>
          {logs.length > 0 ? (
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "12px" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--line)", color: "var(--muted)", textTransform: "uppercase", fontSize: "10px" }}>
                  <th style={{ padding: "10px 14px" }}>Time</th>
                  <th style={{ padding: "10px 14px" }}>Job</th>
                  <th style={{ padding: "10px 14px" }}>Status</th>
                  <th style={{ padding: "10px 14px" }}>Details</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} style={{ borderBottom: "1px solid var(--line)" }}>
                    <td style={{ padding: "8px 14px", whiteSpace: "nowrap", color: "var(--muted)" }}>{timeAgo(log.run_at)}</td>
                    <td style={{ padding: "8px 14px", fontWeight: 600 }}>{JOB_LABELS[log.job_type] || log.job_type}</td>
                    <td style={{ padding: "8px 14px" }}>
                      <span className={`badge ${log.status === "completed" ? "badge-accent" : "badge-amber"}`}>{log.status}</span>
                    </td>
                    <td style={{ padding: "8px 14px", color: "var(--muted)", maxWidth: "380px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {log.error ? String(log.error) : JSON.stringify(log.result ?? {}).slice(0, 120)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ padding: "24px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              No autonomous jobs have run yet. Jobs fire daily at 9AM / 10AM / 10:30AM IST, or immediately on boot if overdue.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
