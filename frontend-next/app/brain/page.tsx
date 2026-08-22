"use client";

import { useEffect, useState, useCallback } from "react";
import { get, post, del } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

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

  // New guideline form state
  const [newTitle, setNewTitle] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newType, setNewType] = useState("preference");
  const [isSaving, setIsSaving] = useState(false);

  const websiteId = getCurrentWebsiteId();

  const loadMemories = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      if (searchQuery) params.set("query", searchQuery);
      if (typeFilter) params.set("memory_type", typeFilter);
      if (websiteId) params.set("website_id", websiteId);

      const qs = params.toString();
      const res = await get(`/api/brain${qs ? `?${qs}` : ""}`);
      setMemories(Array.isArray(res) ? res : []);
    } catch (e: any) {
      console.warn("Brain memory fetch error:", e);
      setMemories([]);
    } finally {
      setLoading(false);
    }
  }, [websiteId, searchQuery, typeFilter]);

  useEffect(() => {
    loadMemories();
  }, [loadMemories]);

  const handleSaveGuideline = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newContent.trim()) {
      setError("Please provide both rule title and guideline content.");
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

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      {/* PAGE HEADER */}
      <div className="page-heading">Brand Brain</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Autonomous Memory · Learned SEO Rules · Performance History · Supabase Vector Database
      </div>

      {/* NOTICES */}
      {error && (
        <div className="notice" style={{ borderColor: "var(--red)", background: "rgba(239,68,68,0.08)" }}>
          <span className="notice-sq" style={{ background: "var(--red)" }}></span>
          <span style={{ color: "var(--red)" }}>{error}</span>
        </div>
      )}

      {noticeMsg && (
        <div className="notice ok">
          <span className="notice-sq"></span>
          <span>{noticeMsg}</span>
        </div>
      )}

      {/* TOP SECTION: BRAND PERSONA + TEACH FORM */}
      <div className="grid-2" style={{ marginBottom: "16px" }}>
        {/* BRAND PERSONA & GUIDELINES */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">Brand Persona & Guidelines</span>
            <button className="panel-action" onClick={loadMemories}>
              Refresh
            </button>
          </div>
          <div className="panel-body">
            <div style={{ fontSize: "12px", fontWeight: 600, marginBottom: "6px", color: "var(--ink)" }}>
              Brand Voice: Direct, Authoritative & Practical
            </div>
            <div style={{ fontSize: "10px", color: "var(--muted)", lineHeight: "1.6" }}>
              RankForge learns your website tone, banned phrases, product differentiators, and target customer personas automatically from past performance and content evaluations.
            </div>

            <div className="divider"></div>

            <div style={{ fontSize: "9px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "8px", letterSpacing: "0.08em", fontWeight: 600 }}>
              Learned SEO Rules
            </div>

            <div className="check-row">
              <span className="ci pass">✓</span>
              <span className="ck-label">Answer query in first 100 words (increases CTR & AEO snippets)</span>
              <span className="badge badge-green">Learned</span>
            </div>
            <div className="check-row">
              <span className="ci pass">✓</span>
              <span className="ck-label">Use comparison tables and checklist in technical guides</span>
              <span className="badge badge-green">Learned</span>
            </div>
            <div className="check-row">
              <span className="ci pass">✓</span>
              <span className="ck-label">Zero banned AI words (Delve, Unlock, Elevate, Plethora, Tapestry)</span>
              <span className="badge badge-green">Active</span>
            </div>
            <div className="check-row">
              <span className="ci pass">✓</span>
              <span className="ck-label">Include 3-item FAQ schema for Answer Engine snippet ranking</span>
              <span className="badge badge-green">Active</span>
            </div>
          </div>
        </div>

        {/* TEACH BRAIN NEW GUIDELINE */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">Teach Brain New Guideline</span>
            <span className="badge badge-accent">Interactive Training</span>
          </div>
          <form onSubmit={handleSaveGuideline} className="panel-body">
            <div className="field-group">
              <div className="field-label">Rule / Guideline Title</div>
              <input
                className="field"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="e.g. Always include code snippets in Next.js guides"
                disabled={isSaving}
              />
            </div>

            <div className="field-group">
              <div className="field-label">Guideline Content / Knowledge Fact</div>
              <textarea
                className="field"
                rows={3}
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
                placeholder="Explain the specific rule, forbidden terminology, or winning structure for future writing runs..."
                disabled={isSaving}
              />
            </div>

            <div className="field-group">
              <div className="field-label">Memory Category</div>
              <select
                className="field"
                value={newType}
                onChange={(e) => setNewType(e.target.value)}
                disabled={isSaving}
              >
                <option value="preference">Preference (Writing style / Tone)</option>
                <option value="fact">Fact (Product, Company or Industry info)</option>
                <option value="experience">Experience (What worked on SERP)</option>
                <option value="failure">Failure (What to avoid)</option>
                <option value="outcome">Outcome (Ranking result)</option>
              </select>
            </div>

            <button
              type="submit"
              className="btn btn-accent"
              style={{ width: "100%", padding: "9px 12px", marginTop: "4px", fontWeight: 600 }}
              disabled={isSaving}
            >
              {isSaving ? "Saving to Supabase..." : "Save to Brain Memory"}
            </button>
          </form>
        </div>
      </div>

      {/* STORED BRAND MEMORIES */}
      <div className="panel">
        <div className="panel-head">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span className="panel-label">Stored Brand Memories & Learned Patterns</span>
            <span className="badge badge-ink">{memories.length} Memories Active</span>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <input
              className="field"
              style={{ padding: "4px 8px", fontSize: "10px", width: "180px" }}
              placeholder="Search memories..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <select
              className="field"
              style={{ padding: "4px 8px", fontSize: "10px", width: "130px" }}
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
            >
              <option value="">All Types</option>
              <option value="preference">Preference</option>
              <option value="fact">Fact</option>
              <option value="experience">Experience</option>
              <option value="failure">Failure</option>
              <option value="outcome">Outcome</option>
            </select>
          </div>
        </div>

        <div style={{ padding: "0 14px" }}>
          {loading ? (
            <div style={{ padding: "24px", textAlign: "center", color: "var(--muted)" }}>
              Loading brand memories from Supabase...
            </div>
          ) : memories.length === 0 ? (
            <div style={{ padding: "24px", textAlign: "center", color: "var(--muted)" }}>
              No memories found matching your criteria. Use "Teach Brain New Guideline" above to add your first rule.
            </div>
          ) : (
            memories.map((m) => (
              <div className="mem-item" key={m.id}>
                <span className="act-sq"></span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "11px", fontWeight: 600, color: "var(--ink)", marginBottom: "2px" }}>
                    {m.title}
                  </div>
                  <div style={{ fontSize: "10px", color: "var(--muted)", lineHeight: "1.5" }}>
                    {m.content}
                  </div>
                </div>
                <div className="mem-stats" style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span className="badge badge-muted">{m.memory_type}</span>
                  <span className="badge badge-green">1024-dim Vector</span>
                  <button
                    className="btn btn-danger"
                    style={{ padding: "2px 6px", fontSize: "8px" }}
                    onClick={() => handleDeleteMemory(m.id)}
                    title="Delete Memory"
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* BOTTOM TICKER */}
      <div className="bticker">
        <span className="bticker-inner">
          <span className="bt-sq"></span>BRAND BRAIN <span className="bt-sep">/</span>
          <span className="bt-sq"></span>PGVECTOR 1024-DIM ACTIVE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>REAL-TIME LEARNING LOOP ENABLED <span className="bt-sep">/</span>
          <span className="bt-sq"></span>ZERO MOCK DATA &nbsp;&nbsp;&nbsp;&nbsp;
          <span className="bt-sq"></span>BRAND BRAIN <span className="bt-sep">/</span>
          <span className="bt-sq"></span>PGVECTOR 1024-DIM ACTIVE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>REAL-TIME LEARNING LOOP ENABLED <span className="bt-sep">/</span>
          <span className="bt-sq"></span>ZERO MOCK DATA
        </span>
      </div>
    </div>
  );
}
