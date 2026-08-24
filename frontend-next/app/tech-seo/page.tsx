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

  const fetchAuditData = useCallback(async () => {
    const wid = getCurrentWebsiteId() || websiteId || getWebsiteId();
    if (!wid) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      let data = await get(`/api/tech-seo/${wid}`);
      if (!data || !data.last_run || data.status === "not_run") {
        setRunning(true);
        const freshAudit = await post(`/api/tech-seo/${wid}/audit`, {});
        setAuditData(freshAudit?.data || freshAudit);
      } else {
        setAuditData(data?.data || data);
      }
    } catch (e: any) {
      setError(e.message || "Failed to load audit data");
    } finally {
      setLoading(false);
      setRunning(false);
    }
  }, [websiteId]);

  useEffect(() => {
    fetchAuditData();
  }, [fetchAuditData]);

  const runLiveAudit = async () => {
    const wid = websiteId || getCurrentWebsiteId() || getWebsiteId();
    if (!wid) return;

    setRunning(true);
    setError(null);
    try {
      const data = await post(`/api/tech-seo/${wid}/audit`, {});
      setAuditData(data?.data || data);
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
            <strong>No website selected.</strong> Go to Settings or Websites and add your website first.
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

              {/* Issues */}
              {auditData.issues && auditData.issues.length > 0 ? (
                <div>
                  <h3 style={{ fontSize: "13px", fontWeight: 600, marginBottom: "8px", textTransform: "uppercase", color: "var(--muted)" }}>
                    Detected Action Items ({auditData.issues.length})
                  </h3>
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {auditData.issues.map((issue: any, i: number) => (
                      <div
                        key={i}
                        style={{
                          padding: "10px 14px",
                          border: "1px solid var(--line)",
                          borderLeft: "4px solid var(--accent)",
                          background: "var(--surface)",
                          fontSize: "12px",
                        }}
                      >
                        <strong style={{ color: "var(--accent)" }}>{issue.type || "Issue"}:</strong> {issue.description || issue.message}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div style={{ padding: "20px", textAlign: "center", color: "var(--green)", fontSize: "12px" }}>
                  ✓ Zero technical issues detected. Robots.txt, sitemap, meta tags, and SSL are fully operational.
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