"use client";

import { useEffect, useState, useCallback } from "react";
import { get, post } from "@/lib/api";

interface ChangeLogItem {
  id: string;
  website_id: string;
  title: string;
  action_type: string;
  target_url: string;
  before_content: string;
  after_content: string;
  ymyl_risk: "low" | "medium" | "high";
  ymyl_notes: string;
  applied_at: string;
  can_rollback: boolean;
  rolled_back: boolean;
  rolled_back_at?: string;
  author: string;
}

interface ChangelogResponse {
  website_id: string;
  total_changes: number;
  changes: ChangeLogItem[];
}

interface ChangelogRollbackCardProps {
  websiteId: string;
  refreshTrigger?: number;
  onRollbackComplete?: () => void;
}

export function ChangelogRollbackCard({
  websiteId,
  refreshTrigger,
  onRollbackComplete,
}: ChangelogRollbackCardProps) {
  const [data, setData] = useState<ChangelogResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rollingBackId, setRollingBackId] = useState<string | null>(null);
  const [selectedChange, setSelectedChange] = useState<ChangeLogItem | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const fetchChangelog = useCallback(async () => {
    if (!websiteId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await get(`/api/guardrails/${websiteId}/changelog`);
      setData(res);
    } catch (err: any) {
      setError(err?.message || "Failed to load change log");
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  useEffect(() => {
    fetchChangelog();
  }, [fetchChangelog, refreshTrigger]);

  const handleRollback = async (change: ChangeLogItem) => {
    if (!confirm(`Are you sure you want to rollback "${change.title}" on ${change.target_url}?`)) {
      return;
    }

    setRollingBackId(change.id);
    setStatusMessage(null);
    try {
      const res = await post(`/api/guardrails/change/${change.id}/rollback`, {});
      setStatusMessage(res.message || `Successfully rolled back ${change.title}`);
      fetchChangelog();
      if (onRollbackComplete) {
        onRollbackComplete();
      }
      if (selectedChange?.id === change.id) {
        setSelectedChange(null);
      }
    } catch (err: any) {
      alert(`Rollback failed: ${err?.message || "Internal error"}`);
    } finally {
      setRollingBackId(null);
    }
  };

  return (
    <div className="panel" style={{ marginBottom: "24px" }}>
      <div className="panel-head" style={{ flexWrap: "wrap", gap: "10px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontSize: "18px" }}>🛡️</span>
          <span className="panel-label" style={{ fontSize: "12px", fontWeight: 700, color: "var(--ink)" }}>
            Guardrails & 1-Click Rollback Audit
          </span>
          <span className="badge badge-accent">YMYL Protected</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button
            onClick={fetchChangelog}
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
            🔄 Refresh Audit Log
          </button>
        </div>
      </div>

      <div className="panel-body" style={{ padding: "16px" }}>
        {statusMessage && (
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
            <span>✅ {statusMessage}</span>
            <button
              onClick={() => setStatusMessage(null)}
              style={{ background: "none", border: "none", color: "var(--green)", cursor: "pointer" }}
            >
              ✕
            </button>
          </div>
        )}

        {error && (
          <div style={{ padding: "10px", background: "rgba(239, 68, 68, 0.1)", border: "1px solid var(--red)", color: "var(--red)", fontSize: "11.5px", marginBottom: "12px" }}>
            ⚠️ {error}
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {loading && (!data?.changes || data.changes.length === 0) ? (
            <div style={{ padding: "24px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              Loading audit changelog...
            </div>
          ) : !data?.changes || data.changes.length === 0 ? (
            <div style={{ padding: "24px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              No automated live site changes recorded yet. Every change executed will appear here with rollback safety.
            </div>
          ) : (
            data.changes.map((item) => {
              const isRollingBack = rollingBackId === item.id;
              const ymylColor =
                item.ymyl_risk === "low"
                  ? "var(--green)"
                  : item.ymyl_risk === "medium"
                  ? "var(--amber)"
                  : "var(--red)";

              return (
                <div
                  key={item.id}
                  style={{
                    padding: "12px 14px",
                    background: item.rolled_back ? "rgba(239, 68, 68, 0.03)" : "var(--panel-inner)",
                    border: `1px solid ${item.rolled_back ? "rgba(239, 68, 68, 0.2)" : "var(--line)"}`,
                    borderRadius: "4px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "10px" }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span style={{ fontWeight: 700, fontSize: "12.5px", color: "var(--ink)" }}>
                          {item.title}
                        </span>
                        {item.rolled_back ? (
                          <span
                            style={{
                              padding: "2px 6px",
                              background: "rgba(239, 68, 68, 0.15)",
                              color: "var(--red)",
                              fontSize: "9px",
                              fontWeight: 700,
                              borderRadius: "2px",
                            }}
                          >
                            ROLLED BACK
                          </span>
                        ) : (
                          <span
                            style={{
                              padding: "2px 6px",
                              background: "rgba(34, 197, 94, 0.15)",
                              color: "var(--green)",
                              fontSize: "9px",
                              fontWeight: 700,
                              borderRadius: "2px",
                            }}
                          >
                            LIVE ON SITE
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: "10.5px", color: "var(--muted)", marginTop: "2px" }}>
                        <span>Target: </span>
                        <code style={{ color: "var(--ink)" }}>{item.target_url}</code>
                        <span style={{ marginLeft: "10px" }}>By: {item.author} · {item.applied_at.split("T")[0]}</span>
                      </div>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span
                        style={{
                          padding: "2px 6px",
                          border: `1px solid ${ymylColor}`,
                          color: ymylColor,
                          fontSize: "9px",
                          fontWeight: 700,
                          borderRadius: "2px",
                        }}
                      >
                        YMYL: {item.ymyl_risk.toUpperCase()}
                      </span>

                      <button
                        onClick={() => setSelectedChange(item)}
                        className="btn"
                        style={{
                          padding: "4px 8px",
                          fontSize: "10px",
                          background: "var(--panel-inner)",
                          border: "1px solid var(--border)",
                          cursor: "pointer",
                        }}
                      >
                        👁️ Diff
                      </button>

                      {item.can_rollback && !item.rolled_back && (
                        <button
                          onClick={() => handleRollback(item)}
                          disabled={isRollingBack}
                          className="btn"
                          style={{
                            padding: "4px 10px",
                            fontSize: "10px",
                            fontWeight: 700,
                            background: "rgba(239, 68, 68, 0.1)",
                            color: "var(--red)",
                            border: "1px solid var(--red)",
                            cursor: isRollingBack ? "not-allowed" : "pointer",
                          }}
                        >
                          {isRollingBack ? "Rolling back..." : "↩️ Undo / Rollback"}
                        </button>
                      )}
                    </div>
                  </div>

                  {item.ymyl_notes && (
                    <div style={{ fontSize: "10px", color: "var(--muted)", background: "var(--bg)", padding: "6px 8px", borderRadius: "2px" }}>
                      🛡️ <strong>Safety Analysis:</strong> {item.ymyl_notes}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* VIEW DIFF MODAL */}
      {selectedChange && (
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
              maxWidth: "800px",
              maxHeight: "90vh",
              overflowY: "auto",
              background: "var(--bg)",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              padding: "20px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px", borderBottom: "1px solid var(--border)", paddingBottom: "10px" }}>
              <div>
                <div style={{ fontSize: "14px", fontWeight: 700, color: "var(--ink)" }}>
                  Audit Diff: {selectedChange.title}
                </div>
                <div style={{ fontSize: "11px", color: "var(--muted)" }}>
                  {selectedChange.target_url} · Applied {selectedChange.applied_at}
                </div>
              </div>
              <button
                onClick={() => setSelectedChange(null)}
                style={{ background: "none", border: "none", fontSize: "18px", color: "var(--muted)", cursor: "pointer" }}
              >
                ✕
              </button>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "16px" }}>
              <div>
                <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--red)", marginBottom: "4px" }}>
                  - BEFORE (Original Live State)
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
                    minHeight: "140px",
                  }}
                >
                  {selectedChange.before_content}
                </pre>
              </div>

              <div>
                <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--green)", marginBottom: "4px" }}>
                  + AFTER (Applied Modification)
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
                    minHeight: "140px",
                  }}
                >
                  {selectedChange.after_content}
                </pre>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ fontSize: "11px", color: "var(--muted)" }}>
                Status: {selectedChange.rolled_back ? "Rolled Back" : "Currently Active"}
              </div>
              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  onClick={() => setSelectedChange(null)}
                  className="btn"
                  style={{ padding: "6px 12px", fontSize: "11px", background: "var(--panel-inner)", border: "1px solid var(--border)" }}
                >
                  Close
                </button>
                {selectedChange.can_rollback && !selectedChange.rolled_back && (
                  <button
                    onClick={() => handleRollback(selectedChange)}
                    disabled={rollingBackId === selectedChange.id}
                    className="btn"
                    style={{
                      padding: "6px 14px",
                      fontSize: "11px",
                      fontWeight: 700,
                      background: "rgba(239, 68, 68, 0.15)",
                      color: "var(--red)",
                      border: "1px solid var(--red)",
                      cursor: "pointer",
                    }}
                  >
                    ↩️ 1-Click Rollback Live Change
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
