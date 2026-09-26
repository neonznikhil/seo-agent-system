"use client";
import { useEffect, useState, useCallback } from "react";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

export default function LeadsPage() {
  const [wid, setWid] = useState("");
  const [data, setData] = useState<any>(null);
  const [spend, setSpend] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const id = getCurrentWebsiteId();
    setWid(id);
    if (!id) return;
    try { const res = await get(`/api/leads/${id}/keyword-performance`); setData(res); }
    catch (e: any) { setError(e.message); }
  }, []);

  useEffect(() => { load(); const h = () => load(); window.addEventListener("website-changed", h); return () => window.removeEventListener("website-changed", h); }, [load]);

  const saveSpend = async () => {
    try { await post(`/api/leads/${wid}/settings`, { website_id: wid, monthly_seo_spend: parseFloat(spend) }); await load(); }
    catch (e: any) { setError(e.message); }
  };

  if (!wid) return <div className="page-container active" style={{ padding: 30 }}>Select website first.</div>;
  const rows = data?.keywords || data?.attribution || [];
  const summary = data?.summary || {};

  return (
    <div className="page-container active" style={{ padding: 24 }}>
      <div className="page-heading">Leads Tied To Rankings</div>
      <div className="page-sub"><span className="sub-sq"></span>Cost per lead by keyword · GA4 conversions</div>
      {error && <div className="notice" style={{ borderColor: "var(--red)" }}>{error}</div>}
      <div className="panel" style={{ marginBottom: 12 }}><div className="panel-body" style={{ display: "flex", gap: 16, fontSize: 12, alignItems: "center", flexWrap: "wrap" }}>
        <span>Leads <strong>{summary.total_leads ?? summary.organic_leads ?? "—"}</strong></span>
        <span>Avg CPL <strong>{summary.avg_cpl ?? summary.average_cpl ?? "—"}</strong></span>
        <span>Pipeline <strong>{summary.pipeline_value ?? "—"}</strong></span>
        <input value={spend} onChange={(e) => setSpend(e.target.value)} placeholder="Monthly SEO spend" className="field" style={{ padding: 6, width: 160 }} />
        <button className="btn" onClick={saveSpend}>Save spend</button>
      </div></div>
      <div className="panel"><div className="panel-head"><span className="panel-label">Keyword CPL ({rows.length})</span></div>
        <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {rows.map((k: any, i: number) => (
            <div key={i} style={{ border: "1px solid var(--line)", padding: 10, fontSize: 12, display: "flex", gap: 12, flexWrap: "wrap" }}>
              <strong style={{ flex: 1 }}>{k.keyword || k.query}</strong>
              <span>Pos {k.position ?? k.current_position ?? "—"}</span>
              <span>Clicks {k.clicks ?? 0}</span>
              <span>Leads {k.leads ?? k.conversions ?? 0}</span>
              <span>CPL <strong>{k.cpl ?? k.cost_per_lead ?? "—"}</strong></span>
            </div>
          ))}
          {rows.length === 0 && <div style={{ fontSize: 12, color: "var(--muted)" }}>No attribution yet. Connect GA4/GSC in /connectors, then set spend.</div>}
        </div>
      </div>
    </div>
  );
}
