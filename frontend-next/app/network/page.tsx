"use client";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get } from "@/lib/api";
import { getCurrentWebsiteId, setCurrentWebsiteId } from "@/lib/website";

export default function NetworkPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await get("/api/network/overview");
      setData(res);
    } catch (e: any) {
      setError(e.message || "Failed to load network");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="page-container active" style={{ padding: 40, textAlign: "center" }}>Loading network…</div>;

  const sites = data?.sites || [];
  const summary = data?.summary || {};

  return (
    <div className="page-container active" style={{ padding: 24 }}>
      <div className="page-heading">Network: All Sites</div>
      <div className="page-sub"><span className="sub-sq"></span>Health, indexation, clicks, open issues per site</div>
      {error && <div className="notice" style={{ borderColor: "var(--red)", marginBottom: 16 }}><span>{error}</span></div>}
      <div className="panel" style={{ marginBottom: 16 }}><div className="panel-body" style={{ display: "flex", gap: 24, fontSize: 12 }}>
        <span>Sites: <strong>{summary.total_sites ?? data?.total_sites ?? sites.length}</strong></span>
        <span>Avg health: <strong>{summary.avg_health_score ?? data?.network_health_avg ?? "—"}</strong></span>
        <span>Clicks 28d: <strong>{summary.total_clicks_28d ?? data?.network_clicks_28d ?? 0}</strong></span>
        <span>Critical: <strong>{summary.critical_issues_total ?? 0}</strong></span>
        <button className="btn" onClick={load} style={{ marginLeft: "auto" }}>Refresh</button>
      </div></div>
      <div className="panel"><div className="panel-head"><span className="panel-label">Sites ({sites.length})</span></div>
        <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {sites.length === 0 && <div style={{ fontSize: 12, color: "var(--muted)" }}>No sites yet. <Link href="/websites">Add website</Link></div>}
          {sites.map((s: any) => (
            <div key={s.id} style={{ border: "1px solid var(--line)", padding: 12, display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ fontWeight: 700 }}>{s.domain}</div>
                <div style={{ fontSize: 11, color: "var(--muted)" }}>{s.status} · {s.last_audit_at || s.last_audit_date || "no audit"}</div>
              </div>
              <span>Health <strong>{s.health_score}</strong></span>
              <span>Index <strong>{s.indexation_rate}%</strong> ({s.indexed_pages}/{s.submitted_pages})</span>
              <span>Clicks <strong>{s.clicks_28d ?? s.performance_28d?.clicks ?? 0}</strong></span>
              <span>Issues <strong>{s.open_issues_count ?? s.open_issues?.total ?? 0}</strong></span>
              <button className="btn" onClick={() => { setCurrentWebsiteId(s.id); window.dispatchEvent(new CustomEvent("website-changed", { detail: s.id })); }}>Select</button>
              <Link className="btn" href={`/actions?site=${s.id}`}>Top 10</Link>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
