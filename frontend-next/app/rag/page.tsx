"use client";

import { useEffect, useState, useCallback } from "react";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

export default function RAGIntelligencePage() {
  const [websiteId, setWebsiteId] = useState<string>("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    const wid = getCurrentWebsiteId() || websiteId || "default";

    try {
      setIsSearching(true);
      showToast("Searching pgvector knowledge base via NVIDIA embeddings...");
      const res = await post("/api/knowledge/search", {
        website_id: wid,
        query: query.trim(),
        limit: 6,
      });

      const list = Array.isArray(res) ? res : res?.results || [];
      setResults(list);
      showToast(`✓ Retrieved ${list.length} grounding context chunks!`);
    } catch (err: any) {
      showToast(`RAG search notice: ${err.message}`);
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
      <div className="page-heading">RAG & Grounding Intelligence</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Retrieval-Augmented Generation · 1024-Dimension Dense Vectors · pgvector Cosine Search
      </div>

      {/* SEARCH TESTER */}
      <div className="panel" style={{ marginBottom: "20px" }}>
        <div className="panel-head">
          <span className="panel-label">🔍 Live Semantic Context Retrieval</span>
          <span className="badge badge-accent">nv-embedqa-e5-v5</span>
        </div>
        <div className="panel-body">
          <form onSubmit={handleSearch}>
            <label style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", display: "block", marginBottom: "4px" }}>
              Semantic Search Query
            </label>
            <div style={{ display: "flex", gap: "8px" }}>
              <input
                className="field"
                placeholder="e.g. Texas commercial vehicle liability and insurance minimums"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <button
                type="submit"
                className="btn btn-accent"
                disabled={isSearching || !query.trim()}
                style={{ whiteSpace: "nowrap", padding: "8px 18px", fontWeight: 600 }}
              >
                {isSearching ? "Searching..." : "⚡ Execute Vector RAG"}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* RETRIEVED CHUNKS GRID */}
      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Retrieved Grounding Documents ({results.length})</span>
        </div>
        <div className="panel-body">
          {results.length > 0 ? (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              {results.map((item, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: "12px",
                    border: "1px solid var(--border)",
                    background: "var(--panel-inner)",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                    <span style={{ fontWeight: 600, fontSize: "11px" }}>{item.title || "Grounding Chunk"}</span>
                    {item.similarity && (
                      <span className="badge badge-green">
                        {Math.round(item.similarity * 100)}% Match
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: "10.5px", color: "var(--muted)", lineHeight: "1.5" }}>
                    {item.content}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: "30px 0", color: "var(--muted)", fontSize: "11px" }}>
              Execute a search above to inspect real-time vector document retrieval.
            </div>
          )}
        </div>
      </div>

      {/* BOTTOM TICKER */}
      <div className="bticker">
        <span className="bticker-inner">
          <span className="bt-sq"></span>RAG INTELLIGENCE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>PGVECTOR 1024D <span className="bt-sep">/</span>
          <span className="bt-sq"></span>NVIDIA NV-EMBEDQA-E5-V5 <span className="bt-sep">/</span>
          <span className="bt-sq"></span>ZERO HALLUCINATION &nbsp;&nbsp;&nbsp;&nbsp;
          <span className="bt-sq"></span>RAG INTELLIGENCE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>PGVECTOR 1024D <span className="bt-sep">/</span>
          <span className="bt-sq"></span>NVIDIA NV-EMBEDQA-E5-V5 <span className="bt-sep">/</span>
          <span className="bt-sq"></span>ZERO HALLUCINATION
        </span>
      </div>
    </div>
  );
}
