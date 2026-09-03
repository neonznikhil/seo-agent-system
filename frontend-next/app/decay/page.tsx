"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface DecayItem {
  id: string;
  url: string;
  keyword: string;
  old_rank: number;
  current_rank: number;
  change: number;
  status: string;
}

export default function DecayPage() {
  const [decayItems, setDecayItems] = useState<DecayItem[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [websiteId, setWebsiteId] = useState<string>("");

  const loadDecayData = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);
    if (!wid) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const [listRes, statsRes] = await Promise.allSettled([
        get(`/api/decay/${wid}/list`),
        get(`/api/decay/${wid}/stats`),
      ]);

      if (listRes.status === "fulfilled" && listRes.value) {
        const items = listRes.value.decay_logs || listRes.value.items || listRes.value || [];
        setDecayItems(Array.isArray(items) ? items : []);
      } else {
        setDecayItems([]);
      }

      if (statsRes.status === "fulfilled" && statsRes.value) {
        setStats(statsRes.value);
      }
    } catch (e: any) {
      // warn removed
      setError(e.message || "Failed to load content decay metrics");
      setDecayItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDecayData();
    const handleChanged = () => loadDecayData();
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [loadDecayData]);

  if (loading && decayItems.length === 0) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px auto" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Analyzing historical ranking decay & traffic drops...
        </p>
      </div>
    );
  }

  if (!websiteId) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">Content Decay Monitoring</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No data yet — add a website first.</strong> Connect your website to track ranking drops and trigger automated content refreshes.
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

  const decayingCount = decayItems.filter((d) => d.status === "decaying" || d.change > 0).length;

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      <div className="page-heading">Content Decay Detection</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Automated Ranking Degradation Tracking · Refresh Agent Triggers · Loss Prevention
        {error && (
          <span className="badge badge-amber" style={{ marginLeft: "12px" }}>
            {error}
          </span>
        )}
      </div>

      <div className="kpi-strip" style={{ marginBottom: "20px" }}>
        <div className="kpi-cell">
          <div className="kpi-label">Decaying URLs</div>
          <div className="kpi-val" style={{ color: decayingCount > 0 ? "var(--red)" : "var(--green)" }}>
            {stats?.decaying_count ?? decayingCount}
          </div>
          <div className="kpi-delta">{decayingCount > 0 ? "Rankings dropped > 3 pos" : "All rankings stable"}</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Monitored URLs</div>
          <div className="kpi-val">{stats?.total_monitored ?? decayItems.length}</div>
          <div className="kpi-delta">Historical positions checked</div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Decaying Articles & Pages</span>
          <button className="panel-action" onClick={loadDecayData}>
            Refresh
          </button>
        </div>
        <div className="panel-body" style={{ padding: "0" }}>
          {decayItems.length === 0 ? (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              ✓ Zero decaying content found. All ranked pages are maintaining their positions.
            </div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "12px" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--line)", color: "var(--muted)", textTransform: "uppercase", fontSize: "10px" }}>
                  <th style={{ padding: "10px 14px" }}>Page URL</th>
                  <th style={{ padding: "10px 14px" }}>Target Keyword</th>
                  <th style={{ padding: "10px 14px" }}>Old Rank</th>
                  <th style={{ padding: "10px 14px" }}>Current Rank</th>
                  <th style={{ padding: "10px 14px" }}>Drop</th>
                  <th style={{ padding: "10px 14px" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {decayItems.map((item, i) => (
                  <tr key={item.id || i} style={{ borderBottom: "1px solid var(--line)" }}>
                    <td style={{ padding: "10px 14px", fontWeight: 600 }}>{item.url}</td>
                    <td style={{ padding: "10px 14px" }}>{item.keyword}</td>
                    <td style={{ padding: "10px 14px" }}>#{item.old_rank}</td>
                    <td style={{ padding: "10px 14px" }}>
                      <span className="badge badge-red">#{item.current_rank}</span>
                    </td>
                    <td style={{ padding: "10px 14px", color: "var(--red)", fontWeight: 600 }}>
                      ↓ {item.change > 0 ? `+${item.change}` : item.change}
                    </td>
                    <td style={{ padding: "10px 14px" }}>
                      <Link
                        href={`/writer`}
                        className="btn btn-accent"
                        style={{ textDecoration: "none", fontSize: "10px", padding: "4px 8px" }}
                      >
                        ⚡ Refresh Post
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
