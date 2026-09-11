"use client";

import { useEffect, useState, useCallback } from "react";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

const LIST_FIELDS = [
  { key: "structure_rules", label: "Structure rules (one per line)" },
  { key: "formatting_rules", label: "Formatting rules (one per line)" },
  { key: "banned_phrases", label: "Banned phrases (one per line)" },
  { key: "required_phrases", label: "Required phrases (one per line)" },
  { key: "verified_facts", label: "Verified facts — content must use these, never contradict (one per line)" },
  { key: "good_examples", label: "Approved examples (paste excerpts that define good output)" },
  { key: "bad_examples", label: "Rejected examples (paste excerpts to never imitate)" },
] as const;

function VersionHistory({ websiteId, currentVersion, onRollback }: { websiteId: string; currentVersion: number | null; onRollback: () => void }) {
  const [versions, setVersions] = useState<any[]>([]);
  const [rollingBack, setRollingBack] = useState<number | null>(null);

  useEffect(() => {
    if (!websiteId) return;
    get(`/api/brand-voice/${websiteId}/history`)
      .then((res) => setVersions(res?.versions || []))
      .catch(() => setVersions([]));
  }, [websiteId, currentVersion]);

  const handleRollback = async (version: number) => {
    if (!window.confirm(`Restore version ${version} as a new version? History is append-only — nothing is deleted.`)) return;
    setRollingBack(version);
    try {
      const res = await post("/api/brand-voice/rollback", { website_id: websiteId, version });
      onRollback();
      setVersions((prev) => [{ id: res?.guide?.id, version: res?.guide?.version, tone: res?.guide?.tone, updated_at: new Date().toISOString() }, ...prev]);
    } catch (e: any) {
      alert(`Rollback failed: ${e.message}`);
    } finally {
      setRollingBack(null);
    }
  };

  if (versions.length === 0) return null;

  return (
    <div className="panel" style={{ marginBottom: "24px" }}>
      <div className="panel-head"><span className="panel-label">Version history (append-only)</span></div>
      <div className="panel-body" style={{ padding: "0" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "11.5px" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--line)", color: "var(--muted)", textTransform: "uppercase", fontSize: "10px" }}>
              <th style={{ padding: "8px 14px", textAlign: "left" }}>Version</th>
              <th style={{ padding: "8px 14px", textAlign: "left" }}>Tone</th>
              <th style={{ padding: "8px 14px", textAlign: "left" }}>Saved</th>
              <th style={{ padding: "8px 14px", textAlign: "right" }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {versions.map((v: any) => (
              <tr key={v.id || v.version} style={{ borderBottom: "1px solid var(--line)" }}>
                <td style={{ padding: "8px 14px", fontWeight: 700 }}>
                  v{v.version}{v.version === currentVersion ? " (current)" : ""}
                </td>
                <td style={{ padding: "8px 14px", color: "var(--muted)", maxWidth: "320px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {v.tone || "—"}
                </td>
                <td style={{ padding: "8px 14px", color: "var(--muted)" }}>
                  {v.updated_at ? new Date(v.updated_at).toLocaleString() : "—"}
                </td>
                <td style={{ padding: "8px 14px", textAlign: "right" }}>
                  {v.version !== currentVersion ? (
                    <button className="btn" style={{ fontSize: "10.5px", padding: "3px 10px" }} disabled={rollingBack === v.version} onClick={() => handleRollback(v.version)}>
                      {rollingBack === v.version ? "Restoring…" : "Rollback to here"}
                    </button>
                  ) : (
                    <span style={{ fontSize: "10.5px", color: "var(--muted)" }}>active</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function BrandVoicePage() {
  const [websiteId, setWebsiteId] = useState<string>("");
  const [guide, setGuide] = useState<any | null>(null);
  const [tone, setTone] = useState("");
  const [lists, setLists] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    if (!wid) {
      setLoading(false);
      return;
    }
    setWebsiteId(wid);
    try {
      const res = await get(`/api/brand-voice/${wid}`);
      const g = res?.guide || null;
      setGuide(g);
      if (g && !g.is_default) {
        setTone(g.tone || "");
        const next: Record<string, string> = {};
        for (const f of LIST_FIELDS) {
          next[f.key] = Array.isArray(g[f.key]) ? g[f.key].join("\n") : "";
        }
        setLists(next);
      }
    } catch {
      setGuide(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    window.addEventListener("website-changed", load);
    return () => window.removeEventListener("website-changed", load);
  }, [load]);

  const [testDraft, setTestDraft] = useState("");
  const [lintReport, setLintReport] = useState<any | null>(null);

  const splitLines = (s: string) =>
    (s || "").split("\n").map((l) => l.trim()).filter(Boolean);

  const handleRunLint = () => {
    if (!testDraft.trim()) return;
    const lower = testDraft.toLowerCase();

    // 1. Check banned phrases
    const banned = splitLines(lists["banned_phrases"] || "");
    const bannedMatches = banned.filter((b) => b && lower.includes(b.toLowerCase()));

    // 2. Check required phrases
    const required = splitLines(lists["required_phrases"] || "");
    const requiredMissing = required.filter((r) => r && !lower.includes(r.toLowerCase()));

    // 3. Check generic anchors
    const badAnchors = ["click here", "read more", "this link", "here", "learn more"];
    const anchorGeneric = badAnchors.some((a) => lower.includes(`>${a}<`) || lower.includes(`"${a}"`));

    // 4. Check disclaimer
    const disclaimerFound = /disclaimer|not legal advice|informational purposes only|consult an attorney/i.test(testDraft);

    let score = 100;
    if (bannedMatches.length > 0) score -= bannedMatches.length * 15;
    if (requiredMissing.length > 0) score -= requiredMissing.length * 10;
    if (anchorGeneric) score -= 15;
    if (!disclaimerFound) score -= 10;
    score = Math.max(0, score);

    setLintReport({
      bannedMatches,
      requiredMissing,
      anchorGeneric,
      disclaimerFound,
      score,
      passed: score >= 80 && bannedMatches.length === 0,
    });
  };

  const handleSave = async () => {
    if (!websiteId) {
      setMsg("Select a website first.");
      return;
    }
    setSaving(true);
    setMsg(null);
    try {
      const payload: any = { website_id: websiteId, tone: tone.trim() || undefined };
      for (const f of LIST_FIELDS) {
        const lines = splitLines(lists[f.key] || "");
        if (lines.length > 0) payload[f.key] = lines;
      }
      const res = await post("/api/brand-voice", payload);
      setGuide(res?.guide || null);
      setMsg(`Saved as version ${res?.guide?.version ?? "?"}. Writers load this guide before every draft.`);
    } catch (e: any) {
      setMsg(`Save failed: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="page-container active"><div className="page-heading">Brand Voice</div></div>;
  }

  if (!websiteId) {
    return (
      <div className="page-container active">
        <div className="page-heading">Brand Voice</div>
        <div className="page-sub">Select a website first — guides are per site.</div>
      </div>
    );
  }

  return (
    <div className="page-container active">
      <div className="page-heading">Brand Voice</div>
      <div className="page-sub">
        Versioned writing contract for this site.{" "}
        {guide && !guide.is_default ? (
          <span>Current version: <strong>v{guide.version}</strong></span>
        ) : (
          <span style={{ color: "var(--amber)" }}>No guide saved yet — writers use explicit defaults.</span>
        )}
      </div>

      {msg && (
        <div className="panel" style={{ marginBottom: "16px", padding: "10px 14px", fontSize: "11px" }}>
          {msg}
        </div>
      )}

      <div className="panel" style={{ marginBottom: "16px" }}>
        <div className="panel-head"><span className="panel-label">Tone</span></div>
        <div className="panel-body" style={{ padding: "12px 16px" }}>
          <textarea
            value={tone}
            onChange={(e) => setTone(e.target.value)}
            placeholder="e.g. Empathetic but precise. Short sentences. No legalese without plain-English translation."
            rows={3}
            style={{ width: "100%", padding: "8px", fontSize: "12px", background: "var(--surface)", border: "1px solid var(--line)", color: "var(--ink)" }}
          />
        </div>
      </div>

      {LIST_FIELDS.map((f) => (
        <div className="panel" key={f.key} style={{ marginBottom: "16px" }}>
          <div className="panel-head"><span className="panel-label">{f.label}</span></div>
          <div className="panel-body" style={{ padding: "12px 16px" }}>
            <textarea
              value={lists[f.key] || ""}
              onChange={(e) => setLists((prev) => ({ ...prev, [f.key]: e.target.value }))}
              rows={f.key.includes("examples") ? 5 : 3}
              style={{ width: "100%", padding: "8px", fontSize: "12px", background: "var(--surface)", border: "1px solid var(--line)", color: "var(--ink)", fontFamily: "monospace" }}
            />
          </div>
        </div>
      ))}

      <button onClick={handleSave} disabled={saving} className="btn btn-accent" style={{ width: "100%", padding: "10px", fontWeight: 600, fontSize: "12px" }}>
        {saving ? "Saving…" : "Save as new version"}
      </button>
      <div style={{ fontSize: "10px", color: "var(--muted)", marginTop: "8px", textAlign: "center", marginBottom: "24px" }}>
        Every save creates a new version — history is preserved, never overwritten.
      </div>

      <VersionHistory websiteId={websiteId} currentVersion={guide && !guide.is_default ? guide.version : null} onRollback={load} />

      {/* INTERACTIVE BRAND VOICE LINTER & QUALITY SANDBOX */}
      <div className="panel" style={{ marginTop: "24px", borderColor: "var(--accent)" }}>
        <div className="panel-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span className="panel-label">⚡ Live Brand Voice Quality Sandbox & Linter</span>
          <span style={{ fontSize: "10px", color: "var(--muted)" }}>Instant Rule Compliance Verification</span>
        </div>
        <div className="panel-body" style={{ padding: "16px" }}>
          <div style={{ fontSize: "11px", color: "var(--muted)", marginBottom: "8px" }}>
            Paste any draft text, outline, or paragraph below to test against the active banned phrases, required terminology, and disclaimer rules.
          </div>
          <textarea
            value={testDraft}
            onChange={(e) => setTestDraft(e.target.value)}
            placeholder="Paste article draft or paragraph to test against your brand rules..."
            rows={4}
            style={{ width: "100%", padding: "10px", fontSize: "12px", background: "var(--surface)", border: "1px solid var(--line)", color: "var(--ink)", fontFamily: "monospace", marginBottom: "10px" }}
          />
          <button
            onClick={handleRunLint}
            disabled={!testDraft.trim()}
            className="btn btn-secondary"
            style={{ padding: "6px 14px", fontSize: "11px", fontWeight: 600, marginBottom: "14px" }}
          >
            ⚡ Test Draft Against Active Guide
          </button>

          {lintReport && (
            <div style={{ padding: "14px", background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "4px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                <span style={{ fontSize: "12px", fontWeight: 700 }}>
                  Compliance Score: <span style={{ color: lintReport.score >= 80 ? "var(--green)" : "var(--amber)" }}>{lintReport.score}/100</span>
                </span>
                <span className={`badge ${lintReport.passed ? "badge-green" : "badge-amber"}`} style={{ fontSize: "10px" }}>
                  {lintReport.passed ? "✓ Brand Voice Compliant" : "⚠️ Rule Violations Detected"}
                </span>
              </div>

              <div style={{ display: "grid", gap: "8px", fontSize: "11px" }}>
                {/* BANNED PHRASES */}
                <div>
                  <strong>Banned Phrases: </strong>
                  {lintReport.bannedMatches.length === 0 ? (
                    <span style={{ color: "var(--green)" }}>None detected (Clean)</span>
                  ) : (
                    <span style={{ color: "var(--red)" }}>
                      Found {lintReport.bannedMatches.length} banned phrase(s): {lintReport.bannedMatches.map((b: string) => `"${b}"`).join(", ")}
                    </span>
                  )}
                </div>

                {/* REQUIRED PHRASES */}
                <div>
                  <strong>Required Phrases: </strong>
                  {lintReport.requiredMissing.length === 0 ? (
                    <span style={{ color: "var(--green)" }}>All required terms present</span>
                  ) : (
                    <span style={{ color: "var(--amber)" }}>
                      Missing {lintReport.requiredMissing.length} required term(s): {lintReport.requiredMissing.map((m: string) => `"${m}"`).join(", ")}
                    </span>
                  )}
                </div>

                {/* ANCHOR QUALITY */}
                <div>
                  <strong>Anchor Quality: </strong>
                  {lintReport.anchorGeneric ? (
                    <span style={{ color: "var(--red)" }}>Generic anchor text detected ("click here", "read more"). Use descriptive semantic anchors.</span>
                  ) : (
                    <span style={{ color: "var(--green)" }}>No generic anchors</span>
                  )}
                </div>

                {/* DISCLAIMER CHECK */}
                <div>
                  <strong>Mandatory Disclaimer: </strong>
                  {lintReport.disclaimerFound ? (
                    <span style={{ color: "var(--green)" }}>✓ Present</span>
                  ) : (
                    <span style={{ color: "var(--muted)" }}>Not detected in sample</span>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
