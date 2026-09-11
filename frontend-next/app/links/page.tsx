"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface GraphNode {
  url: string;
  title: string;
  pagerank?: number;
  in_degree?: number;
  is_orphan?: boolean;
}

interface GraphEdge {
  from: string;
  to: string;
  anchor: string;
}

interface LinkSuggestion {
  target_title: string;
  target_url: string;
  recommended_anchor: string;
  relevance_score: number | null;
  relevance_note?: string;
}

export default function LinksPage() {
  const [websiteId, setWebsiteId] = useState<string>("");
  const [graph, setGraph] = useState<{ nodes: GraphNode[]; edges: GraphEdge[]; orphans: string[] }>({ nodes: [], edges: [], orphans: [] });
  const [suggestions, setSuggestions] = useState<LinkSuggestion[]>([]);
  const [indexationGate, setIndexationGate] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [runningJob, setRunningJob] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  const loadLinksData = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);
    if (!wid) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const [linksRes, sugRes, gateRes] = await Promise.allSettled([
        get(`/api/links/${wid}/graph`),
        get(`/api/links/${wid}/suggestions`),
        get(`/api/indexation/${wid}/gate`),
      ]);

      if (linksRes.status === "fulfilled" && linksRes.value) {
        const g = linksRes.value.graph || linksRes.value;
        setGraph({
          nodes: g.nodes || [],
          edges: g.edges || [],
          orphans: g.orphan_pages || g.orphans || [],
        });
      } else {
        setGraph({ nodes: [], edges: [], orphans: [] });
      }

      if (sugRes.status === "fulfilled" && sugRes.value) {
        setSuggestions(sugRes.value.suggestions || []);
      } else {
        setSuggestions([]);
      }

      if (gateRes.status === "fulfilled" && gateRes.value) {
        setIndexationGate(gateRes.value);
      } else {
        setIndexationGate(null);
      }
    } catch (e: any) {
      setError(e.message || "Failed to load link structure");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLinksData();
    const handleChanged = () => loadLinksData();
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [loadLinksData]);

  const handleRunLinkingJob = async () => {
    if (!websiteId) return;
    setRunningJob(true);
    try {
      const res = await post(`/api/workflows/${websiteId}/run`, { job_name: "internal_linking" });
      if (res?.success) {
        showToast("✓ Internal link graph updated and PageRank recomputed!");
        await loadLinksData();
      }
    } catch (e: any) {
      showToast(`Linking job failed: ${e.message}`);
    } finally {
      setRunningJob(false);
    }
  };

  if (loading && graph.nodes.length === 0) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px auto" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Computing PageRank & internal link graph...
        </p>
      </div>
    );
  }

  if (!websiteId) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">Internal & External Link Graph</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No data yet — add a website first.</strong> Connect your website to crawl internal link equity and orphan pages.
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

  const isIndexationBlocked = indexationGate?.gate === "blocked" || (indexationGate?.indexation_rate != null && indexationGate.indexation_rate < 0.8);

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      {toast && (
        <div
          style={{
            position: "fixed",
            bottom: "24px",
            right: "24px",
            background: "var(--ink)",
            color: "var(--bg)",
            padding: "10px 18px",
            borderRadius: "6px",
            fontSize: "12px",
            fontWeight: 600,
            boxShadow: "0 8px 24px rgba(0,0,0,0.2)",
            zIndex: 9999,
          }}
        >
          {toast}
        </div>
      )}

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px", marginBottom: "16px" }}>
        <div>
          <div className="page-heading">Internal Links & Equity Distribution</div>
          <div className="page-sub">
            <span className="sub-sq"></span>
            Internal PageRank · Orphan Page Detection · Anchor Text Equity & Gaps
          </div>
        </div>
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <button
            onClick={handleRunLinkingJob}
            disabled={runningJob}
            className="btn btn-accent"
            style={{ padding: "8px 18px", fontSize: "12px", fontWeight: 700 }}
          >
            {runningJob ? "⏳ Crawling Internal Links..." : "⚡ Optimize Internal Links"}
          </button>
        </div>
      </div>

      {error && (
        <div className="notice" style={{ marginBottom: 16, borderColor: "var(--red)", background: "rgba(255,85,85,0.08)" }}>
          <span className="notice-sq" style={{ background: "var(--red)" }}></span>
          <div style={{ color: "var(--red)" }}>{error}</div>
        </div>
      )}

      {/* INDEXATION GATE PRIORITY ALERT */}
      {isIndexationBlocked && (
        <div
          style={{
            padding: "14px 20px",
            background: "rgba(245, 158, 11, 0.08)",
            border: "1px solid var(--amber)",
            borderRadius: "4px",
            marginBottom: "20px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "12px",
          }}
        >
          <div>
            <div style={{ fontWeight: 700, fontSize: "13px", color: "var(--amber)", marginBottom: "4px" }}>
              ⚡ Priority Workflow: Site Indexation is Below 80% Safety Gate
            </div>
            <div style={{ fontSize: "12px", color: "var(--ink)", lineHeight: "1.5" }}>
              Publishing is paused to protect crawl budget. Prioritize funneling internal link equity from top authority pages to unindexed/orphan pages below to unblock autonomous publishing.
            </div>
          </div>
          <Link href="/indexation" className="btn btn-secondary" style={{ fontSize: "11px", padding: "6px 12px", textDecoration: "none" }}>
            View Indexation Center ↗
          </Link>
        </div>
      )}

      {/* KPI STRIP */}
      <div className="kpi-strip" style={{ marginBottom: "20px" }}>
        <div className="kpi-cell">
          <div className="kpi-label">Indexed Pages</div>
          <div className="kpi-val">{graph.nodes.length}</div>
          <div className="kpi-delta">Link equity nodes</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Internal Connections</div>
          <div className="kpi-val">{graph.edges.length}</div>
          <div className="kpi-delta">Active links mapped</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Orphan Pages</div>
          <div className="kpi-val" style={{ color: graph.orphans.length > 0 ? "var(--red)" : "var(--green)" }}>
            {graph.orphans.length}
          </div>
          <div className="kpi-delta">{graph.orphans.length > 0 ? "Require inbound links" : "Zero orphans detected"}</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Contextual Gaps</div>
          <div className="kpi-val">{suggestions.length}</div>
          <div className="kpi-delta">Link opportunities</div>
        </div>
      </div>

      <div className="dash-grid" style={{ marginBottom: "24px" }}>
        {/* INTERNAL PAGES TABLE */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">Internal Pages & Inbound Links ({graph.nodes.length})</span>
            <button className="panel-action" onClick={loadLinksData}>
              Refresh
            </button>
          </div>
          <div className="panel-body" style={{ padding: "0" }}>
            {graph.nodes.length === 0 ? (
              <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
                No internal link nodes found. Click <strong>Optimize Internal Links</strong> to crawl your sitemap and map internal link architecture.
              </div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "12px" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--line)", color: "var(--muted)", textTransform: "uppercase", fontSize: "10px" }}>
                    <th style={{ padding: "10px 14px" }}>Page URL</th>
                    <th style={{ padding: "10px 14px" }}>Inbound Links</th>
                    <th style={{ padding: "10px 14px" }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {graph.nodes.map((node, idx) => (
                    <tr key={idx} style={{ borderBottom: "1px solid var(--line)" }}>
                      <td style={{ padding: "10px 14px", fontWeight: 600, wordBreak: "break-all" }}>{node.url}</td>
                      <td style={{ padding: "10px 14px" }}>{node.in_degree ?? 0} links</td>
                      <td style={{ padding: "10px 14px" }}>
                        {node.is_orphan ? (
                          <span className="badge badge-red">Orphan</span>
                        ) : (
                          <span className="badge badge-green">Linked</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* ORPHAN PAGES */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">Orphan Pages Requiring Link Equity ({graph.orphans.length})</span>
          </div>
          <div className="panel-body">
            {graph.orphans.length === 0 ? (
              <div style={{ padding: "20px", textAlign: "center", color: "var(--green)", fontSize: "12px" }}>
                ✓ No orphan pages detected! Internal link architecture is healthy.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {graph.orphans.map((url, idx) => (
                  <div key={idx} style={{ padding: "10px", border: "1px solid var(--red)", background: "rgba(239, 68, 68, 0.05)", fontSize: "12px" }}>
                    <span style={{ fontWeight: 600, color: "var(--red)" }}>⚠ 0 Inbound Links:</span> {url}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* CONTEXTUAL LINKING SUGGESTIONS */}
      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Contextual Internal Link Suggestions ({suggestions.length})</span>
          <span style={{ fontSize: "11px", color: "var(--muted)" }}>Semantic Anchor Matching · Relevance Overlap</span>
        </div>
        <div className="panel-body" style={{ padding: 0 }}>
          {suggestions.length === 0 ? (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              No contextual link suggestions computed yet. Create articles or run internal linking workflow.
            </div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--line)", color: "var(--muted)", textTransform: "uppercase", fontSize: "10px" }}>
                  <th style={{ padding: "10px 14px", textAlign: "left" }}>Target Content</th>
                  <th style={{ padding: "10px 14px", textAlign: "left" }}>Target URL</th>
                  <th style={{ padding: "10px 14px", textAlign: "left" }}>Recommended Anchor</th>
                  <th style={{ padding: "10px 14px", textAlign: "left" }}>Relevance</th>
                </tr>
              </thead>
              <tbody>
                {suggestions.map((s, idx) => (
                  <tr key={idx} style={{ borderBottom: "1px solid var(--line)" }}>
                    <td style={{ padding: "10px 14px", fontWeight: 600 }}>{s.target_title || "Untitled"}</td>
                    <td style={{ padding: "10px 14px", color: "var(--muted)", wordBreak: "break-all" }}>{s.target_url}</td>
                    <td style={{ padding: "10px 14px" }}>
                      <span className="badge badge-accent">{s.recommended_anchor}</span>
                    </td>
                    <td style={{ padding: "10px 14px" }}>
                      {s.relevance_score != null ? (
                        <span className="badge badge-green">{(s.relevance_score * 100).toFixed(0)}% Match</span>
                      ) : (
                        <span style={{ color: "var(--muted)", fontSize: "11px" }}>{s.relevance_note || "—"}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
