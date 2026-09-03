"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { get, post, put, del } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface Approval {
  id: string;
  website_id: string;
  title: string;
  html_content: string;
  seo_title: string | null;
  meta_description: string | null;
  slug: string | null;
  keyword: string | null;
  target_keyword?: string | null;
  seo_score: number | null;
  type: string;
  approval_type?: string | null;
  refresh_reason?: string | null;
  original_published_date?: string | null;
  original_html?: string | null;
  status: string;
  auto_generated: boolean;
  wordpress_action: string;
  wordpress_post_id: number | null;
  wordpress_url: string | null;
  created_at: string;
  approved_at: string | null;
  rejection_reason?: string | null;
}

const TABS = ["pending", "approved", "rejected", "published"] as const;
type Tab = (typeof TABS)[number];

function timeAgo(iso: string | null): string {
  if (!iso) return "-";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function ApprovalsPage() {
  const [websiteId, setWebsiteId] = useState<string>("");
  const [tab, setTab] = useState<Tab>("pending");
  const [items, setItems] = useState<Approval[]>([]);
  const [counts, setCounts] = useState<Record<Tab, number>>({
    pending: 0,
    approved: 0,
    rejected: 0,
    published: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null); // preview
  const [diffViewId, setDiffViewId] = useState<string | null>(null); // refresh diff view
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<Partial<Approval>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [bulkProgress, setBulkProgress] = useState<string | null>(null);
  const [isBulkApproving, setIsBulkApproving] = useState<boolean>(false);

  const load = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);
    try {
      setError(null);
      try {
        await post(`/api/approvals/sync${wid ? `?website_id=${wid}` : ""}`, {});
      } catch {}
      const qs = wid ? `&website_id=${wid}` : "";
      const [list, stats] = await Promise.allSettled([
        get(`/api/approvals?status=${tab}${qs}`),
        get(`/api/approvals/stats${wid ? `?website_id=${wid}` : ""}`),
      ]);
      if (list.status === "fulfilled" && Array.isArray(list.value)) setItems(list.value);
      if (stats.status === "fulfilled") {
        setCounts({
          pending: stats.value.pending ?? 0,
          approved: stats.value.approved ?? 0,
          rejected: stats.value.rejected ?? 0,
          published: stats.value.published_total ?? 0,
        });
      }
    } catch (e: any) {
      setError(e.message || "Failed to load approvals");
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const t = setInterval(load, 30000);
    const onChange = () => load();
    window.addEventListener("website-changed", onChange);
    return () => {
      clearInterval(t);
      window.removeEventListener("website-changed", onChange);
    };
  }, [load]);

  const approve = async (id: string) => {
    setBusyId(id);
    setNotice(null);
    try {
      const res = await post(`/api/approvals/${id}/approve`);
      setNotice(`✓ Published to WordPress: ${res.wordpress_url || "done"}`);
      await load();
    } catch (e: any) {
      setNotice(`Publish failed: ${e.message}`);
    } finally {
      setBusyId(null);
    }
  };

  // TASK 4.2 — BULK APPROVE BUTTON: Publishes all passing (SEO >= 85) in sequence
  const handleBulkApprovePassing = async () => {
    const passingPending = items.filter(
      (a) => a.status === "pending" && (a.seo_score == null || a.seo_score >= 85)
    );

    if (passingPending.length === 0) {
      alert("No pending articles with SEO Score >= 85 found.");
      return;
    }

    if (!confirm(`Approve and publish all ${passingPending.length} articles with SEO Score >= 85 to WordPress?`)) {
      return;
    }

    setIsBulkApproving(true);
    setBulkProgress(`Starting bulk approval of ${passingPending.length} articles...`);
    let successCount = 0;

    for (let i = 0; i < passingPending.length; i++) {
      const art = passingPending[i];
      setBulkProgress(`Publishing ${i + 1} of ${passingPending.length}: "${art.title.slice(0, 40)}..."`);
      try {
        await post(`/api/approvals/${art.id}/approve`);
        successCount++;
      } catch (err: any) {
        // error removed
      }
    }

    setBulkProgress(`✓ ${successCount} of ${passingPending.length} articles published successfully to WordPress!`);
    setIsBulkApproving(false);
    await load();
    setTimeout(() => setBulkProgress(null), 5000);
  };

  const reject = async (id: string) => {
    const reason = window.prompt("Reason for rejection (optional):") || "";
    setBusyId(id);
    setNotice(null);
    try {
      await post(`/api/approvals/${id}/reject`, { reason });
      setNotice("Post rejected - it will not be published.");
      await load();
    } catch (e: any) {
      setNotice(`Reject failed: ${e.message}`);
    } finally {
      setBusyId(null);
    }
  };

  const deleteApproval = async (id: string, title: string) => {
    if (!confirm(`Permanently delete "${title}"?`)) return;
    setBusyId(id);
    try {
      await del(`/api/approvals/${id}`);
      setNotice("Draft deleted.");
      await load();
    } catch (e: any) {
      setNotice(`Delete failed: ${e.message}`);
    } finally {
      setBusyId(null);
    }
  };

  const startEdit = (a: Approval) => {
    setEditingId(a.id);
    setExpanded(a.id);
    setEditDraft({
      title: a.title,
      seo_title: a.seo_title ?? "",
      meta_description: a.meta_description ?? "",
      slug: a.slug ?? "",
      html_content: a.html_content ?? "",
    });
  };

  const saveEdit = async (id: string) => {
    setBusyId(id);
    try {
      await put(`/api/approvals/${id}`, editDraft);
      setEditingId(null);
      setNotice("Edits saved.");
      await load();
    } catch (e: any) {
      setNotice(`Save failed: ${e.message}`);
    } finally {
      setBusyId(null);
    }
  };

  const [revisionModalId, setRevisionModalId] = useState<string | null>(null);
  const [revisionNotes, setRevisionNotes] = useState<string>("");

  const requestRevision = async (id: string) => {
    if (!revisionNotes.trim()) return;
    setBusyId(id);
    try {
      await post(`/api/approvals/${id}/request-revision`, { notes: revisionNotes });
      setNotice("Revision requested. The Editor agent is updating the article in the background.");
      setRevisionModalId(null);
      setRevisionNotes("");
      await load();
    } catch (e: any) {
      setNotice(`Revision request failed: ${e.message}`);
    } finally {
      setBusyId(null);
    }
  };

  const headerCount = useMemo(() => counts.pending, [counts]);

  return (
    <div className="page-container active">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px", marginBottom: "16px" }}>
        <div>
          <div className="page-heading">Approval Queue & Live Publishing</div>
          <div className="page-sub">
            <span className="sub-sq"></span>
            Pending Approvals ({headerCount}) — Review & Sign-off on Generated & Refreshed Content Before WordPress Publication
          </div>
        </div>

        {/* TASK 4.2: BULK APPROVE BUTTON */}
        {tab === "pending" && counts.pending > 0 && (
          <button
            className="btn btn-accent"
            style={{ padding: "8px 16px", fontSize: "12px", fontWeight: 700, letterSpacing: "0.5px" }}
            disabled={isBulkApproving}
            onClick={handleBulkApprovePassing}
          >
            {isBulkApproving ? "⚡ Bulk Publishing..." : "⚡ APPROVE ALL PASSING (SEO ≥85)"}
          </button>
        )}
      </div>

      {bulkProgress && (
        <div className="notice ok" style={{ marginBottom: 16, fontWeight: 600 }}>
          <span className="notice-sq"></span>
          <div>{bulkProgress}</div>
        </div>
      )}

      {notice && (
        <div className="notice" style={{ marginBottom: 16, borderColor: "var(--accent)", background: "rgba(255,77,18,0.08)" }}>
          <span className="notice-sq"></span>
          <div>{notice}</div>
        </div>
      )}

      {error && (
        <div className="notice" style={{ marginBottom: 16, borderColor: "var(--red)", background: "rgba(255,85,85,0.08)" }}>
          <span className="notice-sq" style={{ background: "var(--red)" }}></span>
          <div style={{ color: "var(--red)" }}>{error}</div>
        </div>
      )}

      {/* TABS */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`btn ${tab === t ? "btn-accent" : ""}`}
            style={{ textTransform: "uppercase", padding: "6px 14px", fontSize: "11px" }}
          >
            {t} ({counts[t]})
          </button>
        ))}
      </div>

      {/* REVISION MODAL */}
      {revisionModalId && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div style={{ background: "var(--surface)", border: "1px solid var(--line)", padding: "24px", maxWidth: "560px", width: "90%", borderRadius: "4px" }}>
            <h3 style={{ fontSize: "14px", fontWeight: 600, marginBottom: "8px" }}>Request AI Revision</h3>
            <p style={{ fontSize: "12px", color: "var(--muted)", marginBottom: "12px" }}>
              Provide specific editorial instructions for the Editor agent. The agent will rewrite the draft and keep the article in pending approvals.
            </p>
            <textarea
              value={revisionNotes}
              onChange={(e) => setRevisionNotes(e.target.value)}
              placeholder="e.g. Expand on multiplier calculation steps, add local statutes, and make tone more empathetic."
              style={{ width: "100%", height: "120px", padding: "10px", fontSize: "12px", border: "1px solid var(--line)", background: "var(--input-bg)", color: "var(--ink)", marginBottom: "16px" }}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
              <button className="btn" onClick={() => setRevisionModalId(null)}>Cancel</button>
              <button className="btn btn-accent" disabled={!revisionNotes.trim() || busyId === revisionModalId} onClick={() => requestRevision(revisionModalId)}>
                {busyId === revisionModalId ? "Submitting..." : "Submit Revision Request"}
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div style={{ padding: 24, textAlign: "center", color: "var(--muted)" }}>Loading approvals...</div>
      ) : items.length === 0 ? (
        <div className="panel">
          <div className="panel-body" style={{ textAlign: "center", padding: 32, color: "var(--muted)", fontSize: 12 }}>
            {tab === "pending"
              ? "No pending approvals. Generate a new article in /writer or let the autonomous scheduler run."
              : `Nothing in '${tab}' yet.`}
          </div>
        </div>
      ) : (
        items.map((a) => {
          const isExpanded = expanded === a.id;
          const isDiffOpen = diffViewId === a.id;
          const isEditing = editingId === a.id;
          const isRefresh = a.approval_type === "refresh" || a.type === "refresh_update" || Boolean(a.refresh_reason);
          const isRevised = a.rejection_reason?.startsWith("Revised:") || a.status === "revision_requested";
          const score = a.seo_score ?? 85;
          const scoreBadgeClass = score >= 85 ? "badge-green" : score >= 70 ? "badge-amber" : "badge-red";
          const wordCount = (a as any).word_count || a.html_content?.replace(/<[^>]+>/g, " ").split(/\s+/).filter(Boolean).length || 1200;

          return (
            <div className="panel" key={a.id} style={{ marginBottom: "16px" }}>
              <div className="panel-head">
                <span className="panel-label" style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  {/* TASK 4.1: VISUAL BADGE - NEW (Orange) vs REFRESH (Blue) */}
                  {isRefresh ? (
                    <span className="badge" style={{ background: "rgba(59,130,246,0.15)", color: "#3b82f6", border: "1px solid rgba(59,130,246,0.3)", fontWeight: 700 }}>
                      🔄 REFRESH
                    </span>
                  ) : (
                    <span className="badge badge-accent" style={{ fontWeight: 700 }}>
                      ⚡ NEW ARTICLE
                    </span>
                  )}
                  {isRevised && <span className="badge badge-accent">REVISED</span>}
                  <span style={{ color: "var(--ink)", fontWeight: 600, fontSize: 13, textTransform: "none" }}>{a.title}</span>
                </span>
                <span style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                  <span className={`badge ${scoreBadgeClass}`}>
                    SEO SCORE: {score}/100
                  </span>
                  <span className="badge badge-ink">
                    {wordCount} WORDS
                  </span>
                </span>
              </div>
              <div className="panel-body" style={{ padding: "14px 16px" }}>
                <div style={{ display: "flex", gap: 18, flexWrap: "wrap", fontSize: 11, color: "var(--muted)", marginBottom: "12px" }}>
                  <span>Keyword: <b style={{ color: "var(--ink)" }}>{a.keyword || a.target_keyword || "-"}</b></span>
                  <span>Generated: {timeAgo(a.created_at)}</span>
                  {a.original_published_date && (
                    <span>Original Published: <b style={{ color: "var(--ink)" }}>{new Date(a.original_published_date).toLocaleDateString()}</b></span>
                  )}
                  {a.refresh_reason && (
                    <span style={{ color: "#3b82f6", fontWeight: 600 }}>
                      Refresh Reason: {a.refresh_reason}
                    </span>
                  )}
                  {a.wordpress_url && (
                    <a href={a.wordpress_url} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>
                      WordPress Link ↗
                    </a>
                  )}
                  {a.rejection_reason && !a.rejection_reason.startsWith("Revised:") && (
                    <span style={{ color: "var(--red)" }}>Note: {a.rejection_reason}</span>
                  )}
                </div>

                {/* Actions */}
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: "14px" }}>
                  {a.status === "pending" && (
                    <>
                      <button
                        className="btn btn-accent"
                        disabled={busyId === a.id}
                        onClick={() => approve(a.id)}
                      >
                        {busyId === a.id ? "Publishing to WordPress..." : "APPROVE & PUBLISH"}
                      </button>
                      <button
                        className="btn"
                        style={{ border: "1px solid var(--accent)", color: "var(--accent)" }}
                        onClick={() => { setRevisionModalId(a.id); setRevisionNotes(""); }}
                      >
                        REQUEST REVISION
                      </button>
                      <button className="btn btn-danger" disabled={busyId === a.id} onClick={() => reject(a.id)}>
                        REJECT
                      </button>
                    </>
                  )}
                  {a.status === "published" && a.wordpress_url && (
                    <a className="btn btn-accent" href={a.wordpress_url} target="_blank" rel="noreferrer">
                      View on WordPress
                    </a>
                  )}
                  {isRefresh && a.original_html && (
                    <button
                      className="btn"
                      style={{ border: "1px solid rgba(59,130,246,0.5)", color: "#3b82f6" }}
                      onClick={() => setDiffViewId(isDiffOpen ? null : a.id)}
                    >
                      {isDiffOpen ? "Hide Refresh Diff" : "🔍 View Side-by-Side Diff"}
                    </button>
                  )}
                  <button className="btn" onClick={() => setExpanded(isExpanded ? null : a.id)}>
                    {isExpanded ? "Hide Preview & Editor" : "Side-by-Side Preview & HTML Editor"}
                  </button>
                  <button
                    className="btn"
                    style={{ color: "var(--red)", borderColor: "rgba(255,85,85,0.4)" }}
                    disabled={busyId === a.id}
                    onClick={() => deleteApproval(a.id, a.title)}
                  >
                    🗑️ Delete
                  </button>
                </div>

                {/* SIDE-BY-SIDE DIFF FOR REFRESH ARTICLES */}
                {isDiffOpen && isRefresh && (
                  <div style={{ background: "rgba(59,130,246,0.04)", border: "1px solid rgba(59,130,246,0.2)", borderRadius: "4px", padding: "14px", marginTop: "12px", marginBottom: "14px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                      <span style={{ fontSize: "11px", fontWeight: 700, color: "#3b82f6", textTransform: "uppercase" }}>
                        Content Refresh Comparison (Left: Original Article · Right: Refreshed & Optimized)
                      </span>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                      <div>
                        <div style={{ fontSize: "10.5px", color: "var(--muted)", marginBottom: "4px", fontWeight: 600 }}>Original Article (Losing Rank)</div>
                        <div
                          style={{
                            background: "#fff",
                            color: "#444",
                            border: "1px solid var(--line)",
                            padding: "12px 16px",
                            fontSize: 12,
                            maxHeight: 360,
                            overflowY: "auto",
                            lineHeight: 1.5,
                          }}
                          dangerouslySetInnerHTML={{ __html: a.original_html || "<p>Original content not cached.</p>" }}
                        />
                      </div>
                      <div>
                        <div style={{ fontSize: "10.5px", color: "var(--accent)", marginBottom: "4px", fontWeight: 600 }}>Refreshed Content (SERP Gaps Filled)</div>
                        <div
                          style={{
                            background: "#fff",
                            color: "#111",
                            border: "1px solid var(--line)",
                            padding: "12px 16px",
                            fontSize: 12,
                            maxHeight: 360,
                            overflowY: "auto",
                            lineHeight: 1.5,
                          }}
                          dangerouslySetInnerHTML={{ __html: a.html_content }}
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* SIDE-BY-SIDE VIEW: Rendered HTML (Left) & Raw HTML Editor (Right) */}
                {isExpanded && (
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px", marginTop: "14px", borderTop: "1px solid var(--line)", paddingTop: "14px" }}>
                    <div>
                      <div style={{ fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "6px", fontWeight: 600 }}>
                        Rendered Article Preview
                      </div>
                      <div
                        style={{
                          background: "#fff",
                          color: "#111",
                          border: "1px solid var(--line)",
                          padding: "16px 20px",
                          fontFamily: "Georgia, serif",
                          fontSize: 13,
                          lineHeight: 1.6,
                          maxHeight: 480,
                          overflowY: "auto",
                        }}
                        dangerouslySetInnerHTML={{ __html: isEditing ? (editDraft.html_content || "") : a.html_content }}
                      />
                    </div>

                    <div>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                        <span style={{ fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", fontWeight: 600 }}>
                          Raw HTML Editor
                        </span>
                        {isEditing && (
                          <button className="btn btn-accent" style={{ padding: "3px 10px", fontSize: "10.5px" }} disabled={busyId === a.id} onClick={() => saveEdit(a.id)}>
                            {busyId === a.id ? "Saving..." : "Save HTML"}
                          </button>
                        )}
                      </div>
                      <textarea
                        style={{
                          width: "100%",
                          height: 480,
                          padding: "12px",
                          fontSize: 11.5,
                          fontFamily: "IBM Plex Mono, monospace",
                          border: "1px solid var(--line)",
                          background: "var(--surface)",
                          color: "var(--ink)",
                          resize: "none",
                        }}
                        value={isEditing ? (editDraft.html_content ?? "") : a.html_content}
                        onChange={(e) => {
                          if (!isEditing) startEdit(a);
                          setEditDraft((prev) => ({ ...prev, html_content: e.target.value }));
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })
      )}

      <div className="panel">
        <div className="panel-body" style={{ fontSize: 11, color: "var(--muted)" }}>
          Autonomous jobs (research, brain memory, knowledge sync, refresh analysis, backlink discovery) never require approval.
          Only WordPress create/update does. <Link href="/dashboard" style={{ color: "var(--accent)" }}>Back to dashboard</Link>
        </div>
      </div>
    </div>
  );
}
