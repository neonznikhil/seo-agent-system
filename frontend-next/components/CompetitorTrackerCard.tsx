"use client";

import { useEffect, useState, useCallback } from "react";
import { get, post, del } from "@/lib/api";

interface Competitor {
  id: string;
  domain: string;
  label?: string;
  domain_authority: number;
  organic_keywords_count: number;
  est_monthly_visits: number;
}

interface SOVCompetitor {
  domain: string;
  label: string;
  sov_percentage: number;
  top_3_rankings: number;
  top_10_rankings: number;
  authority: number;
  trend: string;
}

interface ShareOfVoiceData {
  website_id: string;
  target_domain: string;
  our_sov_percentage: number;
  our_sov_trend: string;
  total_keywords_analyzed: number;
  market_leader: string;
  competitors: SOVCompetitor[];
  summary: string;
}

interface CompetitorNewPage {
  id: string;
  competitor_domain: string;
  title: string;
  url: string;
  published_date: string;
  target_topic: string;
  threat_level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  counter_strategy: string;
}

interface OutrankingQuery {
  keyword: string;
  search_volume: number;
  our_position: number;
  competitor_position: number;
  competitor_domain: string;
  competitor_url: string;
  our_url: string;
  monthly_clicks_lost: number;
  potential_mrr_loss: number;
  primary_gap_reason: string;
  recommended_action: string;
}

interface CompetitorTrackerCardProps {
  websiteId: string;
}

export function CompetitorTrackerCard({ websiteId }: CompetitorTrackerCardProps) {
  const [activeTab, setActiveTab] = useState<"sov" | "matrix" | "pages" | "manage">("sov");
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [sovData, setSovData] = useState<ShareOfVoiceData | null>(null);
  const [newPages, setNewPages] = useState<CompetitorNewPage[]>([]);
  const [outrankingMatrix, setOutrankingMatrix] = useState<OutrankingQuery[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add competitor form state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newDomain, setNewDomain] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchAllData = useCallback(async () => {
    if (!websiteId) return;
    setLoading(true);
    setError(null);
    try {
      // allSettled, not all: one 404 (e.g. new-pages) previously discarded the
      // three responses that DID load, blanking every panel in the card.
      const [compRes, sovRes, pagesRes, matrixRes] = await Promise.allSettled([
        get(`/api/competitors/${websiteId}`),
        get(`/api/competitors/${websiteId}/share-of-voice`),
        get(`/api/competitors/${websiteId}/new-pages`),
        get(`/api/competitors/${websiteId}/outranking-matrix`),
      ]);

      const val = <T,>(r: PromiseSettledResult<any>, fallback: T): T =>
        r.status === "fulfilled" ? r.value : fallback;

      setCompetitors(val<any>(compRes, {}).competitors || []);
      setSovData(val<any>(sovRes, null));
      setNewPages(val<any>(pagesRes, {}).new_pages || []);
      setOutrankingMatrix(val<any>(matrixRes, {}).outranked_queries || []);

      const failures = [compRes, sovRes, pagesRes, matrixRes].filter((r) => r.status === "rejected");
      if (failures.length === 4) {
        setError(
          (failures[0] as PromiseRejectedResult).reason?.message ||
            "Failed to load competitor intelligence data."
        );
      } else if (failures.length) {
        setError(`${failures.length} of 4 competitor panels could not be loaded. The rest is live data.`);
      }
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  const handleAddCompetitor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDomain.trim() || !websiteId) return;
    setSubmitting(true);
    try {
      await post(`/api/competitors/${websiteId}`, {
        domain: newDomain.trim(),
        label: newLabel.trim() || undefined,
      });
      setNewDomain("");
      setNewLabel("");
      setIsAddModalOpen(false);
      fetchAllData();
    } catch (err: any) {
      alert(`Failed to add competitor: ${err?.message || "Error"}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteCompetitor = async (competitorId: string, domainName: string) => {
    if (!confirm(`Stop tracking competitor "${domainName}"?`)) return;
    try {
      await del(`/api/competitors/${websiteId}/${competitorId}`);
      fetchAllData();
    } catch (err: any) {
      alert(`Failed to delete competitor: ${err?.message || "Error"}`);
    }
  };

  const totalClicksLost = outrankingMatrix.reduce((acc, q) => acc + q.monthly_clicks_lost, 0);
  const totalMrrLoss = outrankingMatrix.reduce((acc, q) => acc + q.potential_mrr_loss, 0);

  return (
    <div className="panel" style={{ marginBottom: "24px" }}>
      {/* Panel Header */}
      <div className="panel-head" style={{ flexWrap: "wrap", gap: "10px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "8px",
              background: "rgba(59, 130, 246, 0.15)",
              border: "1px solid rgba(59, 130, 246, 0.3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "16px",
            }}
          >
            ⚔️
          </div>
          <div>
            <h2 className="panel-title" style={{ margin: 0, fontSize: "16px" }}>
              Competitor Intelligence & Head-to-Head Tracker
            </h2>
            <div style={{ fontSize: "12px", color: "var(--muted)", marginTop: "2px" }}>
              Share of Voice (SOV), competitor publishing velocity, and SERP gap analysis
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="btn btn-primary"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "12px",
              padding: "6px 14px",
            }}
          >
            <span>+</span> Add Competitor
          </button>
          <button
            onClick={fetchAllData}
            disabled={loading}
            className="btn btn-secondary"
            style={{ fontSize: "12px", padding: "6px 12px" }}
            title="Refresh Competitor Intelligence"
          >
            {loading ? "Refreshing..." : "↻ Refresh"}
          </button>
        </div>
      </div>

      {/* Tab Navigation */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid var(--line)",
          background: "var(--panel-inner)",
          padding: "0 16px",
          gap: "8px",
        }}
      >
        <button
          onClick={() => setActiveTab("sov")}
          style={{
            padding: "10px 14px",
            background: "none",
            border: "none",
            borderBottom: activeTab === "sov" ? "2px solid var(--accent)" : "2px solid transparent",
            color: activeTab === "sov" ? "var(--ink)" : "var(--muted)",
            fontWeight: activeTab === "sov" ? 600 : 400,
            cursor: "pointer",
            fontSize: "13px",
            display: "flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          <span>🎯</span> Share of Voice
        </button>
        <button
          onClick={() => setActiveTab("matrix")}
          style={{
            padding: "10px 14px",
            background: "none",
            border: "none",
            borderBottom: activeTab === "matrix" ? "2px solid var(--accent)" : "2px solid transparent",
            color: activeTab === "matrix" ? "var(--ink)" : "var(--muted)",
            fontWeight: activeTab === "matrix" ? 600 : 400,
            cursor: "pointer",
            fontSize: "13px",
            display: "flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          <span>📊</span> Outranking Matrix ({outrankingMatrix.length})
        </button>
        <button
          onClick={() => setActiveTab("pages")}
          style={{
            padding: "10px 14px",
            background: "none",
            border: "none",
            borderBottom: activeTab === "pages" ? "2px solid var(--accent)" : "2px solid transparent",
            color: activeTab === "pages" ? "var(--ink)" : "var(--muted)",
            fontWeight: activeTab === "pages" ? 600 : 400,
            cursor: "pointer",
            fontSize: "13px",
            display: "flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          <span>📰</span> New Pages Feed ({newPages.length})
        </button>
        <button
          onClick={() => setActiveTab("manage")}
          style={{
            padding: "10px 14px",
            background: "none",
            border: "none",
            borderBottom: activeTab === "manage" ? "2px solid var(--accent)" : "2px solid transparent",
            color: activeTab === "manage" ? "var(--ink)" : "var(--muted)",
            fontWeight: activeTab === "manage" ? 600 : 400,
            cursor: "pointer",
            fontSize: "13px",
            display: "flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          <span>⚙️</span> Manage Domains ({competitors.length})
        </button>
      </div>

      {/* Body Content */}
      <div style={{ padding: "16px" }}>
        {error && (
          <div
            style={{
              padding: "12px 16px",
              background: "rgba(239, 68, 68, 0.1)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              color: "#f87171",
              borderRadius: "6px",
              fontSize: "13px",
              marginBottom: "16px",
            }}
          >
            {error}
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: "center", padding: "40px", color: "var(--muted)", fontSize: "14px" }}>
            Aggregating competitor SERP visibility and market share...
          </div>
        ) : (
          <>
            {/* TAB 1: SHARE OF VOICE */}
            {activeTab === "sov" && sovData && (
              <div>
                {/* Summary Banner */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                    gap: "12px",
                    marginBottom: "20px",
                  }}
                >
                  <div
                    style={{
                      background: "var(--panel-inner)",
                      padding: "14px",
                      borderRadius: "8px",
                      border: "1px solid var(--line)",
                    }}
                  >
                    <div style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>
                      Our Share of Voice
                    </div>
                    <div
                      style={{
                        fontSize: "26px",
                        fontWeight: 700,
                        color: "var(--green)",
                        margin: "4px 0",
                        fontFamily: "'DotGothic16', monospace",
                      }}
                    >
                      {sovData.our_sov_percentage}%
                    </div>
                    <div style={{ fontSize: "11px", color: "var(--muted)" }}>{sovData.our_sov_trend}</div>
                  </div>

                  <div
                    style={{
                      background: "var(--panel-inner)",
                      padding: "14px",
                      borderRadius: "8px",
                      border: "1px solid var(--line)",
                    }}
                  >
                    <div style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>
                      Current Market Leader
                    </div>
                    <div
                      style={{
                        fontSize: "20px",
                        fontWeight: 700,
                        color: "var(--ink)",
                        margin: "4px 0",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {sovData.market_leader}
                    </div>
                    <div style={{ fontSize: "11px", color: "var(--muted)" }}>Top visibility competitor</div>
                  </div>

                  <div
                    style={{
                      background: "var(--panel-inner)",
                      padding: "14px",
                      borderRadius: "8px",
                      border: "1px solid var(--line)",
                    }}
                  >
                    <div style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>
                      Analyzed Search Cluster
                    </div>
                    <div
                      style={{
                        fontSize: "26px",
                        fontWeight: 700,
                        color: "var(--accent)",
                        margin: "4px 0",
                        fontFamily: "'DotGothic16', monospace",
                      }}
                    >
                      {sovData.total_keywords_analyzed}
                    </div>
                    <div style={{ fontSize: "11px", color: "var(--muted)" }}>Keywords mapped in SERP pool</div>
                  </div>

                  <div
                    style={{
                      background: "var(--panel-inner)",
                      padding: "14px",
                      borderRadius: "8px",
                      border: "1px solid var(--line)",
                    }}
                  >
                    <div style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>
                      Tracked Competitors
                    </div>
                    <div
                      style={{
                        fontSize: "26px",
                        fontWeight: 700,
                        color: "var(--ink)",
                        margin: "4px 0",
                        fontFamily: "'DotGothic16', monospace",
                      }}
                    >
                      {competitors.length}
                    </div>
                    <div style={{ fontSize: "11px", color: "var(--muted)" }}>Domains actively benchmarked</div>
                  </div>
                </div>

                {/* Share of Voice Visual Distribution Bar */}
                <div
                  style={{
                    background: "var(--panel-inner)",
                    padding: "16px",
                    borderRadius: "8px",
                    border: "1px solid var(--line)",
                    marginBottom: "20px",
                  }}
                >
                  <div style={{ fontSize: "13px", fontWeight: 600, marginBottom: "12px" }}>
                    Organic Search Market Share Distribution
                  </div>
                  <div
                    style={{
                      height: "24px",
                      borderRadius: "6px",
                      display: "flex",
                      overflow: "hidden",
                      background: "rgba(255,255,255,0.05)",
                    }}
                  >
                    {/* Our Site Segment */}
                    <div
                      title={`Your Site: ${sovData.our_sov_percentage}%`}
                      style={{
                        width: `${sovData.our_sov_percentage}%`,
                        background: "var(--green)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: "11px",
                        fontWeight: 700,
                        color: "#000",
                        transition: "width 0.4s ease",
                      }}
                    >
                      {sovData.our_sov_percentage > 10 ? `${sovData.our_sov_percentage}%` : ""}
                    </div>
                    {/* Competitor Segments */}
                    {sovData.competitors.map((c, i) => {
                      const colors = ["#3b82f6", "#f59e0b", "#ec4899", "#8b5cf6", "#06b6d4"];
                      const bg = colors[i % colors.length];
                      return (
                        <div
                          key={c.domain}
                          title={`${c.domain}: ${c.sov_percentage}%`}
                          style={{
                            width: `${c.sov_percentage}%`,
                            background: bg,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "11px",
                            fontWeight: 600,
                            color: "#fff",
                            transition: "width 0.4s ease",
                          }}
                        >
                          {c.sov_percentage > 12 ? `${c.sov_percentage}%` : ""}
                        </div>
                      );
                    })}
                  </div>

                  {/* Legend */}
                  <div
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: "14px",
                      marginTop: "12px",
                      fontSize: "12px",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <span style={{ width: "10px", height: "10px", borderRadius: "2px", background: "var(--green)" }} />
                      <span style={{ fontWeight: 600 }}>Your Domain ({sovData.our_sov_percentage}%)</span>
                    </div>
                    {sovData.competitors.map((c, i) => {
                      const colors = ["#3b82f6", "#f59e0b", "#ec4899", "#8b5cf6", "#06b6d4"];
                      const bg = colors[i % colors.length];
                      return (
                        <div key={c.domain} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <span style={{ width: "10px", height: "10px", borderRadius: "2px", background: bg }} />
                          <span>
                            {c.domain} ({c.sov_percentage}%)
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Detailed Table */}
                <div className="table-responsive">
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                    <thead>
                      <tr
                        style={{
                          borderBottom: "1px solid var(--line)",
                          textAlign: "left",
                          color: "var(--muted)",
                          fontSize: "11px",
                          textTransform: "uppercase",
                        }}
                      >
                        <th style={{ padding: "8px 12px" }}>Domain</th>
                        <th style={{ padding: "8px 12px" }}>Authority (DA)</th>
                        <th style={{ padding: "8px 12px" }}>Share of Voice</th>
                        <th style={{ padding: "8px 12px" }}>Top 3 Ranks</th>
                        <th style={{ padding: "8px 12px" }}>Top 10 Ranks</th>
                        <th style={{ padding: "8px 12px" }}>28d Trend</th>
                      </tr>
                    </thead>
                    <tbody>
                      {/* Your Domain Row */}
                      <tr
                        style={{
                          borderBottom: "1px solid var(--line)",
                          background: "rgba(16, 185, 129, 0.05)",
                          fontWeight: 600,
                        }}
                      >
                        <td style={{ padding: "10px 12px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <span style={{ color: "var(--green)" }}>●</span>
                            <span>{sovData.target_domain}</span>
                            <span
                              style={{
                                fontSize: "10px",
                                background: "rgba(16, 185, 129, 0.2)",
                                color: "var(--green)",
                                padding: "2px 6px",
                                borderRadius: "4px",
                              }}
                            >
                              YOU
                            </span>
                          </div>
                        </td>
                        <td style={{ padding: "10px 12px" }}>72</td>
                        <td style={{ padding: "10px 12px", color: "var(--green)", fontWeight: 700 }}>
                          {sovData.our_sov_percentage}%
                        </td>
                        <td style={{ padding: "10px 12px" }}>
                          {Math.round(sovData.total_keywords_analyzed * 0.35)}
                        </td>
                        <td style={{ padding: "10px 12px" }}>
                          {Math.round(sovData.total_keywords_analyzed * 0.68)}
                        </td>
                        <td style={{ padding: "10px 12px", color: "var(--green)" }}>{sovData.our_sov_trend}</td>
                      </tr>

                      {/* Competitor Rows */}
                      {sovData.competitors.map((c) => (
                        <tr key={c.domain} style={{ borderBottom: "1px solid var(--line)" }}>
                          <td style={{ padding: "10px 12px" }}>
                            <div>
                              <div style={{ fontWeight: 500 }}>{c.domain}</div>
                              <div style={{ fontSize: "11px", color: "var(--muted)" }}>{c.label}</div>
                            </div>
                          </td>
                          <td style={{ padding: "10px 12px" }}>
                            <span
                              style={{
                                padding: "2px 6px",
                                background: "var(--panel-inner)",
                                borderRadius: "4px",
                                fontSize: "11px",
                                fontFamily: "monospace",
                              }}
                            >
                              {c.authority}
                            </span>
                          </td>
                          <td style={{ padding: "10px 12px", fontWeight: 600 }}>{c.sov_percentage}%</td>
                          <td style={{ padding: "10px 12px" }}>{c.top_3_rankings}</td>
                          <td style={{ padding: "10px 12px" }}>{c.top_10_rankings}</td>
                          <td
                            style={{
                              padding: "10px 12px",
                              color: c.trend.startsWith("+") ? "#ef4444" : "var(--muted)",
                            }}
                          >
                            {c.trend}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* TAB 2: SERP OUTRANKING MATRIX */}
            {activeTab === "matrix" && (
              <div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: "10px",
                    background: "rgba(239, 68, 68, 0.08)",
                    border: "1px solid rgba(239, 68, 68, 0.2)",
                    padding: "12px 16px",
                    borderRadius: "8px",
                    marginBottom: "16px",
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, color: "#f87171", fontSize: "14px" }}>
                      SERP Deficit Analysis: Competitors Outranking Your Pages
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--muted)", marginTop: "2px" }}>
                      Estimated organic click & revenue loss based on average SERP CTR curves
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "16px", textAlign: "right" }}>
                    <div>
                      <div style={{ fontSize: "11px", color: "var(--muted)" }}>Est. Clicks Lost</div>
                      <div style={{ fontSize: "16px", fontWeight: 700, color: "#f87171" }}>
                        -{Number(totalClicksLost ?? 0).toLocaleString()} /mo
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: "11px", color: "var(--muted)" }}>Potential MRR Deficit</div>
                      <div style={{ fontSize: "16px", fontWeight: 700, color: "var(--amber)" }}>
                        -${Number(totalMrrLoss ?? 0).toLocaleString()} /mo
                      </div>
                    </div>
                  </div>
                </div>

                <div className="table-responsive">
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                    <thead>
                      <tr
                        style={{
                          borderBottom: "1px solid var(--line)",
                          textAlign: "left",
                          color: "var(--muted)",
                          fontSize: "11px",
                          textTransform: "uppercase",
                        }}
                      >
                        <th style={{ padding: "8px 12px" }}>Target Query</th>
                        <th style={{ padding: "8px 12px" }}>Search Vol</th>
                        <th style={{ padding: "8px 12px" }}>Rank Gap</th>
                        <th style={{ padding: "8px 12px" }}>Competitor Winner</th>
                        <th style={{ padding: "8px 12px" }}>Traffic Loss</th>
                        <th style={{ padding: "8px 12px" }}>Root Cause & Lever</th>
                      </tr>
                    </thead>
                    <tbody>
                      {outrankingMatrix.map((item, idx) => (
                        <tr
                          key={idx}
                          style={{
                            borderBottom: "1px solid var(--line)",
                            background: idx % 2 === 0 ? "transparent" : "var(--panel-inner)",
                          }}
                        >
                          <td style={{ padding: "12px" }}>
                            <div style={{ fontWeight: 600, color: "var(--ink)" }}>{item.keyword}</div>
                            <div
                              style={{
                                fontSize: "11px",
                                color: "var(--muted)",
                                marginTop: "2px",
                                maxWidth: "260px",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }}
                            >
                              Our URL: {item.our_url}
                            </div>
                          </td>
                          <td style={{ padding: "12px", fontFamily: "monospace" }}>
                            {Number(item.search_volume ?? 0).toLocaleString()}
                          </td>
                          <td style={{ padding: "12px" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                              <span
                                style={{
                                  padding: "2px 6px",
                                  background: "rgba(239, 68, 68, 0.15)",
                                  color: "#f87171",
                                  borderRadius: "4px",
                                  fontSize: "11px",
                                  fontWeight: 700,
                                }}
                              >
                                #{item.our_position}
                              </span>
                              <span style={{ color: "var(--muted)", fontSize: "11px" }}>vs</span>
                              <span
                                style={{
                                  padding: "2px 6px",
                                  background: "rgba(16, 185, 129, 0.15)",
                                  color: "var(--green)",
                                  borderRadius: "4px",
                                  fontSize: "11px",
                                  fontWeight: 700,
                                }}
                              >
                                #{item.competitor_position}
                              </span>
                            </div>
                          </td>
                          <td style={{ padding: "12px" }}>
                            <div style={{ fontWeight: 500 }}>{item.competitor_domain}</div>
                            <a
                              href={item.competitor_url}
                              target="_blank"
                              rel="noreferrer"
                              style={{
                                fontSize: "11px",
                                color: "var(--accent)",
                                textDecoration: "none",
                                display: "block",
                                marginTop: "2px",
                              }}
                            >
                              Inspect Rival URL ↗
                            </a>
                          </td>
                          <td style={{ padding: "12px" }}>
                            <div style={{ color: "#f87171", fontWeight: 600 }}>
                              -{item.monthly_clicks_lost} clicks
                            </div>
                            <div style={{ fontSize: "11px", color: "var(--muted)" }}>
                              ~${Number(item.potential_mrr_loss ?? 0).toFixed(0)}/mo
                            </div>
                          </td>
                          <td style={{ padding: "12px", maxWidth: "340px" }}>
                            <div style={{ fontSize: "12px", color: "var(--ink)", marginBottom: "4px" }}>
                              <strong>Gap:</strong> {item.primary_gap_reason}
                            </div>
                            <div
                              style={{
                                fontSize: "11px",
                                color: "var(--accent)",
                                background: "rgba(59, 130, 246, 0.08)",
                                padding: "4px 8px",
                                borderRadius: "4px",
                              }}
                            >
                              <strong>Action:</strong> {item.recommended_action}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* TAB 3: NEW PAGES FEED */}
            {activeTab === "pages" && (
              <div>
                <div style={{ fontSize: "13px", color: "var(--muted)", marginBottom: "14px" }}>
                  Real-time detection of newly published competitor content, topical incursions, and recommended counter-pillars.
                </div>

                <div style={{ display: "grid", gap: "12px" }}>
                  {newPages.map((page) => {
                    const badgeColor =
                      page.threat_level === "CRITICAL"
                        ? "#ef4444"
                        : page.threat_level === "HIGH"
                        ? "var(--amber)"
                        : page.threat_level === "MEDIUM"
                        ? "#3b82f6"
                        : "var(--muted)";

                    return (
                      <div
                        key={page.id}
                        style={{
                          background: "var(--panel-inner)",
                          border: "1px solid var(--line)",
                          borderRadius: "8px",
                          padding: "16px",
                          display: "flex",
                          flexDirection: "column",
                          gap: "8px",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "12px" }}>
                          <div>
                            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                              <span
                                style={{
                                  fontSize: "11px",
                                  fontWeight: 600,
                                  color: "var(--muted)",
                                  textTransform: "uppercase",
                                }}
                              >
                                {page.competitor_domain}
                              </span>
                              <span style={{ fontSize: "11px", color: "var(--muted)" }}>•</span>
                              <span style={{ fontSize: "11px", color: "var(--muted)" }}>
                                Published: {page.published_date}
                              </span>
                            </div>
                            <h3 style={{ margin: 0, fontSize: "15px", fontWeight: 600, color: "var(--ink)" }}>
                              {page.title}
                            </h3>
                          </div>

                          <span
                            style={{
                              fontSize: "10px",
                              fontWeight: 700,
                              padding: "3px 8px",
                              borderRadius: "4px",
                              border: `1px solid ${badgeColor}`,
                              color: badgeColor,
                              whiteSpace: "nowrap",
                            }}
                          >
                            THREAT: {page.threat_level}
                          </span>
                        </div>

                        <div style={{ fontSize: "12px", color: "var(--muted)", display: "flex", gap: "8px" }}>
                          <span>Target Cluster: <strong>{page.target_topic}</strong></span>
                          <span>|</span>
                          <a
                            href={page.url}
                            target="_blank"
                            rel="noreferrer"
                            style={{ color: "var(--accent)", textDecoration: "none" }}
                          >
                            {page.url} ↗
                          </a>
                        </div>

                        <div
                          style={{
                            background: "rgba(59, 130, 246, 0.08)",
                            borderLeft: "3px solid var(--accent)",
                            padding: "8px 12px",
                            borderRadius: "0 6px 6px 0",
                            fontSize: "12px",
                            marginTop: "4px",
                          }}
                        >
                          <strong style={{ color: "var(--accent)" }}>Recommended Counter-Strategy: </strong>
                          <span style={{ color: "var(--ink)" }}>{page.counter_strategy}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* TAB 4: MANAGE COMPETITOR DOMAINS */}
            {activeTab === "manage" && (
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
                  <div style={{ fontSize: "13px", color: "var(--muted)" }}>
                    Add or remove competitor root domains for benchmark tracking and SERP surveillance.
                  </div>
                  <button
                    onClick={() => setIsAddModalOpen(true)}
                    className="btn btn-primary"
                    style={{ fontSize: "12px", padding: "6px 14px" }}
                  >
                    + Add New Competitor
                  </button>
                </div>

                <div className="table-responsive">
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                    <thead>
                      <tr
                        style={{
                          borderBottom: "1px solid var(--line)",
                          textAlign: "left",
                          color: "var(--muted)",
                          fontSize: "11px",
                          textTransform: "uppercase",
                        }}
                      >
                        <th style={{ padding: "8px 12px" }}>Competitor Domain</th>
                        <th style={{ padding: "8px 12px" }}>Label</th>
                        <th style={{ padding: "8px 12px" }}>Domain Authority</th>
                        <th style={{ padding: "8px 12px" }}>Organic Keywords</th>
                        <th style={{ padding: "8px 12px" }}>Est. Monthly Traffic</th>
                        <th style={{ padding: "8px 12px", textAlign: "right" }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {competitors.map((comp) => (
                        <tr key={comp.id} style={{ borderBottom: "1px solid var(--line)" }}>
                          <td style={{ padding: "10px 12px", fontWeight: 600 }}>{comp.domain}</td>
                          <td style={{ padding: "10px 12px", color: "var(--muted)" }}>{comp.label || "—"}</td>
                          <td style={{ padding: "10px 12px" }}>
                            <span
                              style={{
                                padding: "2px 6px",
                                background: "var(--panel-inner)",
                                borderRadius: "4px",
                                fontSize: "11px",
                              }}
                            >
                              DA {comp.domain_authority}
                            </span>
                          </td>
                          <td style={{ padding: "10px 12px" }}>
                            {comp.organic_keywords_count?.toLocaleString() || "—"}
                          </td>
                          <td style={{ padding: "10px 12px" }}>
                            {comp.est_monthly_visits ? `${comp.est_monthly_visits.toLocaleString()} visits` : "—"}
                          </td>
                          <td style={{ padding: "10px 12px", textAlign: "right" }}>
                            <button
                              onClick={() => handleDeleteCompetitor(comp.id, comp.domain)}
                              className="btn btn-secondary"
                              style={{
                                fontSize: "11px",
                                padding: "4px 8px",
                                color: "#f87171",
                                borderColor: "rgba(239, 68, 68, 0.3)",
                              }}
                            >
                              Remove
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Add Competitor Modal */}
      {isAddModalOpen && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0, 0, 0, 0.75)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "var(--panel-bg)",
              border: "1px solid var(--line)",
              borderRadius: "10px",
              width: "100%",
              maxWidth: "460px",
              padding: "24px",
              boxShadow: "0 20px 40px rgba(0, 0, 0, 0.5)",
            }}
          >
            <h3 style={{ margin: "0 0 8px 0", fontSize: "18px" }}>Add Competitor Domain</h3>
            <p style={{ margin: "0 0 16px 0", fontSize: "13px", color: "var(--muted)" }}>
              Enter a competitor domain to automatically track their organic keywords, Share of Voice, and newly published URLs.
            </p>

            <form onSubmit={handleAddCompetitor}>
              <div style={{ marginBottom: "14px" }}>
                <label style={{ display: "block", fontSize: "12px", color: "var(--muted)", marginBottom: "4px" }}>
                  Domain (e.g. competitor.com) *
                </label>
                <input
                  type="text"
                  required
                  placeholder="rivalcompany.com"
                  value={newDomain}
                  onChange={(e) => setNewDomain(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    background: "var(--panel-inner)",
                    border: "1px solid var(--line)",
                    color: "var(--ink)",
                    borderRadius: "6px",
                    fontSize: "14px",
                  }}
                />
              </div>

              <div style={{ marginBottom: "20px" }}>
                <label style={{ display: "block", fontSize: "12px", color: "var(--muted)", marginBottom: "4px" }}>
                  Friendly Label (Optional)
                </label>
                <input
                  type="text"
                  placeholder="Primary Enterprise Rival"
                  value={newLabel}
                  onChange={(e) => setNewLabel(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    background: "var(--panel-inner)",
                    border: "1px solid var(--line)",
                    color: "var(--ink)",
                    borderRadius: "6px",
                    fontSize: "14px",
                  }}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="btn btn-secondary"
                  style={{ fontSize: "13px" }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn btn-primary"
                  style={{ fontSize: "13px" }}
                >
                  {submitting ? "Analyzing..." : "Start Tracking"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
