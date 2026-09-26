"use client";
import { useEffect, useState, useCallback } from "react";
import { get, post, del } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

export default function CompetitorsPage() {
  const [wid, setWid] = useState("");
  const [comps, setComps] = useState<any[]>([]);
  const [domain, setDomain] = useState("");
  const [sov, setSov] = useState<any>(null);
  const [pages, setPages] = useState<any[]>([]);
  const [matrix, setMatrix] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const id = getCurrentWebsiteId();
    setWid(id);
    if (!id) return;
    try {
      const c = await get(`/api/competitors/${id}`);
      setComps(c.competitors || []);
      try { setSov(await get(`/api/competitors/${id}/share-of-voice`)); } catch {}
      try { const n = await get(`/api/competitors/${id}/new-pages`); setPages(n.new_pages || []); } catch {}
      try { const m = await get(`/api/competitors/${id}/outranking-matrix`); setMatrix(m.outranked_queries || m.outranking_matrix || []); } catch {}
    } catch (e: any) { setError(e.message); }
  }, []);

  useEffect(() => { load(); const h = () => load(); window.addEventListener("website-changed", h); return () => window.removeEventListener("website-changed", h); }, [load]);

  const add = async () => {
    try { await post(`/api/competitors/${wid}`, { domain }); setDomain(""); await load(); }
    catch (e: any) { setError(e.message); }
  };
  const remove = async (id: string) => {
    try { await del(`/api/competitors/${wid}/${id}`); await load(); }
    catch (e: any) { setError(e.message); }
  };

  if (!wid) return <div className="page-container active" style={{ padding: 30 }}>Select website first.</div>;
  return (
    <div className="page-container active" style={{ padding: 24 }}>
      <div className="page-heading">Competitor Tracking</div>
      <div className="page-sub"><span className="sub-sq"></span>Share of voice · new pages · outrank gaps</div>
      {error && <div className="notice" style={{ borderColor: "var(--red)" }}>{error}</div>}
      <div className="panel" style={{ marginBottom: 12 }}><div className="panel-body" style={{ display: "flex", gap: 8 }}>
        <input value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="competitor.com" className="field" style={{ flex: 1, padding: 8 }} />
        <button className="btn btn-accent" onClick={add}>Add competitor</button>
      </div></div>
      <div className="panel"><div className="panel-head"><span className="panel-label">Tracked ({comps.length}) · SOV</span></div>
        <div className="panel-body">
          <pre style={{ fontSize: 11, whiteSpace: "pre-wrap" }}>{sov ? JSON.stringify(sov, null, 2).slice(0, 2000) : "No SOV yet"}</pre>
          {comps.map((c: any) => <div key={c.id || c.domain} style={{ display: "flex", gap: 8, fontSize: 12, padding: 6 }}><span style={{ flex: 1 }}>{c.domain}</span><button className="btn" onClick={() => remove(c.id)}>Remove</button></div>)}
        </div>
      </div>
      <div className="panel" style={{ marginTop: 12 }}><div className="panel-head"><span className="panel-label">New pages ({pages.length})</span></div>
        <div className="panel-body" style={{ fontSize: 12 }}>{pages.slice(0, 20).map((p: any, i: number) => <div key={i} style={{ padding: 6, borderBottom: "1px solid var(--line)" }}>{p.title || p.url} · {p.competitor}</div>)}{pages.length === 0 && "No new pages."}</div>
      </div>
      <div className="panel" style={{ marginTop: 12 }}><div className="panel-head"><span className="panel-label">Where they outrank you ({matrix.length})</span></div>
        <div className="panel-body" style={{ fontSize: 12 }}>{matrix.slice(0, 30).map((m: any, i: number) => <div key={i} style={{ padding: 6, borderBottom: "1px solid var(--line)" }}>{m.query || m.keyword} · you #{m.your_position} vs {m.competitor} #{m.competitor_position}</div>)}{matrix.length === 0 && "No gaps."}</div>
      </div>
    </div>
  );
}
