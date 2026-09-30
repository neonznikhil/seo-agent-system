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
  const [measuring, setMeasuring] = useState(false);
  const [measureMsg, setMeasureMsg] = useState<string | null>(null);

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
  const measure = async () => {
    setMeasuring(true); setMeasureMsg(null); setError(null);
    try {
      const r = await post(`/api/competitors/${wid}/measure`, {});
      if (r.measured) {
        setMeasureMsg(`Measured ${r.keywords_measured} keyword(s) from live SERPs.`);
      } else {
        setMeasureMsg(r.message || "Measurement returned no SERP data.");
      }
      await load();
    } catch (e: any) { setError(e.message); }
    finally { setMeasuring(false); }
  };

  if (!wid) return <div className="page-container active" style={{ padding: 30 }}>Select website first.</div>;
  return (
    <div className="page-container active" style={{ padding: 24 }}>
      <div className="page-heading">Competitor Tracking</div>
      <div className="page-sub"><span className="sub-sq"></span>Share of voice · new pages · outrank gaps</div>
      {error && <div className="notice" style={{ borderColor: "var(--red)" }}>{error}</div>}
      {measureMsg && <div className="notice" style={{ marginBottom: 12 }}><span>{measureMsg}</span></div>}
      <div className="panel" style={{ marginBottom: 12 }}><div className="panel-body" style={{ display: "flex", gap: 8 }}>
        <input value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="competitor.com" className="field" style={{ flex: 1, padding: 8 }} />
        <button className="btn btn-accent" onClick={add}>Add competitor</button>
        <button className="btn" onClick={measure} disabled={measuring || comps.length === 0}>{measuring ? "Measuring…" : "Measure now"}</button>
      </div></div>
      <div className="panel"><div className="panel-head"><span className="panel-label">Tracked ({comps.length}) · Share of Voice</span></div>
        <div className="panel-body">
          {sov && (
            <div style={{ marginBottom: 12, fontSize: 12 }}>
              <div style={{ marginBottom: 6, color: "var(--muted)" }}>{sov.message}</div>
              {sov.measured && (
                <div style={{ display: "flex", gap: 18, flexWrap: "wrap", marginBottom: 10 }}>
                  <span>Leader: <strong>{sov.market_leader?.domain ?? "—"}</strong>{sov.market_leader?.sov_percentage != null ? ` (${sov.market_leader.sov_percentage}%)` : ""}</span>
                  <span>Your visibility: top-3 <strong>{sov.own_visibility?.top_3_count ?? 0}</strong> · top-10 <strong>{sov.own_visibility?.top_10_count ?? 0}</strong></span>
                  {sov.measured_at && <span>Measured: <strong>{String(sov.measured_at).slice(0, 10)}</strong></span>}
                </div>
              )}
            </div>
          )}
          {comps.length > 0 && (
            <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
              <thead><tr style={{ textAlign: "left", color: "var(--muted)" }}>
                <th style={{ padding: 6 }}>Domain</th><th style={{ padding: 6 }}>SOV</th>
                <th style={{ padding: 6 }}>Top 3</th><th style={{ padding: 6 }}>Top 10</th>
                <th style={{ padding: 6 }}>Measured</th><th style={{ padding: 6 }}></th>
              </tr></thead>
              <tbody>
                {comps.map((c: any) => (
                  <tr key={c.id || c.domain} style={{ borderTop: "1px solid var(--line)" }}>
                    <td style={{ padding: 6, fontWeight: 600 }}>{c.domain}</td>
                    <td style={{ padding: 6 }}>{c.sov_percentage != null ? `${c.sov_percentage}%` : <span style={{ color: "var(--muted)" }}>not measured</span>}</td>
                    <td style={{ padding: 6 }}>{c.top_3_rankings ?? "—"}</td>
                    <td style={{ padding: 6 }}>{c.top_10_rankings ?? "—"}</td>
                    <td style={{ padding: 6, color: "var(--muted)" }}>{c.measured_at ? String(c.measured_at).slice(0, 10) : (c.verification || "—")}</td>
                    <td style={{ padding: 6, textAlign: "right" }}><button className="btn" onClick={() => remove(c.id)}>Remove</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {comps.length === 0 && <div style={{ fontSize: 12, color: "var(--muted)" }}>No competitors tracked yet. Add a domain above.</div>}
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
