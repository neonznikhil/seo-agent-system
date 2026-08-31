"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId, getWebsiteId } from "@/lib/website";

export default function TechSEOPage() {
  const [auditData, setAuditData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState<boolean>(false);
  const [websiteId, setWebsiteId] = useState<string>("");
  const [secondsSinceUpdate, setSecondsSinceUpdate] = useState<number>(0);
  const [currentAuditTime, setCurrentAuditTime] = useState<string>("");

  useEffect(() => {
    const wid = getCurrentWebsiteId() || getWebsiteId();
    setWebsiteId(wid);

    const handleChanged = (e: any) => {
      const newWid = e?.detail || getCurrentWebsiteId() || getWebsiteId();
      setWebsiteId(newWid);
    };

    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, []);

  const fetchRecentAudit = async (wid: string) => {
    try {
      const data = await get(`/api/tech-seo/${wid}`);
      const audit = data?.data || data;
      if (audit && audit.health_score != null && audit.status !== "not_run") return audit;
      // Also try raw data wrapper
      if (audit && audit.health_score != null) return audit;
      return null;
    } catch {
      return null;
    }
  };

  const fetchAuditData = useCallback(async () => {
    let wid = getCurrentWebsiteId() || websiteId || getWebsiteId();
    if (!wid) {
      try {
        const sites = await get("/api/websites");
        const list = Array.isArray(sites) ? sites : sites?.websites || [];
        if (list.length > 0 && list[0]?.id) {
          wid = list[0].id;
          setWebsiteId(wid);
          localStorage.setItem("current-website-id", wid);
        }
      } catch {}
    }
    if (!wid) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      let data = await get(`/api/tech-seo/${wid}`);
      const audit = data?.data || data;
      if (!audit || audit.health_score === null || audit.status === "not_run") {
        setRunning(true);
        const freshAudit = await post(`/api/tech-seo/${wid}/audit`, {});
        const fresh = freshAudit?.data || freshAudit;
        setAuditData(fresh);
        setCurrentAuditTime(fresh?.last_run || fresh?.created_at || fresh?.completed_at || new Date().toISOString());
        setSecondsSinceUpdate(0);
      } else {
        setAuditData(audit);
        setCurrentAuditTime(audit?.last_run || audit?.created_at || audit?.completed_at || "");
        setSecondsSinceUpdate(0);
      }
    } catch (e: any) {
      setError(e.message || "Failed to load audit data");
    } finally {
      setLoading(false);
      setRunning(false);
    }
  }, [websiteId]);

  // FIX 1 — AUTO-LOAD ON PAGE OPEN (spec pattern)
  useEffect(() => {
    const initializeTechSEO = async () => {
      const wid = websiteId || getCurrentWebsiteId() || getWebsiteId();
      if (!wid) {
        // try to resolve website first
        try {
          const sites = await get("/api/websites");
          const list = Array.isArray(sites) ? sites : sites?.websites || [];
          if (list.length > 0 && list[0]?.id) {
            const nid = list[0].id;
            setWebsiteId(nid);
            localStorage.setItem("current-website-id", nid);
            // recurse with new wid
            const recent = await fetchRecentAudit(nid);
            if (recent) {
              setAuditData(recent);
              setCurrentAuditTime(recent.last_run || recent.created_at || recent.completed_at || "");
              setSecondsSinceUpdate(0);
              setLoading(false);
              return;
            } else {
              setLoading(true);
              setRunning(true);
              try {
                const freshAudit = await post(`/api/tech-seo/${nid}/audit`, {});
                const fresh = freshAudit?.data || freshAudit;
                setAuditData(fresh);
                setCurrentAuditTime(fresh?.last_run || fresh?.created_at || fresh?.completed_at || new Date().toISOString());
                setSecondsSinceUpdate(0);
              } catch (e: any) {
                setError(e.message || "Failed to run audit");
              } finally {
                setLoading(false);
                setRunning(false);
              }
              return;
            }
          }
        } catch {}
        setLoading(false);
        return;
      }
      setLoading(true);
      const recentAudit = await fetchRecentAudit(wid);
      if (recentAudit) {
        setAuditData(recentAudit);
        setCurrentAuditTime(recentAudit.last_run || recentAudit.created_at || recentAudit.completed_at || "");
        setSecondsSinceUpdate(0);
        setLoading(false);
      } else {
        setRunning(true);
        try {
          const freshAudit = await post(`/api/tech-seo/${wid}/audit`, {});
          const fresh = freshAudit?.data || freshAudit;
          setAuditData(fresh);
          setCurrentAuditTime(fresh?.last_run || fresh?.created_at || fresh?.completed_at || new Date().toISOString());
          setSecondsSinceUpdate(0);
        } catch (e: any) {
          setError(e.message || "Failed to run audit");
        } finally {
          setLoading(false);
          setRunning(false);
        }
      }
    };
    if (websiteId) {
      initializeTechSEO();
    } else {
      // still try if websiteId empty but we can resolve inside
      const maybeWid = getCurrentWebsiteId() || getWebsiteId();
      if (maybeWid) initializeTechSEO();
      else fetchAuditData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [websiteId]);

  // FIX 2 — AUTO-REFRESH EVERY 20 SECONDS
  useEffect(() => {
    const wid = websiteId || getCurrentWebsiteId() || getWebsiteId();
    if (!wid) return;
    const interval = setInterval(async () => {
      const latestAudit = await fetchRecentAudit(wid);
      if (latestAudit && (latestAudit.last_run || latestAudit.created_at) !== currentAuditTime) {
        // Check if newer
        const latestTime = latestAudit.last_run || latestAudit.created_at || latestAudit.completed_at || "";
        if (latestTime && latestTime !== currentAuditTime) {
          setAuditData(latestAudit);
          setCurrentAuditTime(latestTime);
          setSecondsSinceUpdate(0);
        }
      }
    }, 20000);

    const counter = setInterval(() => {
      setSecondsSinceUpdate((prev) => prev + 1);
    }, 1000);

    return () => {
      clearInterval(interval);
      clearInterval(counter);
    };
  }, [websiteId, currentAuditTime]);

  const runLiveAudit = async () => {
    const wid = websiteId || getCurrentWebsiteId() || getWebsiteId();
    if (!wid) return;

    setRunning(true);
    setError(null);
    try {
      const data = await post(`/api/tech-seo/${wid}/audit`, {});
      const fresh = data?.data || data;
      setAuditData(fresh);
      setCurrentAuditTime(fresh?.last_run || fresh?.created_at || fresh?.completed_at || new Date().toISOString());
      setSecondsSinceUpdate(0);
    } catch (err: any) {
      setError(`Audit failed: ${err.message}`);
    } finally {
      setRunning(false);
    }
  };

  if (!websiteId && !loading) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">Technical SEO Audit</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No website selected.</strong> Go to Websites and add your website first.
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

  if (loading && !auditData) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px auto" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Loading Technical SEO audit data...
        </p>
      </div>
    );
  }

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      <div className="page-heading">Technical SEO & Architecture</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Core Web Vitals · Crawl & Index Diagnostics · Security & Architecture Audit
      </div>

      {error && (
        <div className="notice" style={{ borderColor: "var(--red)", background: "rgba(239,68,68,0.08)", marginBottom: "16px" }}>
          <span className="notice-sq" style={{ background: "var(--red)" }}></span>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
            <span style={{ color: "var(--red)" }}>{error}</span>
            <button onClick={fetchAuditData} className="btn" style={{ fontSize: "11px", padding: "4px 10px" }}>
              Retry
            </button>
          </div>
        </div>
      )}

      {/* KPI STRIP */}
      <div className="kpi-strip" style={{ marginBottom: "20px" }}>
        <div className="kpi-cell">
          <div className="kpi-label">Health Score</div>
          <div className="kpi-val" style={{ color: (auditData?.health_score ?? 0) >= 80 ? "var(--green)" : "var(--accent)" }}>
            {auditData?.health_score !== null && auditData?.health_score !== undefined ? `${auditData.health_score}/100` : "Pending"}
          </div>
          <div className="kpi-delta">{auditData?.health_score ? "Live technical score" : "Audit not run yet"}</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Issues Found</div>
          <div className="kpi-val" style={{ color: (auditData?.issues?.length || 0) > 0 ? "var(--red)" : "var(--green)" }}>
            {auditData?.issues?.length || 0}
          </div>
          <div className="kpi-delta">{auditData?.issues?.length ? "Action items" : "All checks passing"}</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Last Audit</div>
          <div className="kpi-val" style={{ fontSize: "16px" }}>
            {auditData?.last_run ? new Date(auditData.last_run).toLocaleDateString() : "Never"}
          </div>
          <div className="kpi-delta">{auditData?.status || "Ready"}</div>
          {/* FIX 3 — LIVE REFRESH INDICATOR */}
          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "6px", fontSize: "10px", color: "var(--muted)" }}>
            <span style={{ width: "8px", height: "8px", background: "#00ff88", borderRadius: "50%", display: "inline-block", animation: "pulse 2s infinite" }}></span>
            Live — refreshes every 20s — last updated {secondsSinceUpdate}s ago
          </div>
        </div>
      </div>

      {/* AUDIT ACTIONS & RESULTS */}
      <div className="panel" style={{ marginBottom: "20px" }}>
        <div className="panel-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span className="panel-label">Technical Audit Results</span>
          <button
            onClick={runLiveAudit}
            disabled={running}
            className="btn btn-accent"
            style={{ padding: "8px 16px", fontSize: "12px", cursor: running ? "not-allowed" : "pointer" }}
          >
            {running ? "Scanning Site..." : "⚡ Run Live Audit"}
          </button>
        </div>
        <div className="panel-body">
          {auditData && (auditData.issues?.length > 0 || auditData.checks?.length > 0) ? (
            <div>
              {/* Checks */}
              {auditData.checks && auditData.checks.length > 0 && (
                <div style={{ marginBottom: "16px" }}>
                  <h3 style={{ fontSize: "13px", fontWeight: 600, marginBottom: "8px", textTransform: "uppercase", color: "var(--muted)" }}>
                    Verified Checks
                  </h3>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "10px" }}>
                    {auditData.checks.map((chk: any, i: number) => (
                      <div
                        key={i}
                        style={{
                          padding: "10px 12px",
                          border: "1px solid var(--line)",
                          background: "var(--surface)",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          fontSize: "12px",
                        }}
                      >
                        <span style={{ fontWeight: 500 }}>{chk.name}</span>
                        <span className={`badge ${chk.status === "Passed" ? "badge-green" : chk.status === "Warning" ? "badge-accent" : "badge-red"}`}>
                          {chk.value || chk.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Issues Grouped by Severity */}
              {auditData.issues && auditData.issues.length > 0 ? (
                <div style={{ marginBottom: "20px" }}>
                  <h3 style={{ fontSize: "13px", fontWeight: 600, marginBottom: "10px", textTransform: "uppercase", color: "var(--muted)" }}>
                    Detected Action Items ({auditData.issues.length})
                  </h3>
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {auditData.issues.map((issue: any, i: number) => {
                      const sev = (issue.severity || "Medium").toLowerCase();
                      const sevColor = sev === "critical" ? "var(--red)" : sev === "high" ? "var(--amber)" : sev === "medium" ? "var(--accent)" : "var(--muted)";
                      return (
                        <div
                          key={i}
                          style={{
                            padding: "12px 16px",
                            border: "1px solid var(--line)",
                            borderLeft: `4px solid ${sevColor}`,
                            background: "var(--surface)",
                            fontSize: "12px",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                            <strong style={{ color: "var(--ink)" }}>{issue.type || "Issue"}</strong>
                            <span className={`badge ${sev === "critical" || sev === "high" ? "badge-red" : "badge-accent"}`}>
                              {issue.severity || "Warning"}
                            </span>
                          </div>
                          <div style={{ color: "var(--muted)", marginBottom: issue.fix_suggestion ? "6px" : "0" }}>
                            {issue.description || issue.message}
                          </div>
                          {issue.fix_suggestion && (
                            <div style={{ fontSize: "11px", color: "var(--accent)", background: "rgba(255, 77, 18, 0.05)", padding: "6px 8px", borderLeft: "2px solid var(--accent)" }}>
                              <strong>Fix:</strong> {issue.fix_suggestion}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div style={{ padding: "20px", textAlign: "center", color: "var(--green)", fontSize: "12px", marginBottom: "16px" }}>
                  ✓ Zero technical issues detected. Robots.txt, sitemap, meta tags, and SSL are fully operational.
                </div>
              )}

              {/* Crawled URLs Table */}
              {((auditData.crawled_urls && auditData.crawled_urls.length > 0) || (auditData.metrics?.crawled_urls && auditData.metrics.crawled_urls.length > 0)) && (
                <div>
                  <h3 style={{ fontSize: "13px", fontWeight: 600, marginBottom: "10px", textTransform: "uppercase", color: "var(--muted)" }}>
                    Crawled Pages ({(auditData.crawled_urls || auditData.metrics?.crawled_urls).length})
                  </h3>
                  <div style={{ overflowX: "auto" }}>
                    <table className="dash-table" style={{ width: "100%", fontSize: "11.5px" }}>
                      <thead>
                        <tr>
                          <th>Page URL</th>
                          <th>Status</th>
                          <th>Title Tag</th>
                          <th>Meta Desc</th>
                          <th>H1 Tag</th>
                          <th>Canonical</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(auditData.crawled_urls || auditData.metrics?.crawled_urls).map((pg: any, idx: number) => (
                          <tr key={idx}>
                            <td style={{ maxWidth: "260px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              <a href={pg.url} target="_blank" rel="noreferrer" style={{ color: "var(--ink)", textDecoration: "none" }}>
                                {pg.url} ↗
                              </a>
                            </td>
                            <td>
                              <span className={`badge ${pg.status_code === 200 ? "badge-green" : "badge-red"}`}>
                                {pg.status_code}
                              </span>
                            </td>
                            <td style={{ maxWidth: "200px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {pg.title || "—"}
                            </td>
                            <td>
                              <span className={`badge ${pg.has_meta_desc ? "badge-green" : "badge-amber"}`}>
                                {pg.has_meta_desc ? "Present" : "Missing"}
                              </span>
                            </td>
                            <td>
                              <span className={`badge ${pg.has_h1 ? "badge-green" : "badge-amber"}`}>
                                {pg.has_h1 ? "Present" : "Missing"}
                              </span>
                            </td>
                            <td>
                              <span className={`badge ${pg.has_canonical ? "badge-green" : "badge-amber"}`}>
                                {pg.has_canonical ? "Present" : "Missing"}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              <p>No audit data yet. Click &quot;⚡ Run Live Audit&quot; above to scan your website.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}