"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get } from "@/lib/api";
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

export default function DashboardPage() {
  const [roiData, setRoiData] = useState<RoiData | null>(null);
  const [stats, setStats] = useState<any>(null);
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

      const [roiRes, statsRes] = await Promise.allSettled([
        get(`/api/roi/${wid}`),
        get(`/api/stats?website_id=${wid}`),
      ]);

      if (roiRes.status === "fulfilled" && roiRes.value) {
        setRoiData(roiRes.value);
      } else {
        setRoiData(null);
      }

      if (statsRes.status === "fulfilled" && statsRes.value) {
        setStats(statsRes.value);
      }
    } catch (e: any) {
      setError(e.message || "Failed to load ROI and dashboard performance");
    } finally {
      setLoading(false);
    }
  }, []);

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
    </div>
  );
}
