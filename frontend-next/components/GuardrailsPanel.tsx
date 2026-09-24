"use client";

/**
 * Guardrails and rollback.
 *
 * Every automated change to a live site goes through: preview diff -> human
 * approval -> apply -> undo if needed. YMYL (legal/medical/financial) changes
 * additionally require a distinct second reviewer, and the backend refuses to
 * apply them otherwise.
 */

import { useCallback, useEffect, useState } from "react";
import {
  ChangeEvent,
  ChangeLog,
  applyChange,
  fetchChangeLog,
  previewChange,
  undoChange,
} from "@/lib/intelligence";

interface Props {
  websiteId: string;
}

function DiffView({ diff }: { diff: string }) {
  return (
    <pre
      style={{
        margin: 0,
        padding: "10px 12px",
        background: "var(--surface)",
        border: "1px solid var(--line)",
        borderRadius: "3px",
        fontSize: "10.5px",
        fontFamily: "'IBM Plex Mono', monospace",
        lineHeight: 1.55,
        overflowX: "auto",
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      }}
    >
      {diff.split("\n").map((line, i) => {
        let color = "var(--ink)";
        let bg = "transparent";
        if (line.startsWith("+") && !line.startsWith("+++")) {
          color = "var(--green)";
          bg = "rgba(34,197,94,0.08)";
        } else if (line.startsWith("-") && !line.startsWith("---")) {
          color = "var(--red)";
          bg = "rgba(239,68,68,0.08)";
        } else if (line.startsWith("@@")) {
          color = "var(--muted)";
        }
        return (
          <div key={i} style={{ color, background: bg }}>
            {line || " "}
          </div>
        );
      })}
    </pre>
  );
}

export function GuardrailsPanel({ websiteId }: Props) {
  const [log, setLog] = useState<ChangeLog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // draft change form
  const [targetUrl, setTargetUrl] = useState("");
  const [beforeContent, setBeforeContent] = useState("");
  const [afterContent, setAfterContent] = useState("");
  const [actor, setActor] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [draft, setDraft] = useState<ChangeEvent | null>(null);

  const load = useCallback(async () => {
    if (!websiteId) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      setLog(await fetchChangeLog(websiteId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load change log");
      setLog(null);
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  useEffect(() => {
    load();
  }, [load]);

  const flash = (msg: string) => {
    setNotice(msg);
    setTimeout(() => setNotice(null), 5000);
  };

  const handlePreview = async () => {
    if (!targetUrl || !afterContent) {
      flash("Target URL and proposed content are required.");
      return;
    }
    try {
      setBusy("preview");
      setDraft(
        await previewChange(websiteId, {
          target_url: targetUrl,
          change_type: "content_update",
          before_content: beforeContent,
          after_content: afterContent,
          actor: actor || "operator",
        })
      );
    } catch (e) {
      flash(e instanceof Error ? e.message : "Preview failed");
    } finally {
      setBusy(null);
    }
  };

  const handleApply = async (change: ChangeEvent) => {
    if (!actor) {
      flash("Enter your name/email as the approver before applying.");
      return;
    }
    try {
      setBusy(change.id);
      await applyChange(change.id, {
        approver: actor,
        second_reviewer: reviewer || undefined,
      });
      flash("Change applied. A 28-day measurement window was opened.");
      setDraft(null);
      await load();
    } catch (e) {
      flash(e instanceof Error ? e.message : "Apply failed");
    } finally {
      setBusy(null);
    }
  };

  const handleUndo = async (change: ChangeEvent) => {
    try {
      setBusy(change.id);
      await undoChange(change.id, actor || "operator");
      flash("Change undone. Restored content returned by the backend.");
      await load();
    } catch (e) {
      flash(e instanceof Error ? e.message : "Undo failed");
    } finally {
      setBusy(null);
    }
  };

  const changes = log?.changes ?? [];

  return (
    <>
      {notice && (
        <div
          className="panel"
          style={{
            padding: "10px 14px",
            borderColor: "var(--accent)",
            fontSize: "11.5px",
          }}
        >
          {notice}
        </div>
      )}

      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Propose a Change (preview only)</span>
          <span style={{ fontSize: "10px", color: "var(--muted)" }}>
            Nothing is written to the live site until you apply it
          </span>
        </div>
        <div className="panel-body">
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "10px",
              marginBottom: "10px",
            }}
          >
            <div>
              <label
                style={{
                  display: "block",
                  fontSize: "9.5px",
                  textTransform: "uppercase",
                  color: "var(--muted)",
                  marginBottom: "4px",
                }}
              >
                Approver (you)
              </label>
              <input
                className="chat-input"
                style={{ width: "100%" }}
                placeholder="you@agency.com"
                value={actor}
                onChange={(e) => setActor(e.target.value)}
              />
            </div>
            <div>
              <label
                style={{
                  display: "block",
                  fontSize: "9.5px",
                  textTransform: "uppercase",
                  color: "var(--muted)",
                  marginBottom: "4px",
                }}
              >
                Second reviewer (YMYL only)
              </label>
              <input
                className="chat-input"
                style={{ width: "100%" }}
                placeholder="compliance@agency.com"
                value={reviewer}
                onChange={(e) => setReviewer(e.target.value)}
              />
            </div>
          </div>

          <label
            style={{
              display: "block",
              fontSize: "9.5px",
              textTransform: "uppercase",
              color: "var(--muted)",
              marginBottom: "4px",
            }}
          >
            Target URL
          </label>
          <input
            className="chat-input"
            style={{ width: "100%", marginBottom: "10px" }}
            placeholder="https://client.com/legal/faq"
            value={targetUrl}
            onChange={(e) => setTargetUrl(e.target.value)}
          />

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "10px",
              marginBottom: "10px",
            }}
          >
            <div>
              <label
                style={{
                  display: "block",
                  fontSize: "9.5px",
                  textTransform: "uppercase",
                  color: "var(--muted)",
                  marginBottom: "4px",
                }}
              >
                Current content
              </label>
              <textarea
                className="chat-input"
                style={{ width: "100%", minHeight: "90px", resize: "vertical" }}
                value={beforeContent}
                onChange={(e) => setBeforeContent(e.target.value)}
              />
            </div>
            <div>
              <label
                style={{
                  display: "block",
                  fontSize: "9.5px",
                  textTransform: "uppercase",
                  color: "var(--muted)",
                  marginBottom: "4px",
                }}
              >
                Proposed content
              </label>
              <textarea
                className="chat-input"
                style={{ width: "100%", minHeight: "90px", resize: "vertical" }}
                value={afterContent}
                onChange={(e) => setAfterContent(e.target.value)}
              />
            </div>
          </div>

          <button
            className="btn btn-primary"
            onClick={handlePreview}
            disabled={busy === "preview" || !websiteId}
          >
            {busy === "preview" ? "Generating diff..." : "Generate preview diff"}
          </button>
        </div>
      </div>

      {draft && (
        <div className="panel" style={{ borderColor: draft.is_ymyl ? "var(--amber)" : "var(--line)" }}>
          <div className="panel-head">
            <span className="panel-label">
              Preview · {draft.target_url}
            </span>
            {draft.is_ymyl && (
              <span className="badge badge-amber">YMYL — second review required</span>
            )}
          </div>
          <div className="panel-body">
            {draft.is_ymyl && (
              <div
                style={{
                  padding: "9px 12px",
                  background: "rgba(245,158,11,0.08)",
                  border: "1px solid var(--amber)",
                  borderRadius: "3px",
                  fontSize: "11px",
                  marginBottom: "10px",
                  color: "var(--ink)",
                }}
              >
                This page looks legal/medical/financial ({draft.ymyl_reason}).
                Applying requires a second reviewer that differs from the approver.
              </div>
            )}
            <DiffView diff={draft.unified_diff || "(no differences)"} />
            <div style={{ display: "flex", gap: "8px", marginTop: "12px" }}>
              <button
                className="btn btn-accent"
                onClick={() => handleApply(draft)}
                disabled={busy === draft.id}
              >
                {busy === draft.id ? "Applying..." : "Apply change"}
              </button>
              <button className="btn" onClick={() => setDraft(null)}>
                Discard preview
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">
            Change Log
            {log && (
              <span className="badge badge-muted" style={{ marginLeft: "8px" }}>
                {log.counts.applied} applied · {log.counts.undone} undone ·{" "}
                {log.counts.ymyl} YMYL
              </span>
            )}
          </span>
          <button className="panel-action" onClick={load} disabled={loading}>
            {loading ? "Loading" : "Refresh"}
          </button>
        </div>
        <div className="panel-body" style={{ padding: 0 }}>
          {error && (
            <div style={{ padding: "16px", fontSize: "11.5px", color: "var(--red)" }}>
              {error}
            </div>
          )}
          {!error && !loading && changes.length === 0 && (
            <div
              style={{
                padding: "28px 16px",
                textAlign: "center",
                fontSize: "11.5px",
                color: "var(--muted)",
              }}
            >
              No changes recorded yet. Every preview, apply and undo will appear
              here with its diff.
            </div>
          )}
          {changes.length > 0 && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>URL</th>
                  <th style={{ width: "150px" }}>Status</th>
                  <th style={{ width: "130px" }}>Actor</th>
                  <th style={{ width: "110px" }}>When</th>
                  <th style={{ width: "90px" }} />
                </tr>
              </thead>
              <tbody>
                {changes.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <div style={{ fontSize: "11px", fontWeight: 600 }}>
                        {c.target_url}
                      </div>
                      <div style={{ fontSize: "9.5px", color: "var(--muted)" }}>
                        {c.change_type}
                        {c.is_ymyl ? " · YMYL" : ""}
                      </div>
                    </td>
                    <td>
                      <span
                        className={`badge ${
                          c.status === "applied"
                            ? "badge-green"
                            : c.status === "undone"
                            ? "badge-red"
                            : "badge-amber"
                        }`}
                      >
                        {c.status}
                      </span>
                      {c.review_required && c.status === "previewed" && (
                        <div
                          style={{
                            fontSize: "9px",
                            color: "var(--amber)",
                            marginTop: "2px",
                          }}
                        >
                          awaiting review
                        </div>
                      )}
                    </td>
                    <td style={{ fontSize: "10.5px" }}>{c.actor}</td>
                    <td style={{ fontSize: "10px", color: "var(--muted)" }}>
                      {c.applied_at || c.undone_at || c.created_at
                        ? new Date(
                            c.applied_at || c.undone_at || c.created_at || ""
                          ).toLocaleString()
                        : "—"}
                    </td>
                    <td>
                      {c.status === "applied" && (
                        <button
                          className="btn btn-danger"
                          onClick={() => handleUndo(c)}
                          disabled={busy === c.id}
                          style={{ fontSize: "9px", padding: "4px 8px" }}
                        >
                          {busy === c.id ? "..." : "Undo"}
                        </button>
                      )}
                      {c.status === "previewed" && (
                        <button
                          className="btn btn-accent"
                          onClick={() => handleApply(c)}
                          disabled={busy === c.id}
                          style={{ fontSize: "9px", padding: "4px 8px" }}
                        >
                          {busy === c.id ? "..." : "Apply"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}