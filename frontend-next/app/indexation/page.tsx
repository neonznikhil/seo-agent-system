"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface IndexationCheck {
  id?: string;
  checked_at: string;
  submitted_pages: number | null;
  indexed_pages: number | null;
  indexation_rate: number | null;
  method?: string;
  gate_passed?: boolean | null;
  not_indexed_urls?: string[];
  sitemap_url?: string | null;
  gsc_connected?: boolean;
  action_taken?: string | null;
}

interface GateState {
  gate: "pass" | "blocked" | "warn" | "unknown";
  indexation_rate?: number | null;
  threshold?: number;
  reason?: string;
  action?: string;
}

export default function IndexationPage() {
  const [websiteId, setWebsiteId] = useState<string>("");
  const [latest, setLatest] = useState<IndexationCheck | null>(null);
  const [gate, setGate] = useState<GateState | null>(null);
  const [history, setHistory] = useState<IndexationCheck[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [checking, setChecking] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  const loadData = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);
    if (!wid) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const [summaryRes, gateRes, histRes] = await Promise.allSettled([
        get(`/api/indexation/${wid}/latest`),
        get(`/api/indexation/${wid}/gate`),
        get(`/api/indexation/${wid}/history?limit=20`),
      ]);

      if (summaryRes.status === "fulfilled" && summaryRes.value) {
        setLatest(summaryRes.value);
      } else {
        setLatest(null);
      }

      if (gateRes.status === "fulfilled" && gateRes.value) {
        setGate(gateRes.value);
      } else {
        setGate(null);
      }

      if (histRes.status === "fulfilled" && histRes.value) {
        setHistory(histRes.value.history || []);
      } else {
        setHistory([]);
      }
    } catch (e: any) {
      setError(e.message || "Failed to load indexation data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const handleChanged = () => loadData();
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [loadData]);

  const handleRunCheck = async () => {
    if (!websiteId) {
      showToast("Please select a website first.");
      return;
    }
    setChecking(true);
    setError(null);
    try {
      const res = await post(`/api/indexation/${websiteId}/check`, {});
      if (res?.success) {
        showToast("✓ Indexation crawl completed and verified!");
        await loadData();
      } else {
        throw new Error(res?.detail || "Check failed");
      }
    } catch (e: any) {
      setError(e.message || "Failed to execute indexation check");
    } finally {
      setChecking(false);
    }
  };

  const rate = latest?.indexation_rate != null ? latest.indexation_rate : null;
  const ratePct = rate != null ? (rate * 100).toFixed(1) : null;
  const isPassed = gate?.gate === "pass" || (rate != null && rate >= 0.8);
  const isBlocked = gate?.gate === "blocked" || (rate != null && rate < 0.8);

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      {/* Toast */}
      {toast && (
        <div
          style={{
            position: "fixed",
            bottom: "24px",
            right: "24px",
            background: "var(--ink)",
            color: "var(--bg)",
            padding: "10px 18px",
            borderRadius: "6px",
            fontSize: "12px",
            fontWeight: 600,
            boxShadow: "0 8px 24px rgba(0,0,0,0.2)",
            zIndex: 9999,
          }}
        >
          {toast}
        </div>
      )}

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px", marginBottom: "20px" }}>
        <div>
          <div className="page-heading">Indexation & Crawl Budget Command</div>
          <div className="page-sub">
            <span className="sub-sq"></span>
            Real-time Indexation Checks · 80% Safety Gate · Crawl Budget Pacing Protection
          </div>
        </div>

        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <button
            onClick={handleRunCheck}
            disabled={checking || !websiteId}
            className="btn btn-accent"
            style={{ padding: "8px 18px", fontSize: "12px", fontWeight: 700 }}
          >
            {checking ? "⏳ Scanning Sitemap & GSC..." : "⚡ Run Real Indexation Check"}
          </button>
        </div>
      </div>

      {error && (
        <div className="notice" style={{ marginBottom: 20, borderColor: "var(--red)", background: "rgba(239, 68, 68, 0.08)" }}>
          <span className="notice-sq" style={{ background: "var(--red)" }}></span>
          <div style={{ color: "var(--red)" }}>{error}</div>
        </div>
      )}

      {/* OUTCOMES-FIRST KPI STRIP */}
      <div className="kpi-strip" style={{ marginBottom: "24px" }}>
        <div className="kpi-cell">
          <div className="kpi-label">Indexation Rate</div>
          <div
            className="kpi-val"
            style={{
              color: isPassed ? "var(--green)" : isBlocked ? "var(--amber)" : "var(--muted)",
            }}
          >
            {ratePct != null ? `${ratePct}%` : "—"}
          </div>
          <div className="kpi-delta">
            {latest?.indexed_pages != null && latest?.submitted_pages != null
              ? `${latest.indexed_pages} indexed / ${latest.submitted_pages} submitted`
              : "No verified check yet"}
          </div>
        </div>

        <div className="kpi-cell">
          <div className="kpi-label">Publishing Pacing Gate</div>
          <div style={{ marginTop: "6px" }}>
            {isBlocked ? (
              <span className="badge badge-amber" style={{ fontSize: "11px", padding: "4px 8px" }}>
                PAUSED (&lt; 80% GATE)
              </span>
            ) : isPassed ? (
              <span className="badge badge-green" style={{ fontSize: "11px", padding: "4px 8px" }}>
                NORMAL (≥ 80% GATE)
              </span>
            ) : (
              <span className="badge" style={{ fontSize: "11px", padding: "4px 8px" }}>
                UNKNOWN (RUN CHECK)
              </span>
            )}
          </div>
          <div className="kpi-delta" style={{ marginTop: "8px" }}>
            Target safety threshold: 80.0%
          </div>
        </div>

        <div className="kpi-cell">
          <div className="kpi-label">Data Source Provenance</div>
          <div className="kpi-val" style={{ fontSize: "14px", textTransform: "uppercase", letterSpacing: "0.5px" }}>
            {latest?.method || (latest ? "sitemap_crawl" : "Unconnected")}
          </div>
          <div className="kpi-delta">
            {latest?.gsc_connected ? "GSC Verified API" : "Sitemap XML Parser"}
          </div>
        </div>

        <div className="kpi-cell">
          <div className="kpi-label">Unindexed Pages</div>
          <div
            className="kpi-val"
            style={{
              color: (latest?.submitted_pages ?? 0) - (latest?.indexed_pages ?? 0) > 0 ? "var(--amber)" : "var(--green)",
            }}
          >
            {latest?.submitted_pages != null && latest?.indexed_pages != null
              ? Math.max(0, latest.submitted_pages - latest.indexed_pages)
              : "—"}
          </div>
          <div className="kpi-delta">Require link equity & fixes</div>
        </div>
      </div>

      {/* 80% GATE VISUALIZER & STATUS BANNER */}
      <div
        className="panel"
        style={{
          marginBottom: "24px",
          borderLeft: `4px solid ${isBlocked ? "var(--amber)" : isPassed ? "var(--green)" : "var(--line)"}`,
        }}
      >
        <div className="panel-body" style={{ padding: "20px 24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "8px" }}>
            <div style={{ fontWeight: 700, fontSize: "14px" }}>
              {isBlocked
                ? "⚠️ Crawl Budget Warning: Autonomous Publishing Is Paused"
                : isPassed
                ? "✓ Healthy Indexation: Publishing At Full Autonomous Speed"
                : "ℹ️ Indexation Status Unmeasured"}
            </div>
            <span style={{ fontSize: "11px", color: "var(--muted)" }}>
              Formula: (Indexed Pages / Submitted Pages) vs 80.0% Threshold
            </span>
          </div>

          <p style={{ fontSize: "12.5px", lineHeight: "1.6", color: "var(--muted)", margin: "0 0 16px 0" }}>
            {isBlocked
              ? "When recent pages aren't indexed, pumping out more articles wastes crawl budget and dilutes domain authority. RankForge automatically halts drafting and pivots workforce resources into internal linking, fixing canonical errors, and repairing broken URLs."
              : isPassed
              ? "Over 80% of your submitted pages are currently indexed by search engines. Crawl budget is healthy, authority is flowing cleanly, and autonomous content generation is proceeding as scheduled."
              : "Connect your Google Search Console or ensure your XML sitemap is reachable. Once verified, RankForge will govern your publishing pace automatically based on real search outcomes."}
          </p>

          {/* Progress bar */}
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "var(--muted)" }}>
              <span>0%</span>
              <span style={{ color: "var(--amber)", fontWeight: 600 }}>80% (Pacing Gate)</span>
              <span>100%</span>
            </div>
            <div style={{ width: "100%", height: "10px", background: "var(--line)", borderRadius: "5px", position: "relative", overflow: "hidden" }}>
              <div
                style={{
                  width: `${Math.min(100, Math.max(0, (rate ?? 0) * 100))}%`,
                  height: "100%",
                  background: (rate ?? 0) >= 0.8 ? "var(--green)" : "var(--amber)",
                  transition: "width 0.6s cubic-bezier(0.16, 1, 0.3, 1)",
                }}
              />
              {/* Threshold Marker line */}
              <div
                style={{
                  position: "absolute",
                  left: "80%",
                  top: 0,
                  bottom: 0,
                  width: "2px",
                  background: "var(--ink)",
                  opacity: 0.4,
                }}
              />
            </div>
          </div>

          {/* Recommended Counter-Measures */}
          {isBlocked && (
            <div style={{ marginTop: "18px", padding: "12px 16px", background: "rgba(245, 158, 11, 0.08)", borderRadius: "4px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
              <div>
                <strong style={{ fontSize: "12px", color: "var(--amber)" }}>Recommended Interventions:</strong>
                <span style={{ fontSize: "11.5px", marginLeft: "8px", color: "var(--ink)" }}>
                  Funnel link equity from high-traffic hubs to unindexed pages & audit canonical tags.
                </span>
              </div>
              <div style={{ display: "flex", gap: "8px" }}>
                <Link href="/links" className="btn btn-secondary" style={{ fontSize: "11px", padding: "4px 10px", textDecoration: "none" }}>
                  ⚡ Build Internal Links
                </Link>
                <Link href="/tech-seo" className="btn btn-secondary" style={{ fontSize: "11px", padding: "4px 10px", textDecoration: "none" }}>
                  ⚡ Audit Technical SEO
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* TWO COLUMNS: UNINDEXED URLS & CHECK HISTORY */}
      <div className="dash-grid">
        {/* UNINDEXED URLS TABLE */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">
              Pages Requiring Indexation Attention ({latest?.not_indexed_urls?.length ?? 0})
            </span>
          </div>
          <div className="panel-body" style={{ padding: 0 }}>
            {(!latest?.not_indexed_urls || latest.not_indexed_urls.length === 0) ? (
              <div style={{ padding: "32px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
                {latest ? "✓ No unindexed URLs reported in latest scan." : "No scan data available yet."}
              </div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "11.5px" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--line)", color: "var(--muted)", textTransform: "uppercase", fontSize: "10px" }}>
                    <th style={{ padding: "10px 14px", textAlign: "left" }}>URL</th>
                    <th style={{ padding: "10px 14px", textAlign: "left" }}>Action Needed</th>
                  </tr>
                </thead>
                <tbody>
                  {latest.not_indexed_urls.map((u, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid var(--line)" }}>
                      <td style={{ padding: "10px 14px", fontWeight: 600, wordBreak: "break-all" }}>{u}</td>
                      <td style={{ padding: "10px 14px" }}>
                        <span className="badge badge-amber">Needs Inbound Link</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* RUN HISTORY & ENVELOPES */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">Indexation Check History ({history.length})</span>
          </div>
          <div className="panel-body" style={{ padding: 0 }}>
            {history.length === 0 ? (
              <div style={{ padding: "32px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
                No prior indexation checks recorded. Run your first check above.
              </div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "11.5px" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--line)", color: "var(--muted)", textTransform: "uppercase", fontSize: "10px" }}>
                    <th style={{ padding: "10px 14px", textAlign: "left" }}>Date / Time</th>
                    <th style={{ padding: "10px 14px", textAlign: "left" }}>Rate</th>
                    <th style={{ padding: "10px 14px", textAlign: "left" }}>Coverage</th>
                    <th style={{ padding: "10px 14px", textAlign: "left" }}>Gate Status</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h, i) => {
                    const hRate = h.indexation_rate != null ? `${(h.indexation_rate * 100).toFixed(1)}%` : "—";
                    const passed = h.gate_passed === true;
                    return (
                      <tr key={i} style={{ borderBottom: "1px solid var(--line)" }}>
                        <td style={{ padding: "10px 14px", color: "var(--muted)" }}>
                          {new Date(h.checked_at).toLocaleDateString()} {new Date(h.checked_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </td>
                        <td style={{ padding: "10px 14px", fontWeight: 700 }}>
                          {hRate}
                        </td>
                        <td style={{ padding: "10px 14px", color: "var(--muted)" }}>
                          {h.indexed_pages ?? "?"} / {h.submitted_pages ?? "?"}
                        </td>
                        <td style={{ padding: "10px 14px" }}>
                          <span className={`badge ${passed ? "badge-green" : "badge-amber"}`}>
                            {passed ? "PASS" : "PAUSED"}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
