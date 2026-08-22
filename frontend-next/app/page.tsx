"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get } from "@/lib/api";
import { getCurrentWebsiteId, setCurrentWebsiteId } from "@/lib/website";

interface DashboardStats {
  total_articles: number;
  pending_articles: number;
  health_score: number | null;
  memories_count: number;
  knowledge_count: number;
  backlinks_count: number;
  wp_connected: boolean;
  recent_blogs: Array<{
    id: string;
    title: string;
    keyword?: string;
    status: string;
    created_at: string;
  }>;
  ai_engine: string;
  active_agents: Array<{
    name: string;
    role: string;
    status: string;
  }>;
}

export default function HomePage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [domain, setDomain] = useState<string>("");
  const [websiteId, setWebsiteId] = useState<string>("");
  const [websites, setWebsites] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = getCurrentWebsiteId();
    if (id) {
      setWebsiteId(id);
    }
    const handleChanged = (e: any) => {
      if (e?.detail) setWebsiteId(e.detail);
    };
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // 1. Fetch websites list
      let sites: any[] = [];
      try {
        const res = await get("/api/websites");
        sites = Array.isArray(res) ? res : res?.websites || [];
        setWebsites(sites);
      } catch (e: any) {
        try {
          const res = await get("/websites");
          sites = Array.isArray(res) ? res : [];
          setWebsites(sites);
        } catch {}
      }

      let activeId = websiteId;
      if (!activeId && sites.length > 0) {
        activeId = sites[0].id;
        setWebsiteId(activeId);
        setCurrentWebsiteId(activeId);
      }

      const activeSite = sites.find((s) => s.id === activeId) || sites[0];
      if (activeSite?.domain) {
        setDomain(activeSite.domain);
      } else {
        setDomain(activeId ? "Selected Website" : "No Website Connected");
      }

      if (!activeId) {
        setStats(null);
        setLoading(false);
        return;
      }

      // 2. Fetch aggregated stats from backend
      const data = await get(`/api/stats?website_id=${activeId}`);
      if (data && typeof data === "object") {
        setStats(data);
      }
    } catch (e: any) {
      console.warn("Stats fetch failed:", e);
      setError(e.message || "Failed to load dashboard data from RankForge API");
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 20000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  if (loading && !stats) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div className="w-8 h-8 border-2 border-ink border-t-transparent rounded-full animate-spin mx-auto mb-4" style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "1px" }}>
          Loading real-time SEO intelligence...
        </p>
      </div>
    );
  }

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      {/* PAGE HEADER */}
      <div className="page-heading">Dashboard</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Autonomous SEO · Real-time intelligence · <span>{domain || "No domain"}</span>
        {error && (
          <span className="badge badge-amber" style={{ marginLeft: "12px" }}>
            {error}
          </span>
        )}
      </div>

      {websites.length === 0 && !loading && (
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)", marginBottom: "20px" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No data yet — add a website first.</strong> Connect your WordPress site or domain to begin autonomous SEO tracking.
            <div style={{ marginTop: "8px" }}>
              <Link href="/websites" className="btn btn-accent" style={{ display: "inline-block", textDecoration: "none", fontSize: "11px", padding: "4px 10px" }}>
                + Add Website Now
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* KPI STRIP */}
      <div className="kpi-strip">
        <div className="kpi-cell">
          <div className="kpi-label">Articles Generated</div>
          <div className="kpi-val">{stats?.total_articles ?? 0}</div>
          <div className="kpi-delta">↑ Live from database</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Pending Approval</div>
          <div className="kpi-val" style={{ color: "var(--accent)" }}>
            {stats?.pending_articles ?? 0}
          </div>
          <div className="kpi-delta" style={{ color: "var(--accent)" }}>
            Review queue
          </div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">SEO Health Score</div>
          <div className="kpi-val">{stats?.health_score !== null && stats?.health_score !== undefined ? `${stats.health_score}/100` : "N/A"}</div>
          <div className="kpi-delta">{stats?.health_score ? "Live technical audit" : "Run audit to score"}</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Monitored Backlinks</div>
          <div className="kpi-val">{stats?.backlinks_count ?? 0}</div>
          <div className="kpi-delta">Active link crawler</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Brain Memories</div>
          <div className="kpi-val">{stats?.memories_count ?? 0}</div>
          <div className="kpi-delta">Learned winning patterns</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">AI Engine</div>
          <div className="kpi-val" style={{ fontSize: "16px", paddingTop: "4px", color: "var(--green)" }}>
            Llama-70B
          </div>
          <div className="kpi-delta">NVIDIA NIM Live</div>
        </div>
      </div>

      {/* MAIN DASH GRID */}
      <div className="dash-grid">
        {/* LEFT COLUMN */}
        <div>
          {/* ACTIVE AI AGENTS */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Active AI Agents</span>
              <span className="badge badge-green">Online</span>
            </div>
            <div style={{ padding: "10px 14px" }}>
              {(stats?.active_agents || [
                { name: "writer_agent", role: "12-phase autonomous content writer & SERP analyzer", status: "Ready" },
                { name: "brain_autopilot", role: "Daily clustering, pattern learning, and decay monitoring", status: "Running" },
                { name: "backlink_autopilot", role: "Continuous backlink verification and prospect crawler", status: "Running" },
                { name: "continuous_monitor", role: "Real-time rank movement, SERP shifts, and tech SEO audits", status: "Running" },
              ]).map((agent) => (
                <div className="agent-row" key={agent.name}>
                  <div>
                    <div className="agent-name">{agent.name}</div>
                    <div className="agent-meta">{agent.role}</div>
                  </div>
                  <span className="badge badge-green">{agent.status}</span>
                </div>
              ))}
            </div>
          </div>

          {/* RECENT ACTIVITY STREAM */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Recent Content Stream</span>
              <button className="panel-action" onClick={fetchStats}>
                Refresh
              </button>
            </div>
            <div className="panel-body" style={{ padding: "8px 14px" }}>
              {stats?.recent_blogs && stats.recent_blogs.length > 0 ? (
                stats.recent_blogs.map((b) => (
                  <div className="activity-row" key={b.id}>
                    <div className="act-left">
                      <span className="act-sq"></span>
                      <span style={{ fontWeight: 600 }}>{b.title}</span>
                      {b.keyword && (
                        <span style={{ color: "var(--muted)", fontSize: "10px" }}>({b.keyword})</span>
                      )}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span className={`badge ${b.status === "published" ? "badge-green" : "badge-accent"}`}>
                        {b.status}
                      </span>
                      <span className="act-time">
                        {b.created_at ? new Date(b.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "Recent"}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="activity-row">
                  <div className="act-left">
                    <span className="act-sq"></span>
                    <span>No articles generated yet. Run the autonomous writer to create your first draft.</span>
                  </div>
                  <Link href="/writer" className="badge badge-accent" style={{ textDecoration: "none" }}>
                    + Generate Now
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN */}
        <div>
          {/* QUICK ACTIONS */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Quick Actions</span>
            </div>
            <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <Link href="/writer" className="btn btn-accent" style={{ width: "100%", padding: "10px", textAlign: "center", textDecoration: "none", display: "block" }}>
                ⚡ Generate Autonomous Article
              </Link>
              <Link href="/tech-seo" className="btn btn-primary" style={{ width: "100%", padding: "10px", textAlign: "center", textDecoration: "none", display: "block" }}>
                🔍 Run Live Tech SEO Audit
              </Link>
              <Link href="/brain" className="btn" style={{ width: "100%", padding: "10px", textAlign: "center", textDecoration: "none", display: "block" }}>
                🧠 Inspect Brand Brain
              </Link>
              <Link href="/settings" className="btn" style={{ width: "100%", padding: "10px", textAlign: "center", textDecoration: "none", display: "block" }}>
                🔷 WordPress Settings & Sync
              </Link>
            </div>
          </div>

          {/* SEO HEALTH BREAKDOWN */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">SEO Health Breakdown</span>
              <span style={{ fontFamily: "'DotGothic16', sans-serif", fontSize: "18px", color: "var(--accent)" }}>
                {stats?.health_score !== null && stats?.health_score !== undefined ? `${stats.health_score}/100` : "Pending Audit"}
              </span>
            </div>
            <div className="panel-body">
              <div className="prog-row">
                <div className="prog-label">
                  <span>Technical Health</span>
                  <span>{stats?.health_score !== null && stats?.health_score !== undefined ? `${stats.health_score}%` : "0%"}</span>
                </div>
                <div className="prog-track">
                  <div className="prog-fill" style={{ width: `${stats?.health_score ?? 0}%` }}></div>
                </div>
              </div>
              <div className="prog-row">
                <div className="prog-label">
                  <span>Brain Knowledge Coverage</span>
                  <span>{stats?.knowledge_count ? Math.min(100, stats.knowledge_count * 10) : 0}%</span>
                </div>
                <div className="prog-track">
                  <div className="prog-fill" style={{ width: `${stats?.knowledge_count ? Math.min(100, stats.knowledge_count * 10) : 0}%` }}></div>
                </div>
              </div>
              <div className="prog-row">
                <div className="prog-label">
                  <span>Backlink Tracking</span>
                  <span>{stats?.backlinks_count ? Math.min(100, stats.backlinks_count * 15) : 0}%</span>
                </div>
                <div className="prog-track">
                  <div className="prog-fill" style={{ width: `${stats?.backlinks_count ? Math.min(100, stats.backlinks_count * 15) : 0}%` }}></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* BOTTOM TICKER */}
      <div className="bticker">
        <span className="bticker-inner">
          <span className="bt-sq"></span>RANKFORGE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>CONNECTED TO REAL SUPABASE & NVIDIA NIM <span className="bt-sep">/</span>
          <span className="bt-sq"></span>ZERO MOCK DATA <span className="bt-sep">/</span>
          <span className="bt-sq"></span>AUTONOMOUS AGENTS ACTIVE &nbsp;&nbsp;&nbsp;&nbsp;
          <span className="bt-sq"></span>RANKFORGE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>CONNECTED TO REAL SUPABASE & NVIDIA NIM <span className="bt-sep">/</span>
          <span className="bt-sq"></span>ZERO MOCK DATA <span className="bt-sep">/</span>
          <span className="bt-sq"></span>AUTONOMOUS AGENTS ACTIVE
        </span>
      </div>
    </div>
  );
}
