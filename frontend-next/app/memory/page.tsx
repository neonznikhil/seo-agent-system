"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface MemoryItem {
  id: string;
  keyword: string;
  ctr?: string;
  impressions?: string;
  content?: string;
  created_at?: string;
}

export default function MemoryPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [memoryItems, setMemoryItems] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [websiteId, setWebsiteId] = useState<string>("");

  const fetchMemoryItems = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);
    if (!wid) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = await get(`/api/memory/${wid}`);
      if (data && data.knowledge_base) {
        const items: MemoryItem[] = data.knowledge_base.map((kb: any, index: number) => ({
          id: kb.id || `kb-${index}`,
          keyword: kb.title || kb.fact?.substring(0, 60) || `Knowledge Item ${index + 1}`,
          content: kb.fact || kb.content || "",
          ctr: kb.ctr ?? "0.0%",
          impressions: kb.impressions ?? "0",
          created_at: kb.created_at,
        }));
        setMemoryItems(items);
      } else if (Array.isArray(data)) {
        setMemoryItems(data);
      } else {
        setMemoryItems([]);
      }
    } catch (err: any) {
      // warn removed
      setError(err.message || "Failed to load memory data");
      setMemoryItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMemoryItems();
    const handleChanged = () => fetchMemoryItems();
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [fetchMemoryItems]);

  const handleSearch = async () => {
    if (!searchQuery.trim() || !websiteId) return;
    try {
      setLoading(true);
      const data = await get(`/api/knowledge/search?q=${encodeURIComponent(searchQuery)}&website_id=${websiteId}`);
      const items: MemoryItem[] = Array.isArray(data)
        ? data.map((kb: any, index: number) => ({
            id: kb.id || `kb-${index}`,
            keyword: kb.title || kb.fact?.substring(0, 60) || `Search Result ${index + 1}`,
            content: kb.fact || kb.content || "",
            ctr: kb.ctr ?? "0.0%",
            impressions: kb.impressions ?? "0",
          }))
        : [];
      setMemoryItems(items);
    } catch (e: any) {
      setError(e.message || "Search failed");
    } finally {
      setLoading(false);
    }
  };

  if (loading && memoryItems.length === 0) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px auto" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Retrieving episodic memory & learned facts...
        </p>
      </div>
    );
  }

  if (!websiteId) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">Episodic Memory</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No data yet — add a website first.</strong> Connect your website to view autonomous memory records and semantic patterns.
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
      <div className="page-heading">Episodic Memory Bank</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Grounding Facts · Semantic Context · Cross-Agent Memory Synchronization
        {error && (
          <span className="badge badge-amber" style={{ marginLeft: "12px" }}>
            {error}
          </span>
        )}
      </div>

      <div className="panel" style={{ marginBottom: "20px" }}>
        <div className="panel-head">
          <span className="panel-label">Query Memory Bank</span>
        </div>
        <div className="panel-body">
          <div style={{ display: "flex", gap: "10px" }}>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search facts and memories..."
              className="field"
              style={{ flex: 1, padding: "8px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
            />
            <button onClick={handleSearch} className="btn btn-accent" style={{ padding: "8px 16px" }}>
              Search Memory
            </button>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Stored Memory Facts ({memoryItems.length})</span>
          <button className="panel-action" onClick={fetchMemoryItems}>
            Refresh
          </button>
        </div>
        <div className="panel-body">
          {memoryItems.length === 0 ? (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              No memory facts stored yet. Add knowledge assets in Knowledge Base to populate episodic memory.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {memoryItems.map((item) => (
                <div key={item.id} style={{ padding: "12px", border: "1px solid var(--line)", background: "var(--surface)" }}>
                  <div style={{ fontWeight: 600, fontSize: "13px" }}>{item.keyword}</div>
                  {item.content && (
                    <div style={{ fontSize: "12px", color: "var(--muted)", marginTop: "4px" }}>{item.content}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
