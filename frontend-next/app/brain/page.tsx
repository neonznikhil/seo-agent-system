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
      console.warn("Brain memory fetch error:", e);
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

      {/* BRAIN STATS */}
      <div className="kpi-strip" style={{ marginBottom: "20px" }}>
        <div className="kpi-cell">
          <div className="kpi-label">Active Memories</div>
          <div className="kpi-val">{memories.length}</div>
          <div className="kpi-delta">Learned winning patterns</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Average Confidence</div>
          <div className="kpi-val" style={{ color: "var(--green)" }}>
            {memories.length > 0 ? `${Math.round((memories.reduce((acc, m) => acc + (m.confidence || 0.9), 0) / memories.length) * 100)}%` : "N/A"}
          </div>
          <div className="kpi-delta">Knowledge validation</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">AI Engine</div>
          <div className="kpi-val" style={{ fontSize: "15px", paddingTop: "4px" }}>Llama-3.1-70B</div>
          <div className="kpi-delta">Vector embedded</div>
        </div>
      </div>

      <div className="dash-grid">
        {/* LEFT COLUMN: MEMORIES LIST */}
        <div>
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Learned Rules & Domain Guidelines</span>
              <button className="panel-action" onClick={loadMemories}>
                Refresh
              </button>
            </div>
            <div className="panel-body">
              {memories.length === 0 ? (
                <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
                  No brain memories recorded yet. Add your brand preferences and writing rules on the right.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {memories.map((m) => (
                    <div key={m.id} style={{ padding: "12px", border: "1px solid var(--line)", background: "var(--surface)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                        <div>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <span className="badge badge-accent">{m.memory_type}</span>
                            <span style={{ fontWeight: 600, fontSize: "13px" }}>{m.title}</span>
                          </div>
                          <p style={{ fontSize: "12px", color: "var(--ink)", marginTop: "6px", lineHeight: "1.5" }}>{m.content}</p>
                        </div>
                        <button
                          onClick={() => handleDeleteMemory(m.id)}
                          style={{ background: "transparent", border: "none", color: "var(--red)", cursor: "pointer", fontSize: "12px" }}
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: ADD GUIDELINE FORM */}
        <div>
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Teach Brain New Guideline / Pattern</span>
            </div>
            <div className="panel-body">
              <form onSubmit={handleSaveGuideline} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                    Guideline Type
                  </label>
                  <select
                    value={newType}
                    onChange={(e) => setNewType(e.target.value)}
                    className="field"
                    style={{ width: "100%", padding: "8px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
                  >
                    <option value="preference">Brand Voice & Style (Preference)</option>
                    <option value="fact">SEO Quality Rule & Facts (Fact)</option>
                    <option value="failure">Negative Pattern to Avoid (Failure)</option>
                    <option value="experience">Learned Best Practice (Experience)</option>
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
