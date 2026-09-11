"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface SERPResult {
  rank: number;
  url: string;
  title: string;
  description: string;
  has_table?: boolean;
  word_count?: number;
  h1?: string;
  h2s?: string[];
}

interface GSCKeyword {
  keyword?: string;
  query?: string;
  clicks?: number;
  impressions?: number;
  position?: number;
  ctr?: number;
  search_volume?: number;
  difficulty?: number;
  opportunity_score?: number;
}

export default function ResearchPage() {
  const [query, setQuery] = useState("");
  const [serpResults, setSerpResults] = useState<SERPResult[]>([]);
  const [keywords, setKeywords] = useState<GSCKeyword[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"keywords" | "serp" | "competitors">("keywords");
  const [websiteId, setWebsiteId] = useState<string>("");

  const [competitors, setCompetitors] = useState<any[]>([]);
  const [newCompDomain, setNewCompDomain] = useState("");
  const [addingComp, setAddingComp] = useState(false);
  const [gapLoading, setGapLoading] = useState<string | null>(null);
  const [gapResult, setGapResult] = useState<any | null>(null);

  const loadCompetitors = useCallback(async (wid: string) => {
    if (!wid) return;
    try {
      const res = await get(`/api/research/competitors?website_id=${wid}`);
      const list = res?.data || (Array.isArray(res) ? res : []);
      setCompetitors(list);
    } catch {
      setCompetitors([]);
    }
  }, []);

  const loadKeywords = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);
    if (!wid) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Fetch keywords from GSC / Crawl fallback
      let data: any = null;
      try {
        data = await get(`/api/gsc/${wid}/keywords`);
      } catch {
        data = await get(`/api/gsc/keywords/${wid}`);
      }

      const kwList = Array.isArray(data) ? data : data?.keywords || [];
      setKeywords(kwList);
      loadCompetitors(wid);
    } catch (e: any) {
      setError(e.message || "Failed to fetch keyword opportunities");
      setKeywords([]);
    } finally {
      setLoading(false);
    }
  }, [loadCompetitors]);

  useEffect(() => {
    loadKeywords();
    const handleChanged = () => loadKeywords();
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [loadKeywords]);

  const handleAddCompetitor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCompDomain.trim() || !websiteId) return;
    try {
      setAddingComp(true);
      const cleanDomain = newCompDomain.replace(/^https?:\/\//, "").replace(/\/.*$/, "").trim();
      const res = await post("/api/research/competitors", {
        website_id: websiteId,
        domain: cleanDomain,
        notes: "Tracked for content gaps",
      });
      if (res?.data || res?.domain) {
        setNewCompDomain("");
        loadCompetitors(websiteId);
      }
    } catch (e: any) {
      setError(e.message || "Failed to add competitor");
    } finally {
      setAddingComp(false);
    }
  };

  const handleRunGapAnalysis = async (compDomain: string) => {
    try {
      setGapLoading(compDomain);
      setError(null);
      const res = await post("/api/research/content-gap", {
        website_id: websiteId || "default",
        competitor_domain: compDomain,
      });
      setGapResult(res);
    } catch (e: any) {
      setError(e.message || "Failed to run content gap analysis");
    } finally {
      setGapLoading(null);
    }
  };

  const runSERP = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    if (!websiteId) {
      setError("Please select or add a website first.");
      return;
    }

    try {
      setAnalyzing(true);
      setError(null);
      setActiveTab("serp");

      let data: any = null;
      try {
        data = await get(`/api/research?website_id=${websiteId}&query=${encodeURIComponent(query.trim())}`);
      } catch {
        data = await get(`/api/serp-analysis/${websiteId}?query=${encodeURIComponent(query.trim())}`);
      }

      const results = data?.results || data?.serp_results || data?.top_results || (Array.isArray(data) ? data : []);
      setSerpResults(results);
    } catch (e: any) {
      setError(e.message || "Failed to run SERP competitor intelligence");
      setSerpResults([]);
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading && keywords.length === 0) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px auto" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Mining keyword opportunities & SERP intelligence...
        </p>
      </div>
    );
  }

  if (!websiteId) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">Keyword & SERP Research</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No data yet — add a website first.</strong> Connect your website to discover target keywords and competitor rankings.
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
      <div className="page-heading">Keyword Research & SERP Intelligence</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        GSC Mining · NVIDIA NIM Crawl Fallback · SERP Competitor Analysis
        {error && (
          <span className="badge badge-amber" style={{ marginLeft: "12px" }}>
            {error}
          </span>
        )}
      </div>

      {/* SEARCH BOX */}
      <div className="panel" style={{ marginBottom: "20px" }}>
        <div className="panel-head">
          <span className="panel-label">Analyze SERP Competitors for Any Target Keyword</span>
        </div>
        <div className="panel-body">
          <form onSubmit={runSERP} style={{ display: "flex", gap: "10px" }}>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. personal injury lawyer settlement amounts"
              className="field"
              style={{ flex: 1, padding: "8px 12px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
            />
            <button type="submit" className="btn btn-accent" disabled={analyzing || !query.trim()} style={{ padding: "8px 20px" }}>
              {analyzing ? "Analyzing SERP..." : "⚡ Analyze SERP"}
            </button>
          </form>
        </div>
      </div>

      {/* TABS */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "14px" }}>
        <button
          onClick={() => setActiveTab("keywords")}
          className={`btn ${activeTab === "keywords" ? "btn-accent" : ""}`}
          style={{ padding: "6px 14px", fontSize: "11px" }}
        >
          Target Keywords ({keywords.length})
        </button>
        <button
          onClick={() => setActiveTab("serp")}
          className={`btn ${activeTab === "serp" ? "btn-accent" : ""}`}
          style={{ padding: "6px 14px", fontSize: "11px" }}
        >
          SERP Competitors ({serpResults.length})
        </button>
        <button
          onClick={() => setActiveTab("competitors")}
          className={`btn ${activeTab === "competitors" ? "btn-accent" : ""}`}
          style={{ padding: "6px 14px", fontSize: "11px" }}
        >
          Competitors & Content Gaps ({competitors.length})
        </button>
      </div>

      {/* TAB CONTENT: KEYWORDS */}
      {activeTab === "keywords" && (
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">Discovered Keyword Opportunities</span>
            <button className="panel-action" onClick={loadKeywords}>
              Refresh
            </button>
          </div>
          <div className="panel-body" style={{ padding: "0" }}>
            {keywords.length === 0 ? (
              <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
                No keywords discovered yet. Connect GSC in /connectors or run keyword research — rows below show measured values only, never filler.
              </div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "12px" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--line)", color: "var(--muted)", textTransform: "uppercase", fontSize: "10px" }}>
                    <th style={{ padding: "10px 14px" }}>Keyword Phrase</th>
                    <th style={{ padding: "10px 14px" }}>Est. Volume / Imp</th>
                    <th style={{ padding: "10px 14px" }}>Position / Diff</th>
                    <th style={{ padding: "10px 14px" }}>Opportunity Score</th>
                    <th style={{ padding: "10px 14px" }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                      {keywords.map((kw, i) => {
                    const kwText = kw.keyword || kw.query || `Keyword #${i + 1}`;
                    const vol = kw.search_volume ?? kw.impressions ?? null;
                    const pos = kw.position ?? null;
                    const diff = kw.difficulty ?? null;
                    const opp = kw.opportunity_score ?? null;
                    return (
                      <tr key={i} style={{ borderBottom: "1px solid var(--line)" }}>
                        <td style={{ padding: "10px 14px", fontWeight: 600 }}>{kwText}</td>
                        <td style={{ padding: "10px 14px" }}>{vol != null ? vol.toLocaleString() : "—"}</td>
                        <td style={{ padding: "10px 14px" }}>
                          {pos != null ? `#${Number(pos).toFixed(1)}` : diff != null ? `${diff}/100 (modeled)` : "—"}
                        </td>
                        <td style={{ padding: "10px 14px" }}>
                          {opp != null ? (
                            <span className="badge badge-green">{opp}/100</span>
                          ) : (
                            <span style={{ color: "var(--muted)" }}>—</span>
                          )}
                        </td>
                        <td style={{ padding: "10px 14px" }}>
                          <Link
                            href={`/writer`}
                            className="btn btn-accent"
                            style={{ textDecoration: "none", fontSize: "10px", padding: "4px 8px" }}
                          >
                            ⚡ Write Article
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* TAB CONTENT: COMPETITORS & CONTENT GAP */}
      {activeTab === "competitors" && (
        <div style={{ display: "grid", gap: "16px" }}>
          {/* ADD COMPETITOR PANEL */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Add Tracked Competitor Domain</span>
            </div>
            <div className="panel-body" style={{ padding: "14px 16px" }}>
              <form onSubmit={handleAddCompetitor} style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                <input
                  type="text"
                  value={newCompDomain}
                  onChange={(e) => setNewCompDomain(e.target.value)}
                  placeholder="e.g. competitor-niche.com"
                  className="field"
                  style={{ flex: 1, padding: "8px 12px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)", fontSize: "12px" }}
                />
                <button
                  type="submit"
                  className="btn btn-accent"
                  disabled={addingComp || !newCompDomain.trim()}
                  style={{ padding: "8px 16px", fontSize: "11px", whiteSpace: "nowrap" }}
                >
                  {addingComp ? "Adding..." : "+ Track Competitor"}
                </button>
              </form>
            </div>
          </div>

          {/* TRACKED COMPETITORS LIST */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Tracked Competitor Domains ({competitors.length})</span>
            </div>
            <div className="panel-body" style={{ padding: "16px" }}>
              {competitors.length === 0 ? (
                <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
                  No competitor domains tracked yet. Enter a competitor above to analyze content gaps and ranking opportunities.
                </div>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "16px" }}>
                  {competitors.map((comp, idx) => (
                    <div key={idx} style={{ padding: "16px", border: "1px solid var(--line)", background: "var(--surface)", borderRadius: "8px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                        <span style={{ fontWeight: 700, fontSize: "14px", color: "var(--ink)" }}>{comp.domain}</span>
                        <span className="badge badge-accent">Tracked</span>
                      </div>
                      <div style={{ fontSize: "12px", color: "var(--muted)", display: "grid", gap: "4px", marginBottom: "12px" }}>
                        <div>Added: <b style={{ color: "var(--ink)" }}>{comp.created_at ? new Date(comp.created_at).toLocaleDateString() : "Active"}</b></div>
                        <div>Notes: <b style={{ color: "var(--ink)" }}>{comp.notes || "SERP gap monitoring"}</b></div>
                      </div>
                      <button
                        onClick={() => handleRunGapAnalysis(comp.domain)}
                        disabled={gapLoading === comp.domain}
                        className="btn btn-accent"
                        style={{ width: "100%", fontSize: "11px", padding: "8px" }}
                      >
                        {gapLoading === comp.domain ? "Analyzing Live SERP..." : "⚡ Run Live Content Gap Analysis"}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* LIVE CONTENT GAP RESULTS TABLE */}
          {gapResult && (
            <div className="panel" style={{ borderColor: "var(--accent)" }}>
              <div className="panel-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="panel-label">
                  Content Gaps vs {gapResult.competitor_domain} ({gapResult.total_gaps_found || 0} Opportunities Found)
                </span>
                <span style={{ fontSize: "10px", color: "var(--muted)" }}>
                  Volume/value/difficulty are rank-order modeled estimates, not measured data
                </span>
                <button
                  className="panel-action"
                  onClick={() => setGapResult(null)}
                  style={{ fontSize: "11px" }}
                >
                  Close
                </button>
              </div>
              <div className="panel-body" style={{ padding: "0" }}>
                {(!gapResult.gap_opportunities || gapResult.gap_opportunities.length === 0) ? (
                  <div style={{ padding: "24px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
                    No unserved ranking gaps detected for this competitor query.
                  </div>
                ) : (
                  <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "12px" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--line)", color: "var(--muted)", textTransform: "uppercase", fontSize: "10px" }}>
                        <th style={{ padding: "10px 14px" }}>Gap Keyword / Opportunity</th>
                        <th style={{ padding: "10px 14px" }}>Competitor Rank</th>
                        <th style={{ padding: "10px 14px" }}>Est. Volume</th>
                        <th style={{ padding: "10px 14px" }}>Est. Traffic Value</th>
                        <th style={{ padding: "10px 14px" }}>Difficulty</th>
                        <th style={{ padding: "10px 14px" }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {gapResult.gap_opportunities.map((gap: any, gIdx: number) => (
                        <tr key={gIdx} style={{ borderBottom: "1px solid var(--line)" }}>
                          <td style={{ padding: "10px 14px" }}>
                            <div style={{ fontWeight: 600 }}>{gap.keyword}</div>
                            {gap.competitor_url && (
                              <a
                                href={gap.competitor_url}
                                target="_blank"
                                rel="noreferrer"
                                style={{ fontSize: "10px", color: "var(--muted)", textDecoration: "none" }}
                              >
                                {gap.competitor_url.slice(0, 45)}... ↗
                              </a>
                            )}
                          </td>
                          <td style={{ padding: "10px 14px" }}>
                            <span className="badge badge-amber">#{gap.competitor_rank}</span>
                          </td>
                          <td style={{ padding: "10px 14px" }} title="Rank-order modeled estimate, not measured search volume">
                            ~{gap.estimated_search_volume?.toLocaleString() || "—"} /mo
                          </td>
                          <td style={{ padding: "10px 14px", fontWeight: 600, color: "var(--green)" }} title="Modeled: est. volume × 18% CTR × $4.50 CPC — heuristic, not revenue">
                            ~${gap.estimated_traffic_value?.toLocaleString() || "0"}
                          </td>
                          <td style={{ padding: "10px 14px" }} title="Rank-order heuristic, not a measured difficulty score">
                            ~{gap.difficulty}/100
                          </td>
                          <td style={{ padding: "10px 14px" }}>
                            <Link
                              href={`/writer?topic=${encodeURIComponent(gap.keyword)}`}
                              className="btn btn-accent"
                              style={{ textDecoration: "none", fontSize: "10px", padding: "4px 8px", whiteSpace: "nowrap" }}
                            >
                              ⚡ Write Counter-Article
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
