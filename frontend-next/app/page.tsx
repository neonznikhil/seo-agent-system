"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post, del } from "@/lib/api";
import { getCurrentWebsiteId, setCurrentWebsiteId } from "@/lib/website";

interface DashboardMetrics {
  website_id: string;
  total_articles: number;
  published_articles: number;
  pending_articles: number;
  seo_health_score: number | null;
  last_audit_date: string | null;
  monitored_alerts: number;
  memories_count: number;
  knowledge_count: number;
  backlinks_count: number;
  backlink_opportunities: number;
  recent_content: Array<{
    id: string;
    title: string;
    keyword?: string;
    status: string;
    pipeline_status?: string;
    approval_id?: string | null;
    wordpress_url?: string | null;
    approval_status?: string | null;
    created_at?: string;
    content?: string;
    html_content?: string;
  }>;
  agents: Array<{
    name: string;
    state: "ACTIVE" | "IDLE" | "ERROR";
    last_run: string | null;
    summary: string | null;
    error: string | null;
  }>;
  publishing_schedule: Array<{
    id: string;
    title: string;
    date: string;
    status: string;
    keyword?: string | null;
  }>;
}

interface Website {
  id: string;
  domain?: string;
}

const AGENT_ROLES: Record<string, string> = {
  WriterPipeline: "10-Phase Unranked-Beater Generator",
  BrainAutopilot: "Winning Heuristics & Pattern Learner",
  ContinuousMonitor: "24/7 SERP Shifts & Uptime Telemetry",
  BacklinkScout: "5-Tier Technical Link Engineer",
  TechSEOAgent: "Core Web Vitals & Schema Injector",
  AuthorityCalibration: "90-Day Strategy Calibration",
};

export default function HomePage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [domain, setDomain] = useState<string>("");
  const [websiteId, setWebsiteId] = useState<string>("");
  const [websites, setWebsites] = useState<Website[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [selectedArticle, setSelectedArticle] = useState<any | null>(null);
  const [approvingId, setApprovingId] = useState<string | null>(null);

  // Quick generator state
  const [genTopic, setGenTopic] = useState("");
  const [genKeyword, setGenKeyword] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  useEffect(() => {
    const id = getCurrentWebsiteId();
    if (id) setWebsiteId(id);
    const handleChanged = (e: any) => {
      if (e?.detail) setWebsiteId(e.detail);
    };
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, []);

  const fetchDashboardData = useCallback(async () => {
    try {
      setError(null);

      let sites: Website[] = [];
      try {
        const res = await get("/api/websites");
        sites = Array.isArray(res) ? res : res?.websites || [];
      } catch {}
      setWebsites(sites);

      let activeId = websiteId || getCurrentWebsiteId();
      if (!activeId && sites.length > 0) activeId = sites[0].id;
      if (!activeId) {
        setMetrics(null);
        setLoading(false);
        return;
      }
      setWebsiteId(activeId);
      setCurrentWebsiteId(activeId);

      const activeSite = sites.find((s) => s.id === activeId);
      setDomain(activeSite?.domain || "");

      const data = await get(`/api/dashboard/${activeId}/metrics`);
      setMetrics(data);
    } catch (e: any) {
      setError(e.message || "Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 30000);
    return () => clearInterval(interval);
  }, [fetchDashboardData]);

  // Manual override generation
  const handleRunPipeline = async (e: React.FormEvent) => {
    e.preventDefault();
    setGenError(null);
    const trimmed = genTopic.trim();
    if (
      !trimmed ||
      trimmed.toLowerCase().includes("e.g.") ||
      trimmed.length < 8
    ) {
      setGenError("Enter a real article topic (at least 8 characters).");
      return;
    }
    const activeId = getCurrentWebsiteId() || websiteId;
    if (!activeId) {
      showToast("Connect a website first");
      return;
    }

    try {
      setIsGenerating(true);
      await post(`/api/writer/${activeId}/generate`, {
        topic: trimmed,
        title: trimmed,
        primary_keyword: genKeyword.trim() || trimmed,
      });
      showToast(`Generation started for "${trimmed}" — watch it stream on the Writer page.`);
      setGenTopic("");
      setGenKeyword("");
      setTimeout(fetchDashboardData, 4000);
    } catch (err: any) {
      setGenError(err.message || "Generation failed to start");
    } finally {
      setIsGenerating(false);
    }
  };

  // Approve uses the SAME endpoint as the approvals page (blog_approvals id)
  const handleApproveDraft = async (item: any) => {
    if (!item.approval_id) {
      showToast("No approval record exists yet for this draft.");
      return;
    }
    try {
      setApprovingId(item.approval_id);
      const res = await post(`/api/approvals/${item.approval_id}/approve`, {});
      showToast(`✓ Published to WordPress${res.wordpress_url ? `: ${res.wordpress_url}` : ""}`);
      setSelectedArticle(null);
      fetchDashboardData();
    } catch (err: any) {
      showToast(`Approval failed: ${err.message}`);
    } finally {
      setApprovingId(null);
    }
  };

  const openDraftPreview = async (item: any) => {
    setSelectedArticle(item);
    if (!item.content && !item.html_content) {
      try {
        const detail = await get(`/api/writer/${websiteId}/content/${item.id}`);
        setSelectedArticle((prev: any) => ({ ...(prev || {}), ...detail }));
      } catch {}
    }
  };

  const handleDeleteDraft = async (item: any) => {
    if (!confirm(`Delete draft: "${item.title}"?`)) return;
    try {
      await del(`/api/blogs/${item.id}`);
      showToast("Draft deleted.");
      fetchDashboardData();
    } catch (err: any) {
      showToast(`Delete failed: ${err.message}`);
    }
  };

  const stateBadge = (state: string) =>
    state === "ACTIVE" ? "badge-green" : state === "ERROR" ? "badge-red" : "badge-amber";

  return (
    <div className="page-container active">
      {toastMsg && (
        <div
          style={{
            position: "fixed",
            bottom: "24px",
            left: "50%",
            transform: "translateX(-50%)",
            background: "var(--ink)",
            color: "var(--bg)",
            padding: "10px 22px",
            fontSize: "10.5px",
            textTransform: "uppercase",
            letterSpacing: ".07em",
            zIndex: 9999,
            fontFamily: "'IBM Plex Mono', monospace",
            border: "1px solid var(--accent)",
            boxShadow: "0 4px 24px rgba(0,0,0,.4)",
          }}
        >
          {toastMsg}
        </div>
      )}

      {/* PAGE HEADING */}
      <div className="page-heading">Dashboard</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Autonomous SEO · Real-time intelligence ·{" "}
        <span style={{ fontWeight: 600, color: "var(--ink)" }}>{domain || "Connect a website"}</span>
        {error && (
          <span className="badge badge-amber" style={{ marginLeft: "12px" }}>
            {error}
          </span>
        )}
      </div>

      {/* KPI STRIP */}
      <div className="kpi-strip">
        <Link href="/content" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Articles Generated</div>
          <div className="kpi-val">{metrics?.total_articles ?? 0}</div>
          <div className="kpi-delta">View all in Content →</div>
        </Link>
        <Link href="/approvals" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Pending Approval</div>
          <div className="kpi-val" style={{ color: "var(--accent)" }}>
            {metrics?.pending_articles ?? 0}
          </div>
          <div className="kpi-delta" style={{ color: "var(--accent)" }}>Open approvals queue →</div>
        </Link>
        <Link href="/tech-seo" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">SEO Health Score</div>
          <div className="kpi-val">
            {metrics?.seo_health_score != null ? `${metrics.seo_health_score}/100` : "No audit yet"}
          </div>
          <div className="kpi-delta">Latest technical audit →</div>
        </Link>
        <Link href="/monitoring" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Monitored Alerts</div>
          <div className="kpi-val">{metrics?.monitored_alerts ?? 0}</div>
          <div className="kpi-delta">Open monitoring →</div>
        </Link>
        <Link href="/brain" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Brain Memories</div>
          <div className="kpi-val">{metrics?.memories_count ?? 0}</div>
          <div className="kpi-delta">Learned patterns →</div>
        </Link>
        <Link href="/backlinks" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Backlinks / Prospects</div>
          <div className="kpi-val">
            {metrics?.backlinks_count ?? 0} / {metrics?.backlink_opportunities ?? 0}
          </div>
          <div className="kpi-delta">Authority engine →</div>
        </Link>
      </div>

      {/* MAIN GRID */}
      <div className="dash-grid">
        {/* LEFT COLUMN */}
        <div>
          {/* MANUAL OVERRIDE GENERATOR */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Manual Override — Force Generate Now</span>
              <span className="badge badge-accent">Optional</span>
            </div>
            <div className="panel-body">
              <p style={{ fontSize: "10px", color: "var(--muted)", marginBottom: "10px" }}>
                Articles normally generate automatically every day at 11:00 IST from your highest-priority keyword.
                Use this only when you want to force one right now.
              </p>
              <form onSubmit={handleRunPipeline}>
                <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr auto", gap: "12px", marginBottom: "8px" }}>
                  <input
                    type="text"
                    className="field"
                    placeholder="Article topic"
                    value={genTopic}
                    onChange={(e) => setGenTopic(e.target.value)}
                    disabled={isGenerating}
                  />
                  <input
                    type="text"
                    className="field"
                    placeholder="Primary keyword (optional)"
                    value={genKeyword}
                    onChange={(e) => setGenKeyword(e.target.value)}
                    disabled={isGenerating}
                  />
                  <button
                    type="submit"
                    className="btn btn-accent"
                    disabled={isGenerating || !genTopic.trim()}
                    style={{ padding: "8px 18px", fontWeight: 600 }}
                  >
                    {isGenerating ? "Starting..." : "Force Generate"}
                  </button>
                </div>
                {genError && <span style={{ fontSize: "10px", color: "var(--red)" }}>{genError}</span>}
              </form>
            </div>
          </div>

          {/* RECENT CONTENT STREAM */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Recent Content Stream</span>
              <button className="panel-action" onClick={fetchDashboardData}>
                Refresh
              </button>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Article Title</th>
                    <th>Keyword</th>
                    <th>Status</th>
                    <th>Date</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics?.recent_content && metrics.recent_content.length > 0 ? (
                    metrics.recent_content.map((item) => {
                      const isPublished =
                        item.status === "published" || item.approval_status === "published";
                      return (
                        <tr key={item.id}>
                          <td style={{ fontWeight: 600, maxWidth: "240px" }}>{item.title}</td>
                          <td>
                            <span style={{ color: "var(--muted)", fontSize: "10px" }}>
                              {item.keyword || "—"}
                            </span>
                          </td>
                          <td>
                            <span className={`badge ${isPublished ? "badge-green" : item.status === "failed" ? "badge-red" : "badge-amber"}`}>
                              {item.approval_status === "published" ? "published" : item.status}
                            </span>
                          </td>
                          <td style={{ fontSize: "9.5px", color: "var(--muted)" }}>
                            {item.created_at ? new Date(item.created_at).toLocaleDateString() : "—"}
                          </td>
                          <td>
                            <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                              <button
                                type="button"
                                className="btn"
                                style={{ fontSize: "8.5px", padding: "2px 7px", color: "var(--accent)", borderColor: "var(--accent)" }}
                                onClick={() => openDraftPreview(item)}
                              >
                                View Draft
                              </button>
                              {!isPublished && item.approval_id ? (
                                <button
                                  type="button"
                                  className="btn btn-accent"
                                  style={{ fontSize: "8.5px", padding: "2px 7px" }}
                                  disabled={approvingId === item.approval_id}
                                  onClick={() => handleApproveDraft(item)}
                                >
                                  {approvingId === item.approval_id ? "Publishing..." : "Approve ✓"}
                                </button>
                              ) : isPublished ? (
                                <a
                                  href={item.wordpress_url || "#"}
                                  target="_blank"
                                  rel="noreferrer"
                                  style={{ color: "var(--green)", fontSize: "9px", textDecoration: "none" }}
                                >
                                  Live ↗
                                </a>
                              ) : null}
                              {!isPublished && (
                                <button
                                  type="button"
                                  className="btn"
                                  style={{ fontSize: "8.5px", padding: "2px 7px", color: "var(--red)", borderColor: "rgba(255,85,85,0.4)" }}
                                  title="Delete Draft"
                                  onClick={() => handleDeleteDraft(item)}
                                >
                                  🗑️
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={5} style={{ textAlign: "center", padding: "24px", color: "var(--muted)" }}>
                        No articles yet. The system generates its first article automatically within an hour of
                        connecting a website — or use Manual Override above.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN */}
        <div>
          {/* PUBLISHING SCHEDULE (replaces standalone calendar nav) */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Publishing Schedule — Next 7 Days</span>
              {metrics?.publishing_schedule?.length ? (
                <span className="badge badge-green">{metrics.publishing_schedule.length} planned</span>
              ) : null}
            </div>
            <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              {metrics?.publishing_schedule?.length ? (
                metrics.publishing_schedule.slice(0, 6).map((s) => (
                  <div key={s.id} style={{ display: "flex", justifyContent: "space-between", fontSize: "11px" }}>
                    <span style={{ maxWidth: "65%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {s.title}
                    </span>
                    <span style={{ color: "var(--muted)" }}>{s.date}</span>
                  </div>
                ))
              ) : (
                <span style={{ fontSize: "11px", color: "var(--muted)" }}>
                  Nothing scheduled yet. Each generated article gets a publish slot 48 hours out automatically.
                </span>
              )}
            </div>
          </div>

          {/* ACTIVE AUTONOMOUS AGENTS — REAL STATUS FROM TASKS TABLE */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Autonomous Agents</span>
              <span className={`badge ${metrics?.agents?.some((a) => a.state === "ACTIVE") ? "badge-green" : "badge-amber"}`}>
                {metrics?.agents?.filter((a) => a.state === "ACTIVE").length ?? 0}/6 Active
              </span>
            </div>
            <div style={{ padding: "8px 12px" }}>
              {(metrics?.agents || AGENT_ROLES as any).length !== undefined &&
                (metrics?.agents || []).map((agent) => (
                  <div className="agent-row" key={agent.name} title={agent.error || agent.summary || undefined}>
                    <div>
                      <div className="agent-name" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <span
                          className="live-dot"
                          style={{
                            width: "5px",
                            height: "5px",
                            background:
                              agent.state === "ACTIVE" ? "var(--green)" :
                              agent.state === "ERROR" ? "var(--red)" : "#f59e0b",
                          }}
                        ></span>
                        {agent.name}
                      </div>
                      <div className="agent-meta">
                        {AGENT_ROLES[agent.name] || ""}
                        {agent.last_run
                          ? ` · last run ${new Date(agent.last_run).toLocaleString()}`
                          : " · never run"}
                      </div>
                    </div>
                    <span className={`badge ${stateBadge(agent.state)}`}>{agent.state}</span>
                  </div>
                ))}
              {!metrics?.agents?.length && (
                <div style={{ fontSize: "11px", color: "var(--muted)", padding: "8px 0" }}>
                  Agent statuses appear once autonomous jobs start running (immediately after setup).
                </div>
              )}
            </div>
          </div>

          {/* QUICK ACTIONS */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Quick Actions</span>
            </div>
            <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <Link href="/writer" className="btn btn-accent" style={{ width: "100%", padding: "9px", textAlign: "center", textDecoration: "none", display: "block", fontWeight: 600 }}>
                ⚡ Open Full Writer Studio
              </Link>
              <Link href="/approvals" className="btn btn-primary" style={{ width: "100%", padding: "9px", textAlign: "center", textDecoration: "none", display: "block" }}>
                📋 Review Pending Approvals ({metrics?.pending_articles ?? 0})
              </Link>
              <Link href="/connectors" className="btn" style={{ width: "100%", padding: "9px", textAlign: "center", textDecoration: "none", display: "block" }}>
                🔌 Connectors (Slack/WP/Serper)
              </Link>
            </div>
          </div>

          {/* SEO HEALTH BREAKDOWN — from real audit only */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">SEO Health Breakdown</span>
              <span style={{ fontFamily: "'DotGothic16', sans-serif", fontSize: "18px", color: "var(--accent)" }}>
                {metrics?.seo_health_score != null ? `${metrics.seo_health_score}/100` : "—"}
              </span>
            </div>
            <div className="panel-body">
              {metrics?.seo_health_score != null ? (
                <>
                  <div className="prog-row">
                    <div className="prog-label">
                      <span>Technical Health (last audit)</span>
                      <span>{metrics.seo_health_score}%</span>
                    </div>
                    <div className="prog-track">
                      <div className="prog-fill" style={{ width: `${metrics.seo_health_score}%` }}></div>
                    </div>
                  </div>
                  <div className="prog-row">
                    <div className="prog-label">
                      <span>Knowledge Coverage</span>
                      <span>{Math.min(100, (metrics.knowledge_count || 0) * 2)}%</span>
                    </div>
                    <div className="prog-track">
                      <div className="prog-fill" style={{ width: `${Math.min(100, (metrics.knowledge_count || 0) * 2)}%` }}></div>
                    </div>
                  </div>
                  <div className="prog-row">
                    <div className="prog-label">
                      <span>Audit Date</span>
                      <span>{metrics.last_audit_date ? new Date(metrics.last_audit_date).toLocaleDateString() : "—"}</span>
                    </div>
                  </div>
                </>
              ) : (
                <div style={{ fontSize: "11px", color: "var(--muted)" }}>
                  No technical audit has run yet. TechSEOAgent runs automatically at 12:00 IST daily,
                  or trigger it now from the Workforce page.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* DRAFT PREVIEW MODAL — rendered HTML like WordPress */}
      {selectedArticle && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,.6)",
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "var(--bg)",
              border: "1px solid var(--border)",
              width: "100%",
              maxWidth: "760px",
              maxHeight: "85vh",
              display: "flex",
              flexDirection: "column",
              boxShadow: "0 8px 32px rgba(0,0,0,.5)",
            }}
          >
            <div
              style={{
                padding: "12px 18px",
                borderBottom: "1px solid var(--border)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                background: "var(--panel-bg)",
              }}
            >
              <div>
                <div style={{ fontFamily: "'DotGothic16', sans-serif", fontSize: "16px", textTransform: "uppercase" }}>
                  {selectedArticle.title}
                </div>
                <div style={{ fontSize: "9.5px", color: "var(--muted)", textTransform: "uppercase" }}>
                  Status: {selectedArticle.approval_status || selectedArticle.status} · Keyword: {selectedArticle.keyword || "—"}
                </div>
              </div>
              <button
                type="button"
                className="btn"
                style={{ fontSize: "11px", padding: "4px 8px" }}
                onClick={() => setSelectedArticle(null)}
              >
                ✕
              </button>
            </div>

            <div style={{ flex: 1, overflowY: "auto", padding: "18px", fontSize: "12px", lineHeight: "1.6" }}>
              {selectedArticle.html_content ? (
                <div dangerouslySetInnerHTML={{ __html: selectedArticle.html_content }} />
              ) : selectedArticle.content ? (
                <pre style={{ fontFamily: "'IBM Plex Mono', monospace", whiteSpace: "pre-wrap", color: "var(--ink)", background: "var(--panel-inner)", padding: "14px", border: "1px solid var(--line)" }}>
                  {selectedArticle.content}
                </pre>
              ) : (
                <div style={{ color: "var(--muted)" }}>
                  Article body not generated yet — this row was created before content finished writing.
                </div>
              )}
            </div>

            <div
              style={{
                padding: "12px 18px",
                borderTop: "1px solid var(--border)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                background: "var(--panel-bg)",
              }}
            >
              <button
                type="button"
                className="btn"
                onClick={() => {
                  navigator.clipboard.writeText(selectedArticle.content || selectedArticle.html_content || "");
                  showToast("✓ Copied to clipboard!");
                }}
              >
                📋 Copy Text
              </button>
              <div style={{ display: "flex", gap: "8px" }}>
                <button type="button" className="btn" onClick={() => setSelectedArticle(null)}>
                  Close
                </button>
                {selectedArticle.approval_status !== "published" && selectedArticle.status !== "published" && selectedArticle.approval_id && (
                  <button
                    type="button"
                    className="btn btn-accent"
                    disabled={approvingId === selectedArticle.approval_id}
                    onClick={() => handleApproveDraft(selectedArticle)}
                  >
                    {approvingId === selectedArticle.approval_id ? "Publishing..." : "Approve & Publish ✓"}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* BOTTOM TICKER */}
      <div className="bticker">
        <span className="bticker-inner">
          <span className="bt-sq"></span>RANKFORGE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SINGLE SOURCE METRICS <span className="bt-sep">/</span>
          <span className="bt-sq"></span>NVIDIA NIM LLAMA-70B CONNECTED <span className="bt-sep">/</span>
          <span className="bt-sq"></span>AUTONOMOUS DAILY CADENCE &nbsp;&nbsp;&nbsp;&nbsp;
          <span className="bt-sq"></span>RANKFORGE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SINGLE SOURCE METRICS <span className="bt-sep">/</span>
          <span className="bt-sq"></span>NVIDIA NIM LLAMA-70B CONNECTED <span className="bt-sep">/</span>
          <span className="bt-sq"></span>AUTONOMOUS DAILY CADENCE
        </span>
      </div>
    </div>
  );
}
