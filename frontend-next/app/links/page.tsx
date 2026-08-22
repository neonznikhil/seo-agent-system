"use client";

import { useEffect, useRef, useState, useCallback } from "react";
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

interface Prospect {
  id: string;
  prospect_url: string;
  domain_rating: number | null;
  strategy: string;
  target_keyword: string;
  status: string;
}

export default function LinksPage() {
  const [websiteId, setWebsiteId] = useState<string>("");
  const [graph, setGraph] = useState<{ nodes: GraphNode[]; edges: GraphEdge[]; orphans: string[] }>({ nodes: [], edges: [], orphans: [] });
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

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

      const [linksRes, backlinkRes] = await Promise.allSettled([
        get(`/api/links/${wid}/graph`),
        get(`/api/backlinks/${wid}`),
      ]);

      if (linksRes.status === "fulfilled" && linksRes.value) {
        setGraph({
          nodes: linksRes.value.nodes || [],
          edges: linksRes.value.edges || [],
          orphans: linksRes.value.orphans || [],
        });
      } else {
        setGraph({ nodes: [], edges: [], orphans: [] });
      }

      if (backlinkRes.status === "fulfilled" && backlinkRes.value) {
        setProspects(backlinkRes.value.prospects || []);
      } else {
        setProspects([]);
      }
    } catch (e: any) {
      console.warn("Links fetch error:", e);
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

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      <div className="page-heading">Internal Links & Equity Distribution</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Internal PageRank · Orphan Page Detection · Anchor Text Equity
        {error && (
          <span className="badge badge-amber" style={{ marginLeft: "12px" }}>
            {error}
          </span>
        )}
      </div>

      <div className="kpi-strip" style={{ marginBottom: "20px" }}>
        <div className="kpi-cell">
          <div className="kpi-label">Indexed Pages</div>
          <div className="kpi-val">{graph.nodes.length}</div>
          <div className="kpi-delta">Link equity nodes</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Internal Connections</div>
          <div className="kpi-val">{graph.edges.length}</div>
          <div className="kpi-delta">Active links</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Orphan Pages</div>
          <div className="kpi-val" style={{ color: graph.orphans.length > 0 ? "var(--red)" : "var(--green)" }}>
            {graph.orphans.length}
          </div>
          <div className="kpi-delta">{graph.orphans.length > 0 ? "Require internal links" : "Zero orphans"}</div>
        </div>
      </div>

      <div className="dash-grid">
        {/* INTERNAL LINKS TABLE */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">Internal Pages & Inbound Links</span>
            <button className="panel-action" onClick={loadLinksData}>
              Refresh
            </button>
          </div>
          <div className="panel-body" style={{ padding: "0" }}>
            {graph.nodes.length === 0 ? (
              <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
                No internal link nodes found. The system crawls your site to map internal link architecture.
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
                      <td style={{ padding: "10px 14px", fontWeight: 600 }}>{node.url}</td>
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

        {/* ORPHAN PAGES / PROSPECTS */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">Orphan Pages Requiring Link Equity</span>
          </div>
          <div className="panel-body">
            {graph.orphans.length === 0 ? (
              <div style={{ padding: "20px", textAlign: "center", color: "var(--green)", fontSize: "12px" }}>
                ✓ No orphan pages detected! Internal link architecture is well structured.
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
    </div>
  );
}
