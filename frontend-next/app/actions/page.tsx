"use client";
import { useEffect, useState, useCallback } from "react";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

export default function ActionsPage() {
  const [wid, setWid] = useState("");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    const id = getCurrentWebsiteId();
    setWid(id);
    if (!id) { setLoading(false); return; }
    try {
      setLoading(true);
      const res = await get(`/api/actions/${id}/top-10`);
      setData(res);
    } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); const h = () => load(); window.addEventListener("website-changed", h); return () => window.removeEventListener("website-changed", h); }, [load]);

  const exec = async (actionId: string) => {
    try { setBusy(actionId); await post(`/api/actions/${wid}/${actionId}/execute`, { author: "Admin Operator" }); await load(); }
    catch (e: any) { setError(e.message); } finally { setBusy(null); }
  };
  const dismiss = async (actionId: string) => {
    try { await post(`/api/actions/${wid}/${actionId}/dismiss`, {}); await load(); }
    catch (e: any) { setError(e.message); }
  };

  if (!wid) return <div className="page-container active" style={{ padding: 30 }}>Select website in /websites first.</div>;
  if (loading) return <div className="page-container active" style={{ padding: 40 }}>Ranking actions…</div>;

  const actions = data?.actions || [];
  return (
    <div className="page-container active" style={{ padding: 24 }}>
      <div className="page-heading">Do These 10 Things Now</div>
      <div className="page-sub"><span className="sub-sq"></span>{data?.domain} · +{data?.total_potential_clicks_per_month || 0} clicks/mo potential</div>
      {error && <div className="notice" style={{ borderColor: "var(--red)" }}>{error}</div>}
      <div className="panel"><div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {actions.map((a: any) => (
          <div key={a.id} style={{ border: "1px solid var(--line)", padding: 12 }}>
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <span className="badge badge-accent">#{a.rank}</span>
              <strong style={{ flex: 1 }}>{a.title}</strong>
              <span style={{ fontSize: 11 }}>+{a.impact_clicks_per_month}/mo · {a.effort}</span>
            </div>
            <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 6 }}>{a.rationale}</div>
            <div style={{ fontSize: 11, marginTop: 6 }}>Target: {a.target_url} · Query: {a.target_query}</div>
            {a.preview_diff && <details style={{ fontSize: 11, marginTop: 6 }}><summary>Preview diff</summary><pre style={{ whiteSpace: "pre-wrap" }}>BEFORE: {a.preview_diff.before}{"\n"}AFTER: {a.preview_diff.after}</pre></details>}
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <button className="btn btn-accent" disabled={busy === a.id} onClick={() => exec(a.id)}>{busy === a.id ? "Applying…" : "Apply with guardrail"}</button>
              <button className="btn" onClick={() => dismiss(a.id)}>Dismiss</button>
            </div>
          </div>
        ))}
        {actions.length === 0 && <div>No actions. Run crawl first.</div>}
      </div></div>
    </div>
  );
}
