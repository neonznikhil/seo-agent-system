"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post, del } from "@/lib/api";
import { getCurrentWebsiteId, getWebsiteId } from "@/lib/website";

interface BrainMemory {
  id: string;
  title: string;
  content: string;
  memory_type: string;
  confidence: number;
  times_used?: number;
  times_successful?: number;
  created_at?: string;
}

export default function BrainPage() {
  const [memories, setMemories] = useState<BrainMemory[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [noticeMsg, setNoticeMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [websiteId, setWebsiteId] = useState<string>("");

  // New guideline form state
  const [newTitle, setNewTitle] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newType, setNewType] = useState("preference");
  const [isSaving, setIsSaving] = useState(false);

  const loadMemories = useCallback(async () => {
    const wid = getCurrentWebsiteId() || getWebsiteId();
    setWebsiteId(wid);
    if (!wid) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      if (searchQuery) params.set("query", searchQuery);
      if (typeFilter) params.set("memory_type", typeFilter);
      params.set("website_id", wid);

      let res: any = null;
      try {
        res = await get(`/api/brain/${wid}/memory`);
      } catch {
        res = await get(`/api/brain?${params.toString()}`);
      }

      const list = Array.isArray(res) ? res : res?.memories || res?.data || [];
      setMemories(list);
    } catch (e: any) {
      // warn removed
      setError(e.message || "Failed to load brain memories");
      setMemories([]);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, typeFilter]);

  useEffect(() => {
    loadMemories();
    const handleChanged = () => loadMemories();
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [loadMemories]);

  const handleSaveGuideline = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newContent.trim()) {
      setError("Please provide both rule title and guideline content.");
      return;
    }
    if (!websiteId) {
      setError("Please select or add a website first.");
      return;
    }

    try {
      setIsSaving(true);
      setError(null);

      await post("/api/brain", {
        title: newTitle.trim(),
        content: newContent.trim(),
        memory_type: newType,
        website_id: websiteId,
        confidence: 0.95,
      });

      setNewTitle("");
      setNewContent("");
      setNoticeMsg("✓ Saved new guideline into Supabase brain_memory! Active for future autonomous writer runs.");
      loadMemories();
    } catch (err: any) {
      setError(`Failed to save guideline: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteMemory = async (id: string) => {
    try {
      await del(`/api/brain/${id}`);
      setNoticeMsg("✓ Removed memory from brain.");
      setMemories((prev) => prev.filter((m) => m.id !== id));
    } catch (err: any) {
      setError(`Failed to delete memory: ${err.message}`);
    }
  };

  if (loading && memories.length === 0) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px auto" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Recalling brand brain memories & learned SEO patterns...
        </p>
      </div>
    );
  }

  if (!websiteId) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">Brand Brain & Memory</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No data yet — add a website first.</strong> Connect your website to train the autonomous SEO brain on your brand guidelines and winning patterns.
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
      {/* PAGE HEADER */}
      <div className="page-heading">Brand Brain & Memory</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Self-Learning Knowledge Base · Continuous Pattern Recognition · Autonomous Recall
      </div>

      {/* NOTICES */}
      {error && (
        <div className="notice" style={{ borderColor: "var(--red)", background: "rgba(239,68,68,0.08)", marginBottom: "16px" }}>
          <span className="notice-sq" style={{ background: "var(--red)" }}></span>
          <span style={{ color: "var(--red)" }}>{error}</span>
        </div>
      )}

      {noticeMsg && (
        <div className="notice ok" style={{ marginBottom: "16px" }}>
          <span className="notice-sq"></span>
          <span>{noticeMsg}</span>
        </div>
      )}

      {/* BRAIN STATS & TOP SUMMARY CARD */}
      <div className="panel" style={{ marginBottom: "20px", borderLeft: "4px solid var(--accent)" }}>
        <div className="panel-head">
          <span className="panel-label">What the System Has Learned About This Website</span>
          <span className="badge badge-accent">Autonomous Memory Active</span>
        </div>
        <div className="panel-body" style={{ padding: "16px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 2fr", gap: "16px", marginBottom: "16px" }}>
            <div style={{ padding: "14px", background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "4px" }}>
              <div style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>Learned Memories</div>
              <div style={{ fontSize: "24px", fontWeight: 700, color: "var(--accent)", marginTop: "4px" }}>{memories.length}</div>
              <div style={{ fontSize: "11px", color: "var(--muted)", marginTop: "2px" }}>Persistent across agent runs</div>
            </div>
            <div style={{ padding: "14px", background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "4px" }}>
              <div style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>Average Confidence</div>
              <div style={{ fontSize: "24px", fontWeight: 700, color: "var(--green)", marginTop: "4px" }}>
                {memories.length > 0 ? `${Math.round((memories.reduce((acc, m) => acc + (m.confidence || 0.9), 0) / memories.length) * 100)}%` : "95%"}
              </div>
              <div style={{ fontSize: "11px", color: "var(--muted)", marginTop: "2px" }}>Quality-weighted recall</div>
            </div>
            <div style={{ padding: "14px", background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "4px" }}>
              <div style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase", marginBottom: "6px" }}>Top Recent Learnings</div>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                {memories.slice(0, 3).map((m, i) => (
                  <div key={i} style={{ fontSize: "11.5px", display: "flex", alignItems: "center", gap: "6px" }}>
                    <span className="badge badge-accent" style={{ fontSize: "9px", padding: "1px 5px" }}>{m.memory_type}</span>
                    <span style={{ color: "var(--ink)", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.title}</span>
                  </div>
                ))}
                {memories.length === 0 && <span style={{ fontSize: "11px", color: "var(--muted)" }}>Run an article generation to start training the brain.</span>}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* FILTER TABS */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "16px", flexWrap: "wrap" }}>
        {["all", "facts", "outcomes", "experience", "feedback"].map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter(t === "all" ? "" : t)}
            className={`btn ${(t === "all" && !typeFilter) || typeFilter === t ? "btn-accent" : ""}`}
            style={{ textTransform: "uppercase", padding: "6px 14px", fontSize: "11px" }}
          >
            {t} {t !== "all" ? `(${memories.filter((m) => m.memory_type?.toLowerCase().includes(t.slice(0, 4))).length})` : `(${memories.length})`}
          </button>
        ))}
      </div>

      {/* TWO COLUMN LAYOUT */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "20px" }}>
        {/* LEFT COLUMN: MEMORIES LIST */}
        <div>
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Memory Registry (Grouped by Type)</span>
              <button className="panel-action" onClick={loadMemories}>
                Refresh
              </button>
            </div>
            <div className="panel-body">
              {memories.length === 0 ? (
                <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
                  No brain memories recorded yet. Generate an article in /writer or add a custom rule on the right.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  {memories
                    .filter((m) => !typeFilter || m.memory_type?.toLowerCase().includes(typeFilter.slice(0, 4)))
                    .map((m) => {
                      const confPct = Math.round((m.confidence || 0.9) * 100);
                      return (
                        <div key={m.id} style={{ padding: "14px", border: "1px solid var(--line)", background: "var(--surface)", borderRadius: "4px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                            <div>
                              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                                <span className="badge badge-accent" style={{ textTransform: "uppercase", fontSize: "10px" }}>{m.memory_type}</span>
                                <span style={{ fontWeight: 600, fontSize: "13px" }}>{m.title}</span>
                              </div>
                              <p style={{ fontSize: "12px", color: "var(--ink)", marginTop: "6px", lineHeight: "1.5" }}>{m.content}</p>
                            </div>
                            <button
                              onClick={() => handleDeleteMemory(m.id)}
                              style={{ background: "transparent", border: "none", color: "var(--red)", cursor: "pointer", fontSize: "12px", padding: "4px" }}
                            >
                              ✕
                            </button>
                          </div>

                          {/* Confidence Bar & Date */}
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid var(--line)", paddingTop: "8px", marginTop: "8px" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "8px", flex: 1, maxWidth: "240px" }}>
                              <span style={{ fontSize: "10px", color: "var(--muted)" }}>Confidence:</span>
                              <div style={{ flex: 1, height: "6px", background: "rgba(255,255,255,0.08)", borderRadius: "3px", overflow: "hidden" }}>
                                <div style={{ width: `${confPct}%`, height: "100%", background: confPct >= 85 ? "var(--green)" : "var(--accent)" }} />
                              </div>
                              <span style={{ fontSize: "10px", fontWeight: 600, color: confPct >= 85 ? "var(--green)" : "var(--accent)" }}>{confPct}%</span>
                            </div>
                            <span style={{ fontSize: "10px", color: "var(--muted)" }}>
                              {m.created_at ? new Date(m.created_at).toLocaleDateString() : "Active"}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: ADD GUIDELINE FORM */}
        <div>
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Teach Brain New Rule / Pattern</span>
            </div>
            <div className="panel-body">
              <form onSubmit={handleSaveGuideline} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                    Memory Classification
                  </label>
                  <select
                    value={newType}
                    onChange={(e) => setNewType(e.target.value)}
                    className="field"
                    style={{ width: "100%", padding: "8px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
                  >
                    <option value="facts">Brand Voice & Knowledge (Facts)</option>
                    <option value="outcomes">Content Performance & SEO (Outcomes)</option>
                    <option value="experience">Workflow Patterns (Experience)</option>
                    <option value="feedback">Human Review Edits (Feedback)</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                    Rule Title
                  </label>
                  <input
                    type="text"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    placeholder="e.g. Always include Georgia statutory limits"
                    className="field"
                    style={{ width: "100%", padding: "8px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
                    required
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                    Guideline Description
                  </label>
                  <textarea
                    rows={4}
                    value={newContent}
                    onChange={(e) => setNewContent(e.target.value)}
                    placeholder="e.g. Every article discussing Georgia injury claims must mention O.C.G.A. § 9-3-33 for the 2-year statute of limitations."
                    className="field"
                    style={{ width: "100%", padding: "8px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
                    required
                  />
                </div>

                <button type="submit" disabled={isSaving} className="btn btn-accent" style={{ padding: "10px", width: "100%" }}>
                  {isSaving ? "Saving into Vector Brain..." : "+ Save to Brain Memory"}
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
