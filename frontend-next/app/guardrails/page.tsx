"use client";
import { useEffect, useState, useCallback } from "react";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

export default function GuardrailsPage() {
  const [wid, setWid] = useState("");
  const [changes, setChanges] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const id = getCurrentWebsiteId();
    setWid(id);
    if (!id) return;
    try { const res = await get(`/api/guardrails/${id}/changelog`); setChanges(res.changes || res || []); }
    catch (e: any) { setError(e.message); }
  }, []);

  useEffect(() => { load(); const h = () => load(); window.addEventListener("website-changed", h); return () => window.removeEventListener("website-changed", h); }, [load]);

  const view = async (id: string) => {
    try { const res = await get(`/api/guardrails/change/${id}`); setSelected(res); }
    catch (e: any) { setError(e.message); }
  };
  const rollback = async (id: string) => {
    if (!confirm("Rollback this change on live site?")) return;
    try { await post(`/api/guardrails/change/${id}/rollback`, { author: "Admin Operator" }); await load(); setSelected(null); }
    catch (e: any) { setError(e.message); }
  };

  if (!wid) return <div className="page-container active" style={{ padding: 30 }}>Select website first.</div>;
  return (
    <div className="page-container active" style={{ padding: 24 }}>
      <div className="page-heading">Guardrails & Rollback</div>
      <div className="page-sub"><span className="sub-sq"></span>Preview diff · undo · change log · YMYL check</div>
      {error && <div className="notice" style={{ borderColor: "var(--red)" }}>{error}</div>}
      <div className="panel"><div className="panel-head"><span className="panel-label">Change log ({changes.length})</span></div>
        <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {changes.map((c: any) => (
            <div key={c.id} style={{ border: "1px solid var(--line)", padding: 10, fontSize: 12 }}>
              <div style={{ display: "flex", gap: 10 }}><strong style={{ flex: 1 }}>{c.title}</strong><span>{c.status}</span><span>{c.ymyl_flag}</span></div>
              <div style={{ color: "var(--muted)" }}>{c.target_url} · {c.created_at}</div>
              <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                <button className="btn" onClick={() => view(c.id)}>Preview diff</button>
                <button className="btn" onClick={() => rollback(c.id)}>Undo</button>
              </div>
            </div>
          ))}
          {changes.length === 0 && <div>No changes yet. Apply action in /actions.</div>}
        </div>
      </div>
      {selected && <div className="panel" style={{ marginTop: 12 }}><div className="panel-head"><span className="panel-label">Diff</span></div>
        <div className="panel-body"><pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(selected, null, 2)}</pre></div>
      </div>}
    </div>
  );
}
