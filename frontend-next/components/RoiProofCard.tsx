"use client";

import { useEffect, useState, useCallback } from "react";
import { get, post } from "@/lib/api";

interface Milestone {
  day: number;
  measured: boolean;
  position: number | null;
  clicks: number | null;
}

interface TrackedFix {
  id: string;
  website_id: string;
  target_url: string;
  fix_title: string;
  category: string;
  target_keyword: string;
  baseline_position: number;
  baseline_monthly_clicks: number;
  current_position: number;
  current_monthly_clicks: number;
  position_lift: number;
  traffic_lift_clicks: number;
  traffic_lift_percentage: number;
  monthly_value_generated: number;
  shipped_at: string;
  days_tracked: number;
  status: "PROVEN_LIFT" | "TRACKING" | "NO_LIFT";
  milestones: Milestone[];
}

interface RoiSummary {
  website_id: string;
  total_fixes_tracked: number;
  proven_fixes_count: number;
  total_monthly_clicks_won: number;
  average_position_lift: number;
  monthly_value_generated: number;
  monthly_seo_spend: number;
  roi_multiple: string;
  conclusion: string;
}

interface RoiProofCardProps {
  websiteId: string;
}

export function RoiProofCard({ websiteId }: RoiProofCardProps) {
  const [fixes, setFixes] = useState<TrackedFix[]>([]);
  const [summary, setSummary] = useState<RoiSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add Fix Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [targetUrl, setTargetUrl] = useState("");
  const [fixTitle, setFixTitle] = useState("");
  const [category, setCategory] = useState("TECHNICAL_SEO");
  const [targetKeyword, setTargetKeyword] = useState("");
  const [baselinePos, setBaselinePos] = useState("12.0");
  const [baselineClicks, setBaselineClicks] = useState("250");

  const fetchData = useCallback(async () => {
    if (!websiteId) return;
    setLoading(true);
    setError(null);
    try {
      const [listRes, sumRes] = await Promise.all([
        get(`/api/roi-proof/${websiteId}/proof-list`),
        get(`/api/roi-proof/${websiteId}/summary`),
      ]);
      setFixes(listRes.tracked_fixes || []);
      setSummary(sumRes);
    } catch (err: any) {
      setError(err?.message || "Failed to load ROI proof data.");
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleTrackNewFix = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!websiteId || !targetUrl.trim() || !fixTitle.trim()) return;
    setSubmitting(true);
    try {
      await post(`/api/roi-proof/${websiteId}/track`, {
        target_url: targetUrl.trim(),
        fix_title: fixTitle.trim(),
        category,
        target_keyword: targetKeyword.trim() || "organic search term",
        baseline_position: parseFloat(baselinePos) || 12.0,
        baseline_monthly_clicks: parseInt(baselineClicks, 10) || 100,
      });

      setTargetUrl("");
      setFixTitle("");
      setTargetKeyword("");
      setIsModalOpen(false);
      fetchData();
    } catch (err: any) {
      alert(`Failed to track fix: ${err?.message || "Error"}`);
    } finally {
      setSubmitting(false);
    }
  };

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
              background: "rgba(16, 185, 129, 0.15)",
              border: "1px solid rgba(16, 185, 129, 0.3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "16px",
            }}
          >
            📈
          </div>
          <div>
            <h2 className="panel-title" style={{ margin: 0, fontSize: "16px" }}>
              28-Day Post-Fix Impact & ROI Proof
            </h2>
            <div style={{ fontSize: "12px", color: "var(--muted)", marginTop: "2px" }}>
              Empirical ROI validation: Automated 28-day tracking of position lift, clicks won, and pipeline value
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button
            onClick={() => setIsModalOpen(true)}
            className="btn btn-primary"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "12px",
              padding: "6px 14px",
            }}
          >
            <span>+</span> Track Shipped Fix
          </button>
          <button
            onClick={fetchData}
            disabled={loading}
            className="btn btn-secondary"
            style={{ fontSize: "12px", padding: "6px 12px" }}
            title="Refresh 28-Day Proof Measurements"
          >
            {loading ? "Measuring..." : "↻ Refresh"}
          </button>
        </div>
      </div>

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
            Querying post-fix search console telemetry and measuring 28-day lift...
          </div>
        ) : (
          <>
            {/* KPI Cards Row */}
            {summary && (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                  gap: "12px",
                  marginBottom: "16px",
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
                    Verified Fixes
                  </div>
                  <div
                    style={{
                      fontSize: "24px",
                      fontWeight: 700,
                      color: "var(--green)",
                      margin: "4px 0",
                      fontFamily: "'DotGothic16', monospace",
                    }}
                  >
                    {summary.proven_fixes_count} / {summary.total_fixes_tracked}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--muted)" }}>Proven positive rank & traffic</div>
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
                    Total Clicks Won
                  </div>
                  <div
                    style={{
                      fontSize: "24px",
                      fontWeight: 700,
                      color: "var(--green)",
                      margin: "4px 0",
                      fontFamily: "'DotGothic16', monospace",
                    }}
                  >
                    +{summary.total_monthly_clicks_won.toLocaleString()}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--muted)" }}>Incremental organic visits/mo</div>
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
                    Avg. Position Lift
                  </div>
                  <div
                    style={{
                      fontSize: "24px",
                      fontWeight: 700,
                      color: "var(--accent)",
                      margin: "4px 0",
                      fontFamily: "'DotGothic16', monospace",
                    }}
                  >
                    +{summary.average_position_lift} pos
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--muted)" }}>Average SERP elevation</div>
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
                    Pipeline Generated
                  </div>
                  <div
                    style={{
                      fontSize: "24px",
                      fontWeight: 700,
                      color: "var(--ink)",
                      margin: "4px 0",
                      fontFamily: "'DotGothic16', monospace",
                    }}
                  >
                    ${summary.monthly_value_generated.toLocaleString()}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--muted)" }}>Monthly commercial lift</div>
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
                    SEO Budget Multiple
                  </div>
                  <div
                    style={{
                      fontSize: "24px",
                      fontWeight: 700,
                      color: "var(--amber)",
                      margin: "4px 0",
                      fontFamily: "'DotGothic16', monospace",
                    }}
                  >
                    {summary.roi_multiple}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--muted)" }}>Return on SEO spend</div>
                </div>
              </div>
            )}

            {/* Evidence Callout Banner */}
            {summary && (
              <div
                style={{
                  background: "rgba(16, 185, 129, 0.08)",
                  border: "1px solid rgba(16, 185, 129, 0.25)",
                  borderRadius: "8px",
                  padding: "12px 16px",
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  marginBottom: "20px",
                }}
              >
                <span style={{ fontSize: "20px" }}>🛡️</span>
                <div style={{ fontSize: "13px", color: "var(--ink)", lineHeight: 1.5 }}>
                  <strong>Client ROI Proof Statement: </strong>
                  {summary.conclusion}
                </div>
              </div>
            )}

            {/* Tracked Fixes Table */}
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
                    <th style={{ padding: "8px 12px" }}>Remediation & URL</th>
                    <th style={{ padding: "8px 12px" }}>Target Query</th>
                    <th style={{ padding: "8px 12px" }}>SERP Lift</th>
                    <th style={{ padding: "8px 12px" }}>Traffic Gain</th>
                    <th style={{ padding: "8px 12px" }}>28-Day Milestones</th>
                    <th style={{ padding: "8px 12px" }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {fixes.map((fix) => (
                    <tr
                      key={fix.id}
                      style={{
                        borderBottom: "1px solid var(--line)",
                      }}
                    >
                      <td style={{ padding: "12px", maxWidth: "300px" }}>
                        <div style={{ fontWeight: 600, color: "var(--ink)", marginBottom: "4px" }}>
                          {fix.fix_title}
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <span
                            style={{
                              fontSize: "10px",
                              padding: "2px 6px",
                              borderRadius: "4px",
                              background: "var(--panel-inner)",
                              color: "var(--muted)",
                              fontFamily: "monospace",
                            }}
                          >
                            {fix.category}
                          </span>
                          <span
                            style={{
                              fontSize: "11px",
                              color: "var(--muted)",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                              maxWidth: "180px",
                            }}
                            title={fix.target_url}
                          >
                            {fix.target_url}
                          </span>
                        </div>
                      </td>

                      <td style={{ padding: "12px" }}>
                        <div style={{ fontWeight: 500 }}>{fix.target_keyword}</div>
                        <div style={{ fontSize: "11px", color: "var(--muted)" }}>
                          Tracked: {fix.days_tracked} of 28 days
                        </div>
                      </td>

                      <td style={{ padding: "12px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <span style={{ color: "var(--muted)", fontSize: "12px" }}>#{fix.baseline_position}</span>
                          <span style={{ color: "var(--muted)" }}>→</span>
                          <span style={{ fontWeight: 700, color: "var(--green)", fontSize: "13px" }}>
                            #{fix.current_position}
                          </span>
                        </div>
                        <span
                          style={{
                            fontSize: "10px",
                            fontWeight: 700,
                            padding: "2px 6px",
                            borderRadius: "4px",
                            background: "rgba(16, 185, 129, 0.15)",
                            color: "var(--green)",
                            display: "inline-block",
                            marginTop: "2px",
                          }}
                        >
                          +{fix.position_lift} pos lift
                        </span>
                      </td>

                      <td style={{ padding: "12px" }}>
                        <div style={{ fontWeight: 700, color: "var(--green)" }}>
                          +{fix.traffic_lift_clicks.toLocaleString()} clicks/mo
                        </div>
                        <div style={{ fontSize: "11px", color: "var(--muted)" }}>
                          +{fix.traffic_lift_percentage}% lift (${fix.monthly_value_generated.toLocaleString()}/mo)
                        </div>
                      </td>

                      {/* 28-day Milestones (Days 7, 14, 21, 28) */}
                      <td style={{ padding: "12px" }}>
                        <div style={{ display: "flex", gap: "6px" }}>
                          {fix.milestones.map((m) => (
                            <div
                              key={m.day}
                              title={
                                m.measured
                                  ? `Day ${m.day}: Rank #${m.position}, ${m.clicks} clicks`
                                  : `Day ${m.day}: Measurement pending`
                              }
                              style={{
                                padding: "4px 6px",
                                borderRadius: "4px",
                                border: m.measured ? "1px solid rgba(16, 185, 129, 0.4)" : "1px solid var(--line)",
                                background: m.measured ? "rgba(16, 185, 129, 0.1)" : "var(--panel-inner)",
                                textAlign: "center",
                                minWidth: "42px",
                              }}
                            >
                              <div style={{ fontSize: "9px", color: "var(--muted)" }}>D{m.day}</div>
                              <div
                                style={{
                                  fontSize: "11px",
                                  fontWeight: 600,
                                  color: m.measured ? "var(--green)" : "var(--muted)",
                                }}
                              >
                                {m.measured ? `#${m.position}` : "⏳"}
                              </div>
                            </div>
                          ))}
                        </div>
                      </td>

                      <td style={{ padding: "12px" }}>
                        <span
                          style={{
                            fontSize: "11px",
                            fontWeight: 700,
                            padding: "3px 8px",
                            borderRadius: "4px",
                            background:
                              fix.status === "PROVEN_LIFT"
                                ? "rgba(16, 185, 129, 0.15)"
                                : "rgba(59, 130, 246, 0.15)",
                            color: fix.status === "PROVEN_LIFT" ? "var(--green)" : "var(--accent)",
                            border:
                              fix.status === "PROVEN_LIFT"
                                ? "1px solid rgba(16, 185, 129, 0.3)"
                                : "1px solid rgba(59, 130, 246, 0.3)",
                          }}
                        >
                          {fix.status === "PROVEN_LIFT" ? "✓ PROVEN LIFT" : "⏳ TRACKING"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {/* Track New Fix Modal */}
      {isModalOpen && (
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
              maxWidth: "500px",
              padding: "24px",
              boxShadow: "0 20px 40px rgba(0, 0, 0, 0.5)",
            }}
          >
            <h3 style={{ margin: "0 0 8px 0", fontSize: "18px" }}>Track New Shipped Fix</h3>
            <p style={{ margin: "0 0 16px 0", fontSize: "13px", color: "var(--muted)" }}>
              Register a recently deployed SEO fix or URL change to automatically benchmark it for 28 days.
            </p>

            <form onSubmit={handleTrackNewFix}>
              <div style={{ marginBottom: "12px" }}>
                <label style={{ display: "block", fontSize: "12px", color: "var(--muted)", marginBottom: "4px" }}>
                  Target Page URL *
                </label>
                <input
                  type="text"
                  required
                  placeholder="https://mysite.com/services/enterprise"
                  value={targetUrl}
                  onChange={(e) => setTargetUrl(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    background: "var(--panel-inner)",
                    border: "1px solid var(--line)",
                    color: "var(--ink)",
                    borderRadius: "6px",
                    fontSize: "13px",
                  }}
                />
              </div>

              <div style={{ marginBottom: "12px" }}>
                <label style={{ display: "block", fontSize: "12px", color: "var(--muted)", marginBottom: "4px" }}>
                  Fix Title / Summary *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Injected Product JSON-LD Schema + Optimized H1"
                  value={fixTitle}
                  onChange={(e) => setFixTitle(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    background: "var(--panel-inner)",
                    border: "1px solid var(--line)",
                    color: "var(--ink)",
                    borderRadius: "6px",
                    fontSize: "13px",
                  }}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "12px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "12px", color: "var(--muted)", marginBottom: "4px" }}>
                    Category
                  </label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      background: "var(--panel-inner)",
                      border: "1px solid var(--line)",
                      color: "var(--ink)",
                      borderRadius: "6px",
                      fontSize: "13px",
                    }}
                  >
                    <option value="TECHNICAL_SEO">Technical SEO</option>
                    <option value="CTR_OPTIMIZATION">CTR Optimization</option>
                    <option value="CANNIBALIZATION">Cannibalization</option>
                    <option value="SCHEMA_MARKUP">Schema Markup</option>
                    <option value="CONTENT_REFRESH">Content Refresh</option>
                    <option value="YMYL_EAT">YMYL / E-E-A-T</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "12px", color: "var(--muted)", marginBottom: "4px" }}>
                    Target Keyword
                  </label>
                  <input
                    type="text"
                    placeholder="enterprise seo suite"
                    value={targetKeyword}
                    onChange={(e) => setTargetKeyword(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      background: "var(--panel-inner)",
                      border: "1px solid var(--line)",
                      color: "var(--ink)",
                      borderRadius: "6px",
                      fontSize: "13px",
                    }}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "20px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "12px", color: "var(--muted)", marginBottom: "4px" }}>
                    Baseline Position (Pre-Fix)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    value={baselinePos}
                    onChange={(e) => setBaselinePos(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      background: "var(--panel-inner)",
                      border: "1px solid var(--line)",
                      color: "var(--ink)",
                      borderRadius: "6px",
                      fontSize: "13px",
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "12px", color: "var(--muted)", marginBottom: "4px" }}>
                    Baseline Monthly Clicks
                  </label>
                  <input
                    type="number"
                    value={baselineClicks}
                    onChange={(e) => setBaselineClicks(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      background: "var(--panel-inner)",
                      border: "1px solid var(--line)",
                      color: "var(--ink)",
                      borderRadius: "6px",
                      fontSize: "13px",
                    }}
                  />
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
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
                  {submitting ? "Registering..." : "Start 28-Day Tracking"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
