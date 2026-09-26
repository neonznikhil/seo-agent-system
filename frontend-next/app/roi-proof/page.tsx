"use client";
import { useEffect, useState, useCallback } from "react";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

export default function RoiProofPage() {
  const [wid, setWid] = useState("");
  const [fixes, setFixes] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ target_url: "", fix_title: "", category: "", target_keyword: "", baseline_position: "", baseline_monthly_clicks: "" });

  const load = useCallback(async () => {
    const id = getCurrentWebsiteId();
    setWid(id);
    if (!id) return;
    try {
      const l = await get(`/api/roi-proof/${id}/proof-list`);
      setFixes(l.tracked_fixes || []);
      try { setSummary(await get(`/api/roi-proof/${id}/summary`)); } catch {}
    } catch (e: any) { setError(e.message); }
  }, []);

  useEffect(() => { load(); const h = () => load(); window.addEventListener("website-changed", h); return () => window.removeEventListener("website-changed", h); }, [load]);

  const track = async () => {
    try {
      await post(`/api/roi-proof/${wid}/track`, {
        target_url: form.target_url, fix_title: form.fix_title, category: form.category,
        target_keyword: form.target_keyword, baseline_position: parseFloat(form.baseline_position),
        baseline_monthly_clicks: parseInt(form.baseline_monthly_clicks || "0"),
      });
      setForm({ target_url: "", fix_title: "", category: "", target_keyword: "", baseline_position: "", baseline_monthly_clicks: "" });
      await load();
    } catch (e: any) { setError(e.message); }
  };

  if (!wid) return <div className="page-container active" style={{ padding: 30 }}>Select website first.</div>;
  return (
    <div className="page-container active" style={{ padding: 24 }}>
      <div className="page-heading">Prove The Work: 28-Day Lift</div>
      <div className="page-sub"><span className="sub-sq"></span>Position and traffic lift per shipped fix</div>
      {error && <div className="notice" style={{ borderColor: "var(--red)" }}>{error}</div>}
      {summary && <div className="panel" style={{ marginBottom: 12 }}><div className="panel-body" style={{ fontSize: 12 }}><pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(summary, null, 2).slice(0, 1500)}</pre></div></div>}
      <div className="panel" style={{ marginBottom: 12 }}><div className="panel-head"><span className="panel-label">Track new fix</span></div>
        <div className="panel-body" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <input placeholder="Target URL" value={form.target_url} onChange={(e) => setForm({ ...form, target_url: e.target.value })} className="field" style={{ padding: 6 }} />
          <input placeholder="Fix title" value={form.fix_title} onChange={(e) => setForm({ ...form, fix_title: e.target.value })} className="field" style={{ padding: 6 }} />
          <input placeholder="Category" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="field" style={{ padding: 6 }} />
          <input placeholder="Keyword" value={form.target_keyword} onChange={(e) => setForm({ ...form, target_keyword: e.target.value })} className="field" style={{ padding: 6 }} />
          <input placeholder="Baseline position" value={form.baseline_position} onChange={(e) => setForm({ ...form, baseline_position: e.target.value })} className="field" style={{ padding: 6 }} />
          <input placeholder="Baseline clicks/mo" value={form.baseline_monthly_clicks} onChange={(e) => setForm({ ...form, baseline_monthly_clicks: e.target.value })} className="field" style={{ padding: 6 }} />
          <button className="btn btn-accent" onClick={track} style={{ gridColumn: "1 / -1" }}>Track 28 days</button>
        </div>
      </div>
      <div className="panel"><div className="panel-head"><span className="panel-label">Tracked fixes ({fixes.length})</span></div>
        <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {fixes.map((f: any, i: number) => (
            <div key={i} style={{ border: "1px solid var(--line)", padding: 10, fontSize: 12 }}>
              <strong>{f.fix_title}</strong> · {f.target_url}
              <div>Keyword {f.target_keyword} · base pos {f.baseline_position} · now {f.current_position ?? "—"} · lift {f.position_lift ?? "—"}</div>
              <div>Clicks {f.baseline_monthly_clicks} → {f.current_monthly_clicks ?? "—"} · day {f.day ?? f.days_tracked ?? 0}/28</div>
            </div>
          ))}
          {fixes.length === 0 && <div>No tracked fixes yet.</div>}
        </div>
      </div>
    </div>
  );
}
