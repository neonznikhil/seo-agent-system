"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface Cluster {
  id: string;
  name?: string;
  topic?: string;
  cluster_topic?: string;
  keywords: string[];
  search_volume?: number;
  avg_volume?: number;
  difficulty?: number;
  avg_difficulty?: number;
  intent?: string;
}

export default function ClustersPage() {
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [websiteId, setWebsiteId] = useState<string>("");

  const loadClusters = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);
    if (!wid) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = await get(`/api/clusters?website_id=${wid}`);
      const list = Array.isArray(data) ? data : data?.clusters || [];
      setClusters(list);
    } catch (e: any) {
      // warn removed
      setError(e.message || "Failed to load keyword clusters");
      setClusters([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadClusters();
    const handleChanged = () => loadClusters();
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [loadClusters]);

  if (loading && clusters.length === 0) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px auto" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Generating semantic keyword clusters & topic graphs...
        </p>
      </div>
    );
  }

  if (!websiteId) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">Keyword Clusters</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No data yet — add a website first.</strong> Connect your website to map keyword clusters and topic authority silos.
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
      <div className="page-heading">Semantic Keyword Clusters</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Topical Authority Silos · Semantic Keyword Grouping · Cannibalization Prevention
        {error && (
          <span className="badge badge-amber" style={{ marginLeft: "12px" }}>
            {error}
          </span>
        )}
      </div>

      <div className="kpi-strip" style={{ marginBottom: "20px" }}>
        <div className="kpi-cell">
          <div className="kpi-label">Identified Clusters</div>
          <div className="kpi-val">{clusters.length}</div>
          <div className="kpi-delta">Content silos mapped</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Total Clustered Keywords</div>
          <div className="kpi-val" style={{ color: "var(--accent)" }}>
            {clusters.reduce((acc, c) => acc + (Array.isArray(c.keywords) ? c.keywords.length : 1), 0)}
          </div>
          <div className="kpi-delta">Target query coverage</div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Topical Clusters Map</span>
          <button className="panel-action" onClick={loadClusters}>
            Refresh
          </button>
        </div>
        <div className="panel-body">
          {clusters.length === 0 ? (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              No keyword clusters computed yet. The system runs clustering automatically as keywords and content are discovered.
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "16px" }}>
              {clusters.map((cluster, i) => {
                const topic = cluster.name || cluster.topic || cluster.cluster_topic || `Cluster #${i + 1}`;
                const keywords = Array.isArray(cluster.keywords) ? cluster.keywords : [];
                return (
                  <div
                    key={cluster.id || i}
                    style={{ padding: "16px", border: "1px solid var(--line)", background: "var(--surface)" }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                      <span className="badge badge-accent">{cluster.intent || "Informational"}</span>
                      <span style={{ fontSize: "11px", color: "var(--muted)" }}>
                        {cluster.search_volume || cluster.avg_volume ? `${cluster.search_volume || cluster.avg_volume} vol` : ""}
                      </span>
                    </div>
                    <div style={{ fontWeight: 600, fontSize: "14px", marginBottom: "10px" }}>{topic}</div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                      {keywords.map((kw, kIdx) => (
                        <span
                          key={kIdx}
                          style={{
                            fontSize: "11px",
                            padding: "2px 8px",
                            background: "var(--line)",
                            borderRadius: "3px",
                            color: "var(--ink)",
                          }}
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                    <div style={{ marginTop: "14px" }}>
                      <Link
                        href={`/writer`}
                        className="btn btn-accent"
                        style={{ display: "block", textAlign: "center", textDecoration: "none", fontSize: "11px", padding: "6px" }}
                      >
                        ⚡ Write Pillar Content
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
