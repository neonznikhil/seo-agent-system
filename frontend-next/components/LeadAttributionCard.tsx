"use client";

import { useEffect, useState, useCallback } from "react";
import { get, post } from "@/lib/api";

interface KeywordAttribution {
  keyword: string;
  url: string;
  clicks: number;
  estimated_conversions: number;
  cvr_percentage: number;
  cost_per_lead: number;
  pipeline_value: number;
  intent: string;
  rank: number;
}

interface LeadSummary {
  website_id: string;
  total_spend: number;
  total_leads: number;
  blended_cpl: number;
  total_pipeline_value: number;
  roi_percentage: number;
  top_converting_keywords: KeywordAttribution[];
}

interface LeadAttributionCardProps {
  websiteId: string;
}

export function LeadAttributionCard({ websiteId }: LeadAttributionCardProps) {
  const [summary, setSummary] = useState<LeadSummary | null>(null);
  const [keywords, setKeywords] = useState<KeywordAttribution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isEditingBudget, setIsEditingBudget] = useState(false);
  const [newBudget, setNewBudget] = useState<string>("2500");

  const fetchAttributionData = useCallback(async () => {
    if (!websiteId) return;
    setLoading(true);
    setError(null);
    try {
      const [sumRes, kwRes] = await Promise.all([
        get(`/api/leads/${websiteId}/summary`),
        get(`/api/leads/${websiteId}/keyword-performance`),
      ]);
      setSummary(sumRes);
      setKeywords(kwRes.keywords || []);
      if (sumRes.total_spend) {
        setNewBudget(sumRes.total_spend.toString());
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load lead attribution data");
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  useEffect(() => {
    fetchAttributionData();
  }, [fetchAttributionData]);

  const handleUpdateBudget = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!websiteId) return;
    try {
      await post(`/api/leads/${websiteId}/settings`, { monthly_budget: parseFloat(newBudget) || 2500 });
      setIsEditingBudget(false);
      fetchAttributionData();
    } catch (err: any) {
      alert(`Failed to update budget: ${err?.message || "Error"}`);
    }
  };

  return (
    <div className="panel" style={{ marginBottom: "24px" }}>
      <div className="panel-head" style={{ flexWrap: "wrap", gap: "10px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontSize: "18px" }}>💰</span>
          <span className="panel-label" style={{ fontSize: "12px", fontWeight: 700, color: "var(--ink)" }}>
            Lead & Revenue Attribution (GA4 + GSC)
          </span>
          <span className="badge badge-accent">Keyword-Level CPL</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button
            onClick={() => setIsEditingBudget(true)}
            className="btn"
            style={{
              padding: "4px 10px",
              fontSize: "10.5px",
              background: "var(--panel-inner)",
              border: "1px solid var(--border)",
              cursor: "pointer",
            }}
          >
            ⚙️ Set Monthly Budget (${summary?.total_spend?.toLocaleString() || "2,500"})
          </button>
          <button
            onClick={fetchAttributionData}
            disabled={loading}
            className="btn"
            style={{
              padding: "4px 10px",
              fontSize: "10.5px",
              background: "var(--panel-inner)",
              border: "1px solid var(--border)",
              cursor: "pointer",
            }}
          >
            🔄 Sync GA4
          </button>
        </div>
      </div>

      <div className="panel-body" style={{ padding: "16px" }}>
        {/* KPI CARDS */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: "12px",
            marginBottom: "18px",
          }}
        >
          <div style={{ padding: "12px 14px", background: "var(--panel-inner)", border: "1px solid var(--line)", borderRadius: "4px" }}>
            <div style={{ fontSize: "9.5px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "4px" }}>
              Total Monthly Leads
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: "6px" }}>
              <span style={{ fontFamily: "DotGothic16, monospace", fontSize: "26px", color: "var(--green)" }}>
                {summary?.total_leads || 0}
              </span>
              <span style={{ fontSize: "11px", color: "var(--muted)" }}>Qualified</span>
            </div>
          </div>

          <div style={{ padding: "12px 14px", background: "var(--panel-inner)", border: "1px solid var(--line)", borderRadius: "4px" }}>
            <div style={{ fontSize: "9.5px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "4px" }}>
              Blended Cost Per Lead
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: "6px" }}>
              <span style={{ fontFamily: "DotGothic16, monospace", fontSize: "26px", color: "var(--ink)" }}>
                ${summary?.blended_cpl ? Math.round(summary.blended_cpl) : "--"}
              </span>
              <span style={{ fontSize: "11px", color: "var(--green)" }}>/ lead</span>
            </div>
          </div>

          <div style={{ padding: "12px 14px", background: "var(--panel-inner)", border: "1px solid var(--line)", borderRadius: "4px" }}>
            <div style={{ fontSize: "9.5px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "4px" }}>
              Pipeline Value Created
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: "6px" }}>
              <span style={{ fontFamily: "DotGothic16, monospace", fontSize: "26px", color: "var(--green)" }}>
                ${summary?.total_pipeline_value ? summary.total_pipeline_value.toLocaleString() : "0"}
              </span>
            </div>
          </div>

          <div style={{ padding: "12px 14px", background: "var(--panel-inner)", border: "1px solid var(--line)", borderRadius: "4px" }}>
            <div style={{ fontSize: "9.5px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "4px" }}>
              Attributed Organic ROI
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: "6px" }}>
              <span style={{ fontFamily: "DotGothic16, monospace", fontSize: "26px", color: "var(--accent)" }}>
                {summary?.roi_percentage ? Math.round(summary.roi_percentage) : 0}%
              </span>
              <span style={{ fontSize: "11px", color: "var(--muted)" }}>over spend</span>
            </div>
          </div>
        </div>

        {/* ERROR STATE */}
        {error && (
          <div style={{ padding: "10px", background: "rgba(239, 68, 68, 0.1)", border: "1px solid var(--red)", color: "var(--red)", fontSize: "11.5px", marginBottom: "12px" }}>
            ⚠️ {error}
          </div>
        )}

        {/* KEYWORDS TABLE */}
        <div style={{ overflowX: "auto", border: "1px solid var(--border)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "11px", textAlign: "left" }}>
            <thead>
              <tr style={{ background: "var(--table-head)", borderBottom: "1px solid var(--border)" }}>
                <th style={{ padding: "9px 12px", fontWeight: 700 }}>Keyword</th>
                <th style={{ padding: "9px 12px", fontWeight: 700 }}>SERP Pos</th>
                <th style={{ padding: "9px 12px", fontWeight: 700 }}>Clicks</th>
                <th style={{ padding: "9px 12px", fontWeight: 700 }}>Est. Leads</th>
                <th style={{ padding: "9px 12px", fontWeight: 700 }}>CVR %</th>
                <th style={{ padding: "9px 12px", fontWeight: 700 }}>Cost / Lead</th>
                <th style={{ padding: "9px 12px", fontWeight: 700 }}>Pipeline Value</th>
                <th style={{ padding: "9px 12px", fontWeight: 700 }}>Intent</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} style={{ padding: "24px", textAlign: "center", color: "var(--muted)" }}>
                    Loading keyword conversion metrics...
                  </td>
                </tr>
              ) : keywords.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ padding: "24px", textAlign: "center", color: "var(--muted)" }}>
                    No keyword attribution data available yet.
                  </td>
                </tr>
              ) : (
                keywords.map((kw, idx) => (
                  <tr key={idx} style={{ borderBottom: "1px solid var(--line)" }}>
                    <td style={{ padding: "10px 12px" }}>
                      <div style={{ fontWeight: 600, color: "var(--ink)" }}>{kw.keyword}</div>
                      <div style={{ fontSize: "9.5px", color: "var(--muted)", maxWidth: "240px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {kw.url}
                      </div>
                    </td>

                    <td style={{ padding: "10px 12px" }}>
                      <span
                        style={{
                          padding: "2px 6px",
                          background: kw.rank <= 3 ? "rgba(34, 197, 94, 0.15)" : kw.rank <= 10 ? "rgba(245, 158, 11, 0.15)" : "var(--panel-inner)",
                          color: kw.rank <= 3 ? "var(--green)" : kw.rank <= 10 ? "var(--amber)" : "var(--muted)",
                          fontWeight: 700,
                          borderRadius: "2px",
                        }}
                      >
                        #{kw.rank}
                      </span>
                    </td>

                    <td style={{ padding: "10px 12px", fontWeight: 600 }}>
                      {Number(kw.clicks ?? 0).toLocaleString()}
                    </td>

                    <td style={{ padding: "10px 12px", color: "var(--green)", fontWeight: 700 }}>
                      {kw.estimated_conversions}
                    </td>

                    <td style={{ padding: "10px 12px" }}>
                      {Number(kw.cvr_percentage ?? 0).toFixed(1)}%
                    </td>

                    <td style={{ padding: "10px 12px", fontWeight: 600 }}>
                      ${Math.round(kw.cost_per_lead ?? 0)}
                    </td>

                    <td style={{ padding: "10px 12px", color: "var(--green)", fontWeight: 700 }}>
                      ${Number(kw.pipeline_value ?? 0).toLocaleString()}
                    </td>

                    <td style={{ padding: "10px 12px" }}>
                      <span
                        style={{
                          padding: "2px 6px",
                          fontSize: "9px",
                          textTransform: "uppercase",
                          border: "1px solid var(--line)",
                          borderRadius: "2px",
                          color: kw.intent === "Commercial" || kw.intent === "Transactional" ? "var(--accent)" : "var(--muted)",
                        }}
                      >
                        {kw.intent}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* EDIT BUDGET MODAL */}
      {isEditingBudget && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0, 0, 0, 0.65)",
            zIndex: 9999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            style={{
              width: "100%",
              maxWidth: "420px",
              background: "var(--bg)",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              padding: "20px",
            }}
          >
            <div style={{ fontSize: "14px", fontWeight: 700, marginBottom: "8px", color: "var(--ink)" }}>
              Set Monthly SEO Spend / Budget
            </div>
            <div style={{ fontSize: "11px", color: "var(--muted)", marginBottom: "16px" }}>
              This spend figure is used to calculate keyword-level Cost Per Lead (CPL) and total organic pipeline ROI.
            </div>

            <form onSubmit={handleUpdateBudget}>
              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "10.5px", textTransform: "uppercase", marginBottom: "6px", color: "var(--muted)" }}>
                  Monthly Budget (USD)
                </label>
                <input
                  type="number"
                  value={newBudget}
                  onChange={(e) => setNewBudget(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    fontSize: "13px",
                    background: "var(--panel-inner)",
                    border: "1px solid var(--border)",
                    color: "var(--ink)",
                    fontFamily: "'IBM Plex Mono', monospace",
                  }}
                  required
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
                <button
                  type="button"
                  onClick={() => setIsEditingBudget(false)}
                  className="btn"
                  style={{ padding: "6px 12px", fontSize: "11px", background: "var(--panel-inner)", border: "1px solid var(--border)" }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-secondary"
                  style={{ padding: "6px 16px", fontSize: "11px", fontWeight: 700, background: "var(--accent)", color: "#fff" }}
                >
                  Save Budget
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
