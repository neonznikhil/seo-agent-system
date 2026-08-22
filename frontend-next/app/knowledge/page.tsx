"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
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
  const [websiteId, setWebsiteId] = useState<string>("");

  // Modal / Add state
  const [showAddModal, setShowAddModal] = useState(false);
  const [modalTitle, setModalTitle] = useState("");
  const [modalContent, setModalContent] = useState("");
  const [modalSource, setModalSource] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const loadKnowledge = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);
    if (!wid) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      if (searchQuery) params.set("q", searchQuery);
      params.set("website_id", wid);

      let res: any = null;
      try {
        res = await get(`/api/knowledge?${params.toString()}`);
      } catch {
        res = await get(`/api/knowledge?${params.toString()}`);
      }

      const list = Array.isArray(res) ? res : res?.items || res?.knowledge || [];
      setEntries(list);
    } catch (e: any) {
      console.warn("Knowledge fetch error:", e);
      setError(e.message || "Failed to load knowledge base items");
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, [searchQuery]);

  useEffect(() => {
    loadKnowledge();
    const handleChanged = () => loadKnowledge();
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [loadKnowledge]);

  const handleCreateKnowledge = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!modalTitle.trim() || !modalContent.trim()) {
      setError("Please fill in both title and content fields.");
      return;
    }
    if (!websiteId) {
      setError("Please select or add a website first.");
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

  if (loading && entries.length === 0) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px auto" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Indexing business knowledge base & crawled facts...
        </p>
      </div>
    );
  }

  if (!websiteId) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">Knowledge Base</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No data yet — add a website first.</strong> Connect your website to extract and store domain knowledge for autonomous writing.
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
      <div className="page-heading">Knowledge Base</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Verified Domain Facts · Business Knowledge Base · Hallucination Prevention
      </div>

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

      <div className="kpi-strip" style={{ marginBottom: "20px" }}>
        <div className="kpi-cell">
          <div className="kpi-label">Knowledge Items</div>
          <div className="kpi-val">{entries.length}</div>
          <div className="kpi-delta">Verified business facts</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Grounding Source</div>
          <div className="kpi-val" style={{ color: "var(--green)" }}>Supabase DB</div>
          <div className="kpi-delta">Vector indexed for NIM</div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span className="panel-label">Domain Knowledge & Fact Repository</span>
          <button className="btn btn-accent" onClick={() => setShowAddModal(!showAddModal)} style={{ padding: "4px 12px", fontSize: "11px" }}>
            {showAddModal ? "Cancel" : "+ Add Knowledge Item"}
          </button>
        </div>

        {showAddModal && (
          <div style={{ padding: "16px", borderBottom: "1px solid var(--line)", background: "var(--surface)" }}>
            <form onSubmit={handleCreateKnowledge} style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <input
                type="text"
                value={modalTitle}
                onChange={(e) => setModalTitle(e.target.value)}
                placeholder="Fact Title / Topic (e.g. Free Consultation Policy)"
                className="field"
                style={{ padding: "8px", background: "var(--paper)", color: "var(--ink)", border: "1px solid var(--line)" }}
                required
              />
              <textarea
                rows={3}
                value={modalContent}
                onChange={(e) => setModalContent(e.target.value)}
                placeholder="Detailed fact content to ground autonomous writer LLMs..."
                className="field"
                style={{ padding: "8px", background: "var(--paper)", color: "var(--ink)", border: "1px solid var(--line)" }}
                required
              />
              <input
                type="text"
                value={modalSource}
                onChange={(e) => setModalSource(e.target.value)}
                placeholder="Source (e.g. Website About Page, Legal Docs)"
                className="field"
                style={{ padding: "8px", background: "var(--paper)", color: "var(--ink)", border: "1px solid var(--line)" }}
              />
              <button type="submit" disabled={isSaving} className="btn btn-accent" style={{ padding: "8px 16px", alignSelf: "flex-end" }}>
                {isSaving ? "Saving..." : "Save Knowledge Asset"}
              </button>
            </form>
          </div>
        )}

        <div className="panel-body">
          {entries.length === 0 ? (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              No knowledge base entries recorded yet. Add business facts above to ground the AI writer.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {entries.map((item) => (
                <div key={item.id} style={{ padding: "12px", border: "1px solid var(--line)", background: "var(--surface)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: "13px" }}>{item.title}</div>
                      <p style={{ fontSize: "12px", color: "var(--ink)", marginTop: "4px", lineHeight: "1.5" }}>{item.content}</p>
                      {item.source && (
                        <span style={{ fontSize: "10px", color: "var(--muted)", marginTop: "4px", display: "inline-block" }}>
                          Source: {item.source}
                        </span>
                      )}
                    </div>
                    <button
                      onClick={() => handleDeleteItem(item.id)}
                      style={{ background: "transparent", border: "none", color: "var(--red)", cursor: "pointer" }}
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
  );
}
