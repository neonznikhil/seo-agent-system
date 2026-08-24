"use client";

import { useEffect, useState, useCallback } from "react";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface KnowledgeChunk {
  id: string;
  website_id?: string;
  source_type?: string;
  title?: string;
  content: string;
  created_at?: string;
  similarity?: number;
}

export default function KnowledgePage() {
  const [websiteId, setWebsiteId] = useState<string>("");
  const [chunks, setChunks] = useState<KnowledgeChunk[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  // Ingest Form
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState("statute");
  const [content, setContent] = useState("");
  const [isIngesting, setIsIngesting] = useState(false);

  // Search Test
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<KnowledgeChunk[] | null>(null);
  const [isSearching, setIsSearching] = useState(false);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  const loadKnowledgeChunks = useCallback(async () => {
    const wid = getCurrentWebsiteId() || "default";
    setWebsiteId(wid);
    try {
      setLoading(true);
      const res = await get(`/api/knowledge?website_id=${wid}`);
      const list = Array.isArray(res) ? res : res?.data || res?.chunks || [];
      setChunks(list);
    } catch {
      // Fallback
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadKnowledgeChunks();
  }, [loadKnowledgeChunks]);

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) {
      showToast("Please enter fact content to ingest");
      return;
    }
    const wid = getCurrentWebsiteId() || websiteId || "default";

    try {
      setIsIngesting(true);
      showToast("Ingesting & generating 1024d embedding via NVIDIA nv-embedqa-e5-v5...");

      await post("/api/knowledge/ingest", {
        website_id: wid,
        title: title.trim() || "Grounding Fact",
        source_type: sourceType,
        content: content.trim(),
      });

      showToast("✓ Fact ingested into Supabase pgvector knowledge base!");
      setTitle("");
      setContent("");
      loadKnowledgeChunks();
    } catch (err: any) {
      showToast(`Ingestion notice: ${err.message || "Saved"}`);
      loadKnowledgeChunks();
    } finally {
      setIsIngesting(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    const wid = getCurrentWebsiteId() || websiteId || "default";

    try {
      setIsSearching(true);
      const res = await post("/api/knowledge/search", {
        website_id: wid,
        query: searchQuery.trim(),
        limit: 5,
      });

      const list = Array.isArray(res) ? res : res?.results || [];
      setSearchResults(list);
      showToast(`✓ Retrieved ${list.length} semantically relevant knowledge chunks`);
    } catch (err: any) {
      showToast(`Search notice: ${err.message}`);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="page-container active">
      {toastMsg && (
        <div
          style={{
            position: "fixed",
            bottom: "24px",
            left: "50%",
            transform: "translateX(-50%)",
            background: "var(--ink)",
            color: "var(--bg)",
            padding: "10px 22px",
            fontSize: "10.5px",
            textTransform: "uppercase",
            letterSpacing: ".07em",
            zIndex: 9999,
            fontFamily: "'IBM Plex Mono', monospace",
            border: "1px solid var(--accent)",
            boxShadow: "0 4px 24px rgba(0,0,0,.4)",
          }}
        >
          {toastMsg}
        </div>
      )}

      {/* PAGE HEADER */}
      <div className="page-heading">Living Knowledge Base</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Multi-Source Fact Ingestion · pgvector Semantic Retrieval · Hallucination Defense
      </div>

      {/* INGEST & SEARCH TESTER */}
      <div className="grid-2" style={{ marginBottom: "20px" }}>
        {/* INGEST FORM */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">📥 Ingest Real Knowledge & Legal Facts</span>
            <span className="badge badge-accent">pgvector 1024d</span>
          </div>
          <div className="panel-body">
            <form onSubmit={handleIngest}>
              <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "10px", marginBottom: "10px" }}>
                <div>
                  <label style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", display: "block", marginBottom: "4px" }}>
                    Fact Title / Heading
                  </label>
                  <input
                    className="field"
                    placeholder="e.g. Texas Civ. Prac. & Rem. Code § 16.003"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                  />
                </div>
                <div>
                  <label style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", display: "block", marginBottom: "4px" }}>
                    Source Type
                  </label>
                  <select
                    className="field"
                    value={sourceType}
                    onChange={(e) => setSourceType(e.target.value)}
                    style={{ cursor: "pointer" }}
                  >
                    <option value="statute">Statute / Legal Code</option>
                    <option value="technical_paper">Technical Document</option>
                    <option value="product_doc">Company & Pricing Doc</option>
                    <option value="competitor_intel">Competitor Analysis</option>
                  </select>
                </div>
              </div>

              <div style={{ marginBottom: "12px" }}>
                <label style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", display: "block", marginBottom: "4px" }}>
                  Knowledge Content (Verifiable Ground Truth)
                </label>
                <textarea
                  className="field"
                  rows={4}
                  placeholder="Paste legal statute text, verified company statistics, or technical specifications..."
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  required
                />
              </div>

              <button
                type="submit"
                className="btn btn-accent"
                disabled={isIngesting || !content.trim()}
                style={{ width: "100%", padding: "9px", fontWeight: 600 }}
              >
                {isIngesting ? "⚡ Generating Embedding & Ingesting..." : "⚡ Ingest into Living Knowledge Base"}
              </button>
            </form>
          </div>
        </div>

        {/* SEMANTIC VECTOR SEARCH */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">🔍 Semantic Recall Query Tester</span>
            <span className="badge badge-green">Cosine Distance</span>
          </div>
          <div className="panel-body">
            <form onSubmit={handleSearch} style={{ marginBottom: "14px" }}>
              <label style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", display: "block", marginBottom: "4px" }}>
                Natural Language Semantic Query
              </label>
              <div style={{ display: "flex", gap: "8px" }}>
                <input
                  className="field"
                  placeholder="e.g. What is the statute of limitations for personal injury in Texas?"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isSearching || !searchQuery.trim()}
                  style={{ whiteSpace: "nowrap" }}
                >
                  {isSearching ? "Searching..." : "Search"}
                </button>
              </div>
            </form>

            <div>
              <div style={{ fontSize: "9.5px", textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", marginBottom: "6px" }}>
                Query Results ({searchResults ? searchResults.length : 0})
              </div>
              {searchResults && searchResults.length > 0 ? (
                searchResults.map((r, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: "8px 10px",
                      background: "var(--panel-inner)",
                      border: "1px solid var(--line)",
                      marginBottom: "6px",
                      fontSize: "11px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "3px" }}>
                      <span style={{ fontWeight: 600 }}>{r.title || "Knowledge Chunk"}</span>
                      {r.similarity && (
                        <span className="badge badge-green">
                          {Math.round(r.similarity * 100)}% Match
                        </span>
                      )}
                    </div>
                    <div style={{ color: "var(--muted)", fontSize: "10px", lineHeight: "1.4" }}>
                      {r.content}
                    </div>
                  </div>
                ))
              ) : (
                <div style={{ fontSize: "10.5px", color: "var(--muted)", padding: "16px 0", textAlign: "center" }}>
                  {searchResults ? "No vector matches found above 0.70 similarity." : "Enter a search query to test real-time vector retrieval."}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* KNOWLEDGE BASE INGESTED CHUNKS TABLE */}
      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Stored Grounding Facts & Knowledge Chunks</span>
          <button type="button" className="panel-action" onClick={loadKnowledgeChunks}>
            Refresh
          </button>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Title / Reference</th>
                <th>Source Type</th>
                <th>Content Snippet</th>
                <th>Embedding</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {chunks.length > 0 ? (
                chunks.map((item) => (
                  <tr key={item.id}>
                    <td style={{ fontWeight: 600, maxWidth: "200px" }}>{item.title || "Statutory Fact"}</td>
                    <td>
                      <span className="badge badge-ink">{item.source_type || "statute"}</span>
                    </td>
                    <td style={{ maxWidth: "340px", fontSize: "10.5px", color: "var(--muted)" }}>
                      {item.content?.slice(0, 120)}...
                    </td>
                    <td>
                      <span className="badge badge-green">1024d Dense</span>
                    </td>
                    <td style={{ fontSize: "9.5px", color: "var(--muted)" }}>
                      {item.created_at ? new Date(item.created_at).toLocaleDateString() : "Active"}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} style={{ textAlign: "center", padding: "28px", color: "var(--muted)" }}>
                    No knowledge chunks stored yet. Use the ingestion form above to store your first verified fact!
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* BOTTOM TICKER */}
      <div className="bticker">
        <span className="bticker-inner">
          <span className="bt-sq"></span>KNOWLEDGE BASE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>NVIDIA NV-EMBEDQA-E5-V5 <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SUPABASE PGVECTOR 1024D <span className="bt-sep">/</span>
          <span className="bt-sq"></span>LIVING EVOLUTION ACTIVE &nbsp;&nbsp;&nbsp;&nbsp;
          <span className="bt-sq"></span>KNOWLEDGE BASE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>NVIDIA NV-EMBEDQA-E5-V5 <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SUPABASE PGVECTOR 1024D <span className="bt-sep">/</span>
          <span className="bt-sq"></span>LIVING EVOLUTION ACTIVE
        </span>
      </div>
    </div>
  );
}
