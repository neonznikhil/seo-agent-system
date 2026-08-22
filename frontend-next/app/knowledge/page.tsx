"use client";

import { useEffect, useState, useCallback } from "react";
import { get, post, del } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface KnowledgeEntry {
  id: string;
  title: string;
  content: string;
  source?: string;
  created_at?: string;
}

export default function KnowledgePage() {
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [noticeMsg, setNoticeMsg] = useState<string | null>(null);

  // Modal / Add state
  const [showAddModal, setShowAddModal] = useState(false);
  const [modalTitle, setModalTitle] = useState("");
  const [modalContent, setModalContent] = useState("");
  const [modalSource, setModalSource] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const websiteId = getCurrentWebsiteId();

  const loadKnowledge = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      if (searchQuery) params.set("q", searchQuery);
      if (websiteId) params.set("website_id", websiteId);

      const qs = params.toString();
      const res = await get(`/api/knowledge${qs ? `?${qs}` : ""}`);
      setEntries(Array.isArray(res) ? res : []);
    } catch (e: any) {
      console.warn("Knowledge fetch error:", e);
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, [websiteId, searchQuery]);

  useEffect(() => {
    loadKnowledge();
  }, [loadKnowledge]);

  const handleCreateKnowledge = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!modalTitle.trim() || !modalContent.trim()) {
      setError("Please fill in both title and content fields.");
      return;
    }

    try {
      setIsSaving(true);
      setError(null);

      await post("/api/knowledge", {
        title: modalTitle.trim(),
        content: modalContent.trim(),
        source: modalSource.trim() || "Documentation / Team Best Practices",
        website_id: websiteId,
      });

      setModalTitle("");
      setModalContent("");
      setModalSource("");
      setShowAddModal(false);
      setNoticeMsg("✓ Successfully saved knowledge asset to Supabase!");
      loadKnowledge();
    } catch (err: any) {
      setError(`Failed to save knowledge item: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteItem = async (id: string) => {
    try {
      await del(`/api/knowledge/${id}`);
      setNoticeMsg("✓ Removed knowledge item from database.");
      setEntries((prev) => prev.filter((item) => item.id !== id));
    } catch (err: any) {
      setError(`Failed to delete item: ${err.message}`);
    }
  };

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      {/* PAGE HEADER */}
      <div className="page-heading">Knowledge Base</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Topical Authority Assets · Source Data · Domain Context · Supabase Knowledge Store
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

      {/* SEARCH AND ADD BAR */}
      <div style={{ display: "flex", gap: "10px", marginBottom: "16px" }}>
        <input
          className="field"
          style={{ flex: 1 }}
          placeholder="Search knowledge base articles, company facts, and guidelines..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        <button
          className="btn btn-accent"
          style={{ padding: "8px 16px", fontWeight: 600, whiteSpace: "nowrap" }}
          onClick={() => setShowAddModal(true)}
        >
          + Add Knowledge Item
        </button>
      </div>

      {/* KNOWLEDGE LIST PANEL */}
      <div className="panel">
        <div className="panel-head">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span className="panel-label">Knowledge Items in Database</span>
            <span className="badge badge-ink">{entries.length} items</span>
          </div>
          <button className="panel-action" onClick={loadKnowledge}>
            Refresh
          </button>
        </div>

        <div style={{ padding: "0 14px" }}>
          {loading ? (
            <div style={{ padding: "24px", textAlign: "center", color: "var(--muted)" }}>
              Loading knowledge base from Supabase...
            </div>
          ) : entries.length === 0 ? (
            <div style={{ padding: "32px", textAlign: "center", color: "var(--muted)" }}>
              {searchQuery
                ? `No knowledge entries found matching "${searchQuery}".`
                : "No knowledge base items stored yet. Click '+ Add Knowledge Item' above to seed your domain authority context."}
            </div>
          ) : (
            entries.map((item) => (
              <div
                key={item.id}
                style={{
                  padding: "12px 0",
                  borderBottom: "1px solid var(--line)",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: "16px",
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--ink)", marginBottom: "4px" }}>
                    {item.title}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--muted)", lineHeight: "1.6", whiteSpace: "pre-wrap" }}>
                    {item.content}
                  </div>
                  <div style={{ display: "flex", gap: "12px", marginTop: "6px", fontSize: "9px", color: "var(--muted)" }}>
                    <span><strong>Source:</strong> {item.source || "Manual Entry"}</span>
                    {item.created_at && (
                      <span><strong>Indexed:</strong> {new Date(item.created_at).toLocaleDateString()}</span>
                    )}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span className="badge badge-green">Synced</span>
                  <button
                    className="btn btn-danger"
                    style={{ padding: "2px 6px", fontSize: "8px" }}
                    onClick={() => handleDeleteItem(item.id)}
                    title="Delete knowledge item"
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* ADD KNOWLEDGE MODAL */}
      {showAddModal && (
        <div className="modal-backdrop active">
          <div className="modal-card">
            <div className="modal-head">
              <span className="modal-title">+ Add Knowledge Base Item</span>
              <button className="modal-close" onClick={() => setShowAddModal(false)}>
                ✕
              </button>
            </div>
            <form onSubmit={handleCreateKnowledge}>
              <div className="modal-body">
                <div className="notice info" style={{ marginBottom: "14px" }}>
                  <span className="notice-sq"></span>
                  Knowledge assets are ingested by writer agents during the Brain Recall phase to provide factually verified product details.
                </div>

                <div className="field-group">
                  <div className="field-label">Title / Subject</div>
                  <input
                    className="field"
                    value={modalTitle}
                    onChange={(e) => setModalTitle(e.target.value)}
                    placeholder="e.g. Next.js 14 Server Components SEO Architecture"
                    disabled={isSaving}
                  />
                </div>

                <div className="field-group">
                  <div className="field-label">Knowledge Content & Fact Details</div>
                  <textarea
                    className="field"
                    rows={5}
                    value={modalContent}
                    onChange={(e) => setModalContent(e.target.value)}
                    placeholder="Detailed insights, facts, product specifications, benchmarks, or domain best practices..."
                    disabled={isSaving}
                  />
                </div>

                <div className="field-group">
                  <div className="field-label">Source / Reference (Optional)</div>
                  <input
                    className="field"
                    value={modalSource}
                    onChange={(e) => setModalSource(e.target.value)}
                    placeholder="e.g. Official Documentation / Engineering Blog"
                    disabled={isSaving}
                  />
                </div>
              </div>

              <div className="modal-foot">
                <button
                  type="button"
                  className="btn"
                  onClick={() => setShowAddModal(false)}
                  disabled={isSaving}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-accent"
                  disabled={isSaving}
                  style={{ fontWeight: 600 }}
                >
                  {isSaving ? "Saving to Supabase..." : "Save to Knowledge Base →"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* BOTTOM TICKER */}
      <div className="bticker">
        <span className="bticker-inner">
          <span className="bt-sq"></span>KNOWLEDGE BASE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SUPABASE KNOWLEDGE STORE ACTIVE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>EMBEDDINGS READY <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SERP CONTEXT INGESTION &nbsp;&nbsp;&nbsp;&nbsp;
          <span className="bt-sq"></span>KNOWLEDGE BASE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SUPABASE KNOWLEDGE STORE ACTIVE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>EMBEDDINGS READY <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SERP CONTEXT INGESTION
        </span>
      </div>
    </div>
  );
}
