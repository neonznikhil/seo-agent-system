"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface Issue {
  severity: "high" | "medium" | "low";
  message: string;
}

export default function TechSeoPage() {
  const [healthScore, setHealthScore] = useState<number | null>(null);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [auditing, setAuditing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [websiteId, setWebsiteId] = useState<string>("");

  const fetchTechSEOData = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);
    if (!wid) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const techData = await get(`/api/tech-seo/${wid}`);
      if (techData) {
        setHealthScore(techData.health_score ?? (techData.score ? Math.round(techData.score) : null));
        setIssues(techData.issues || techData.critical_issues || []);
      }
    } catch (err: any) {
      console.warn("Tech SEO fetch error:", err);
      setError(err.message || "Failed to load Technical SEO audit");
      setHealthScore(null);
      setIssues([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTechSEOData();
    const handleChanged = () => fetchTechSEOData();
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [fetchTechSEOData]);

  const runAuditNow = async () => {
    if (!websiteId) return;
    try {
      setAuditing(true);
      setError(null);
      const res = await post(`/api/tech-seo/${websiteId}/run-audit`, {});
      if (res) {
        setHealthScore(res.health_score ?? (res.score ? Math.round(res.score) : null));
        setIssues(res.issues || []);
      }
    } catch (err: any) {
      setError(err.message || "Failed to run audit");
    } finally {
      setAuditing(false);
    }
  };

  if (loading && healthScore === null) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px auto" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Scanning Core Web Vitals, Crawlability, and Schema...
        </p>
      </div>
    );
  }

  if (!websiteId) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">Technical SEO Audit</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No data yet — add a website first.</strong> Connect your website to run autonomous technical audits and crawl health checks.
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
      <div className="page-heading">Technical SEO & Architecture</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Core Web Vitals · Crawl & Index Diagnostics · Schema Validation
        {error && (
          <span className="badge badge-amber" style={{ marginLeft: "12px" }}>
            {error}
          </span>
        )}
      </div>

      <div className="kpi-strip" style={{ marginBottom: "20px" }}>
        <div className="kpi-cell">
          <div className="kpi-label">Health Score</div>
          <div className="kpi-val" style={{ color: (healthScore ?? 0) >= 80 ? "var(--green)" : "var(--accent)" }}>
            {healthScore !== null ? `${healthScore}/100` : "Pending"}
          </div>
          <div className="kpi-delta">{healthScore !== null ? "Live technical score" : "Audit not run"}</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Detected Issues</div>
          <div className="kpi-val" style={{ color: issues.length > 0 ? "var(--red)" : "var(--green)" }}>
            {issues.length}
          </div>
          <div className="kpi-delta">{issues.length > 0 ? "Action items" : "All checks passing"}</div>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: "20px" }}>
        <div className="panel-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span className="panel-label">Live Technical Audit Diagnostic</span>
          <button onClick={runAuditNow} disabled={auditing} className="btn btn-accent" style={{ padding: "6px 14px", fontSize: "11px" }}>
            {auditing ? "Scanning Site..." : "⚡ Run Live Technical Audit"}
          </button>
        </div>
        <div className="panel-body">
          {issues.length === 0 ? (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--green)", fontSize: "12px" }}>
              ✓ Zero technical issues detected. Robots.txt, sitemap, meta tags, and Core Web Vitals are fully optimized.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {issues.map((issue, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: "12px 16px",
                    border: "1px solid var(--line)",
                    borderLeft: `4px solid ${issue.severity === "high" ? "var(--red)" : issue.severity === "medium" ? "#f97316" : "var(--accent)"}`,
                    background: "var(--surface)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                    <span className={`badge ${issue.severity === "high" ? "badge-red" : "badge-accent"}`}>
                      {issue.severity.toUpperCase()}
                    </span>
                    <span style={{ fontWeight: 600, fontSize: "13px" }}>{issue.message}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}