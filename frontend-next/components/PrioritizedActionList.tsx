"use client";

import { useEffect, useState, useCallback } from "react";
import { get, post } from "@/lib/api";

interface ActionItem {
  id: string;
  website_id: string;
  rank: number;
  title: string;
  description: string;
  category: string;
  impact: string;
  estimated_monthly_clicks_gain: number;
  difficulty: string;
  status: "pending" | "executed" | "dismissed";
  action_type: string;
  target_url: string;
  preview_diff?: {
    before: string;
    after: string;
    summary: string;
    ymyl_compliant: boolean;
    risk_level: string;
  };
  created_at?: string;
}

interface ActionsResponse {
  website_id: string;
  total_potential_traffic_gain: number;
  actions: ActionItem[];
}

interface PrioritizedActionListProps {
  websiteId: string;
  onActionExecuted?: () => void;
}

export function PrioritizedActionList({ websiteId, onActionExecuted }: PrioritizedActionListProps) {
  const [data, setData] = useState<ActionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [executingId, setExecutingId] = useState<string | null>(null);
  const [previewAction, setPreviewAction] = useState<ActionItem | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const fetchActions = useCallback(async () => {
    if (!websiteId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await get(`/api/actions/${websiteId}/top-10`);
      setData(res);
    } catch (err: any) {
      setError(err?.message || "Failed to load prioritized actions");
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  useEffect(() => {
    fetchActions();
  }, [fetchActions]);

  const handleExecute = async (action: ActionItem) => {
    if (!websiteId) return;
    setExecutingId(action.id);
    setSuccessMessage(null);
    try {
      const res = await post(`/api/actions/${websiteId}/${action.id}/execute`, {});
      setSuccessMessage(res.message || `Successfully executed: ${action.title}`);

      // Optimistically update status
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          actions: prev.actions.map((a) => (a.id === action.id ? { ...a, status: "executed" } : a)),
        };
      });

      if (previewAction?.id === action.id) {
        setPreviewAction(null);
      }

      if (onActionExecuted) {
        onActionExecuted();
      }
    } catch (err: any) {
      alert(`Execution failed: ${err?.message || "Internal error"}`);
    } finally {
      setExecutingId(null);
    }
  };

  const handleDismiss = async (actionId: string) => {
    if (!websiteId) return;
    try {
      await post(`/api/actions/${websiteId}/${actionId}/dismiss`, {});
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          actions: prev.actions.filter((a) => a.id !== actionId),
        };
      });
      if (previewAction?.id === actionId) {
        setPreviewAction(null);
      }
    } catch (err: any) {
      alert(`Failed to dismiss: ${err?.message || "Internal error"}`);
    }
  };

  return (
    <div className="panel" style={{ marginBottom: "24px" }}>
      <div className="panel-head" style={{ flexWrap: "wrap", gap: "10px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontSize: "18px" }}>🎯</span>
          <span className="panel-label" style={{ fontSize: "12px", fontWeight: 700, color: "var(--ink)" }}>
            Ranked Priority Engine
          </span>
          <span className="badge badge-accent">Top 10 Actions</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ fontSize: "11px", color: "var(--green)", fontWeight: 700 }}>
            ⚡ +{data?.total_potential_traffic_gain?.toLocaleString() || 0} Estimated Clicks/Mo
          </div>
          <button
            onClick={fetchActions}
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
            {loading ? "Refreshing..." : "Recalculate"}
          </button>
        </div>
      </div>

      <div className="panel-body" style={{ padding: "16px" }}>
        {/* SUCCESS NOTIFICATION */}
        {successMessage && (
          <div
            style={{
              padding: "10px 14px",
              background: "rgba(34, 197, 94, 0.12)",
              border: "1px solid var(--green)",
              color: "var(--green)",
              fontSize: "11.5px",
              borderRadius: "3px",
              marginBottom: "14px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span>✅ {successMessage} (Logged to Audit Diff & Tracking 28d ROI)</span>
            <button
              onClick={() => setSuccessMessage(null)}
              style={{ background: "none", border: "none", color: "var(--green)", cursor: "pointer", fontSize: "13px" }}
            >
              ✕
            </button>
          </div>
        )}

        {/* ERROR STATE */}
        {error && (
          <div
            style={{
              padding: "12px",
              background: "rgba(239, 68, 68, 0.1)",
              border: "1px solid var(--red)",
              color: "var(--red)",
              fontSize: "12px",
              marginBottom: "14px",
            }}
          >
            ⚠️ {error}
          </div>
        )}

        {/* ACTION ITEMS LIST */}
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {loading && (!data?.actions || data.actions.length === 0) ? (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              Analyzing site signals and ranking top 10 impactful actions...
            </div>
          ) : !data?.actions || data.actions.length === 0 ? (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              No pending actions. Your site is fully optimized!
            </div>
          ) : (
            data.actions.map((action) => {
              const isExecuted = action.status === "executed";
              const isExecuting = executingId === action.id;

              const difficultyColor =
                action.difficulty === "EASY"
                  ? "var(--green)"
                  : action.difficulty === "MEDIUM"
                  ? "var(--amber)"
                  : "var(--red)";

              return (
                <div
                  key={action.id}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                    padding: "14px",
                    background: isExecuted ? "rgba(34, 197, 94, 0.04)" : "var(--panel-inner)",
                    border: `1px solid ${isExecuted ? "rgba(34, 197, 94, 0.3)" : "var(--line)"}`,
                    borderRadius: "4px",
                    transition: "all 0.2s ease",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <span
                        style={{
                          width: "24px",
                          height: "24px",
                          background: isExecuted ? "var(--green)" : "var(--accent)",
                          color: "#fff",
                          fontSize: "11px",
                          fontWeight: 700,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          borderRadius: "2px",
                        }}
                      >
                        #{action.rank}
                      </span>
                      <div>
                        <div style={{ fontSize: "13px", fontWeight: 700, color: "var(--ink)" }}>
                          {action.title}
                          {isExecuted && (
                            <span
                              style={{
                                marginLeft: "8px",
                                padding: "2px 6px",
                                background: "rgba(34, 197, 94, 0.2)",
                                color: "var(--green)",
                                fontSize: "9.5px",
                                borderRadius: "2px",
                              }}
                            >
                              ✓ SHIPPED
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: "11px", color: "var(--muted)", marginTop: "2px" }}>
                          {action.description}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "8px", flexShrink: 0 }}>
                      <span
                        style={{
                          padding: "3px 8px",
                          background: "rgba(34, 197, 94, 0.12)",
                          color: "var(--green)",
                          fontSize: "10.5px",
                          fontWeight: 700,
                          borderRadius: "3px",
                        }}
                      >
                        +{action.estimated_monthly_clicks_gain} clicks/mo
                      </span>

                      <span
                        style={{
                          padding: "3px 7px",
                          border: `1px solid ${difficultyColor}`,
                          color: difficultyColor,
                          fontSize: "9.5px",
                          fontWeight: 600,
                          borderRadius: "2px",
                        }}
                      >
                        {action.difficulty}
                      </span>
                    </div>
                  </div>

                  {/* TARGET URL AND BUTTONS */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      flexWrap: "wrap",
                      gap: "8px",
                      marginTop: "4px",
                      paddingTop: "8px",
                      borderTop: "1px dashed var(--line)",
                    }}
                  >
                    <div style={{ fontSize: "10.5px", color: "var(--muted)", display: "flex", alignItems: "center", gap: "6px" }}>
                      <span>🔗 Target:</span>
                      <code style={{ color: "var(--ink)", background: "var(--bg)", padding: "2px 5px", borderRadius: "2px" }}>
                        {action.target_url}
                      </code>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      {action.preview_diff && (
                        <button
                          onClick={() => setPreviewAction(action)}
                          className="btn"
                          style={{
                            padding: "4px 8px",
                            fontSize: "10px",
                            background: "var(--panel-inner)",
                            border: "1px solid var(--border)",
                            color: "var(--ink)",
                            cursor: "pointer",
                          }}
                        >
                          👁️ Preview Diff
                        </button>
                      )}

                      {!isExecuted ? (
                        <>
                          <button
                            onClick={() => handleExecute(action)}
                            disabled={isExecuting}
                            className="btn btn-secondary"
                            style={{
                              padding: "5px 12px",
                              fontSize: "10.5px",
                              fontWeight: 700,
                              background: "var(--accent)",
                              color: "#fff",
                              border: "1px solid var(--accent)",
                              cursor: isExecuting ? "not-allowed" : "pointer",
                            }}
                          >
                            {isExecuting ? "Executing..." : "⚡ Execute Fix"}
                          </button>
                          <button
                            onClick={() => handleDismiss(action.id)}
                            style={{
                              padding: "4px 8px",
                              fontSize: "10px",
                              background: "transparent",
                              border: "none",
                              color: "var(--muted)",
                              cursor: "pointer",
                            }}
                          >
                            Dismiss
                          </button>
                        </>
                      ) : (
                        <span style={{ fontSize: "10.5px", color: "var(--green)" }}>
                          ⚡ Fix Active & Monitored
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* PREVIEW DIFF MODAL */}
      {previewAction && previewAction.preview_diff && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0, 0, 0, 0.7)",
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
              maxWidth: "750px",
              maxHeight: "90vh",
              overflowY: "auto",
              background: "var(--bg)",
              border: "1px solid var(--border)",
              boxShadow: "0 10px 40px rgba(0, 0, 0, 0.4)",
              borderRadius: "4px",
            }}
          >
            <div
              style={{
                padding: "14px 18px",
                borderBottom: "1px solid var(--border)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                background: "var(--panel-bg)",
              }}
            >
              <div>
                <div style={{ fontSize: "13px", fontWeight: 700, color: "var(--ink)" }}>
                  Change Guardrail & Code Diff Preview
                </div>
                <div style={{ fontSize: "11px", color: "var(--muted)" }}>
                  {previewAction.title}
                </div>
              </div>
              <button
                onClick={() => setPreviewAction(null)}
                style={{
                  background: "transparent",
                  border: "none",
                  fontSize: "16px",
                  color: "var(--muted)",
                  cursor: "pointer",
                }}
              >
                ✕
              </button>
            </div>

            <div style={{ padding: "18px" }}>
              {/* YMYL & SAFETY BADGE */}
              <div
                style={{
                  padding: "10px 14px",
                  background: previewAction.preview_diff.ymyl_compliant ? "rgba(34, 197, 94, 0.1)" : "rgba(245, 158, 11, 0.1)",
                  border: `1px solid ${previewAction.preview_diff.ymyl_compliant ? "var(--green)" : "var(--amber)"}`,
                  borderRadius: "3px",
                  marginBottom: "16px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <div>
                  <div style={{ fontWeight: 700, fontSize: "11.5px", color: previewAction.preview_diff.ymyl_compliant ? "var(--green)" : "var(--amber)" }}>
                    🛡️ YMYL Safety & Accuracy Check: {previewAction.preview_diff.ymyl_compliant ? "PASSED" : "CAUTION"}
                  </div>
                  <div style={{ fontSize: "10px", color: "var(--muted)", marginTop: "2px" }}>
                    Risk Level: {previewAction.preview_diff.risk_level.toUpperCase()} · Auto-rollback enabled upon execution
                  </div>
                </div>
                <span
                  style={{
                    padding: "2px 8px",
                    background: previewAction.preview_diff.ymyl_compliant ? "var(--green)" : "var(--amber)",
                    color: "#fff",
                    fontSize: "9.5px",
                    fontWeight: 700,
                    borderRadius: "2px",
                  }}
                >
                  {previewAction.preview_diff.risk_level}
                </span>
              </div>

              {/* SUMMARY */}
              <div style={{ marginBottom: "16px", fontSize: "11.5px", color: "var(--ink)" }}>
                <strong>Impact Summary:</strong> {previewAction.preview_diff.summary}
              </div>

              {/* BEFORE VS AFTER DIFF */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "20px" }}>
                <div>
                  <div style={{ fontSize: "10.5px", fontWeight: 700, color: "var(--red)", marginBottom: "4px" }}>
                    - BEFORE (CURRENT LIVE)
                  </div>
                  <pre
                    style={{
                      background: "rgba(239, 68, 68, 0.05)",
                      border: "1px solid rgba(239, 68, 68, 0.2)",
                      padding: "10px",
                      fontSize: "11px",
                      fontFamily: "'IBM Plex Mono', monospace",
                      overflowX: "auto",
                      whiteSpace: "pre-wrap",
                      color: "var(--ink)",
                      minHeight: "120px",
                    }}
                  >
                    {previewAction.preview_diff.before}
                  </pre>
                </div>

                <div>
                  <div style={{ fontSize: "10.5px", fontWeight: 700, color: "var(--green)", marginBottom: "4px" }}>
                    + AFTER (PROPOSED MODIFICATION)
                  </div>
                  <pre
                    style={{
                      background: "rgba(34, 197, 94, 0.05)",
                      border: "1px solid rgba(34, 197, 94, 0.2)",
                      padding: "10px",
                      fontSize: "11px",
                      fontFamily: "'IBM Plex Mono', monospace",
                      overflowX: "auto",
                      whiteSpace: "pre-wrap",
                      color: "var(--ink)",
                      minHeight: "120px",
                    }}
                  >
                    {previewAction.preview_diff.after}
                  </pre>
                </div>
              </div>

              {/* MODAL FOOTER */}
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                <button
                  onClick={() => setPreviewAction(null)}
                  className="btn"
                  style={{
                    padding: "6px 14px",
                    fontSize: "11px",
                    background: "var(--panel-inner)",
                    border: "1px solid var(--border)",
                    color: "var(--ink)",
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
                <button
                  onClick={() => handleExecute(previewAction)}
                  disabled={executingId === previewAction.id}
                  className="btn btn-secondary"
                  style={{
                    padding: "6px 16px",
                    fontSize: "11px",
                    fontWeight: 700,
                    background: "var(--accent)",
                    color: "#fff",
                    border: "1px solid var(--accent)",
                    cursor: "pointer",
                  }}
                >
                  {executingId === previewAction.id ? "Executing..." : "Confirm & Ship to Live"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
