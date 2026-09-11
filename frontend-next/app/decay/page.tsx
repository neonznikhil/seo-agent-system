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
  const [detecting, setDetecting] = useState<boolean>(false);
  const [refreshingId, setRefreshingId] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
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
      setError(e.message || "Failed to load content decay metrics");
      setDecayItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleDetectDecay = async () => {
    if (!websiteId) return;
    try {
      setDetecting(true);
      setError(null);
      setSuccessMsg(null);
      const res = await post(`/api/decay/${websiteId}/detect`, {});
      const count = res?.data?.decayed_pages?.length ?? 0;
      setSuccessMsg(`Decay scan completed under run envelope. Found ${count} decaying page(s).`);
      await loadDecayData();
    } catch (e: any) {
      setError(e.message || "Decay detection scan failed");
    } finally {
      setDetecting(false);
    }
  };

  const handleTriggerRefresh = async (item: DecayItem) => {
    if (!websiteId || !item.id) return;
    try {
      setRefreshingId(item.id);
      setError(null);
      setSuccessMsg(null);
      const res = await post(`/api/decay/${item.id}/refresh?website_id=${websiteId}`, {});
      setSuccessMsg(`AI content refresh generated and staged in Approvals queue for '${item.keyword}'.`);
      await loadDecayData();
    } catch (e: any) {
      setError(e.message || "Failed to trigger AI content refresh");
    } finally {
      setRefreshingId(null);
    }
  };

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
        {successMsg && (
          <span className="badge badge-green" style={{ marginLeft: "12px" }}>
            {successMsg}
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
        <div className="panel-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span className="panel-label">Decaying Articles & Pages</span>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              className="btn btn-accent"
              onClick={handleDetectDecay}
              disabled={detecting}
              style={{ fontSize: "11px", padding: "4px 10px" }}
            >
              {detecting ? "Scanning Live..." : "⚡ Scan For Decaying Content"}
            </button>
            <button className="panel-action" onClick={loadDecayData}>
              Refresh
            </button>
          </div>
        </div>
        <div className="panel-body" style={{ padding: "0" }}>
          {decayItems.length === 0 ? (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              ✓ Zero decaying content found. All ranked pages are maintaining their positions. Click "Scan For Decaying Content" to check live positions.
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
                  <th style={{ padding: "10px 14px" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {decayItems.map((item, i) => (
                  <tr key={item.id || i} style={{ borderBottom: "1px solid var(--line)" }}>
                    <td style={{ padding: "10px 14px", fontWeight: 600 }}>
                      <a href={item.url} target="_blank" rel="noreferrer" style={{ color: "var(--ink)", textDecoration: "none" }}>
                        {item.url} ↗
                      </a>
                    </td>
                    <td style={{ padding: "10px 14px" }}>{item.keyword}</td>
                    <td style={{ padding: "10px 14px" }}>#{item.old_rank}</td>
                    <td style={{ padding: "10px 14px" }}>
                      <span className="badge badge-red">#{item.current_rank}</span>
                    </td>
                    <td style={{ padding: "10px 14px", color: "var(--red)", fontWeight: 600 }}>
                      ↓ {item.change > 0 ? `+${item.change}` : item.change}
                    </td>
                    <td style={{ padding: "10px 14px" }}>
                      <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                        <button
                          onClick={() => handleTriggerRefresh(item)}
                          disabled={refreshingId === item.id}
                          className="btn btn-accent"
                          style={{ fontSize: "10px", padding: "4px 8px", whiteSpace: "nowrap" }}
                        >
                          {refreshingId === item.id ? "Refreshing..." : "⚡ 1-Click AI Refresh"}
                        </button>
                        <Link
                          href={`/writer?topic=${encodeURIComponent(item.keyword)}`}
                          className="btn btn-secondary"
                          style={{ textDecoration: "none", fontSize: "10px", padding: "4px 8px", whiteSpace: "nowrap" }}
                        >
                          Manual Edit
                        </Link>
                      </div>
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
