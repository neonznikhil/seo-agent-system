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
  seo_score: number | null;
  type: string;
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

const TYPE_META: Record<string, { label: string; cls: string }> = {
  new_post: { label: "NEW POST", cls: "badge-accent" },
  new_page: { label: "NEW PAGE", cls: "badge-ink" },
  refresh_update: { label: "REFRESH", cls: "badge-amber" },
};

function scoreClass(score: number | null): string {
  if (score == null) return "badge-muted";
  if (score >= 80) return "badge-green";
  if (score >= 60) return "badge-amber";
  return "badge-red";
}

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
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<Partial<Approval>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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
      setNotice(`Published to WordPress: ${res.wordpress_url || "done"}`);
      await load();
    } catch (e: any) {
      setNotice(`Publish failed: ${e.message}`);
    } finally {
      setBusyId(null);
    }
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

  const headerCount = useMemo(() => counts.pending, [counts]);

  return (
    <div className="page-container active">
      <div className="page-heading">Approval Queue</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Pending Approvals ({headerCount}) - posts waiting for your human sign-off. Everything else runs autonomously.
      </div>

      {notice && (
        <div className="notice" style={{ marginBottom: 16, borderColor: "var(--accent)", background: "rgba(255,77,18,0.08)" }}>
          <span className="notice-sq"></span>
          <div>{notice}</div>
        </div>
      )}
      {error && (
        <div className="badge badge-red" style={{ marginBottom: 16 }}>{error}</div>
      )}

      {/* Tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`btn ${tab === t ? "btn-accent" : ""}`}
            style={{ textTransform: "uppercase" }}
          >
            {t}{t === "pending" ? ` (${counts.pending})` : t === "published" ? ` (${counts.published})` : ""}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ padding: 24, textAlign: "center", color: "var(--muted)" }}>Loading approvals...</div>
      ) : items.length === 0 ? (
        <div className="panel">
          <div className="panel-body" style={{ textAlign: "center", padding: 32, color: "var(--muted)", fontSize: 12 }}>
            {tab === "pending"
              ? "No posts waiting for approval. New drafts appear here automatically after the 11AM IST daily run (or via Manual Run in scheduler)."
              : `Nothing in '${tab}' yet.`}
          </div>
        </div>
      ) : (
        items.map((a) => {
          const tm = TYPE_META[a.type] ?? { label: a.type.toUpperCase(), cls: "badge-muted" };
          const isExpanded = expanded === a.id;
          const isEditing = editingId === a.id;
          return (
            <div className="panel" key={a.id}>
              <div className="panel-head">
                <span className="panel-label" style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span className={tm.cls + " badge"}>{tm.label}</span>
                  <span style={{ color: "var(--ink)", fontWeight: 600, fontSize: 13, textTransform: "none" }}>{a.title}</span>
                </span>
                <span className={scoreClass(a.seo_score) + " badge"}>
                  SEO {a.seo_score != null ? `${a.seo_score}/100` : "N/A"}
                </span>
              </div>
              <div className="panel-body" style={{ padding: "12px 14px" }}>
                <div style={{ display: "flex", gap: 18, flexWrap: "wrap", fontSize: 11, color: "var(--muted)" }}>
                  <span>Keyword: <b style={{ color: "var(--ink)" }}>{a.keyword || "-"}</b></span>
                  <span>Created: {timeAgo(a.created_at)}</span>
                  <span>WP action: {a.wordpress_action}</span>
                  {a.wordpress_url && (
                    <a href={a.wordpress_url} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>
                      {a.wordpress_url}
                    </a>
                  )}
                  {a.status === "rejected" && a.rejection_reason && <span>Reason: {a.rejection_reason}</span>}
                </div>

                {/* Meta block */}
                <div style={{ marginTop: 10, display: "grid", gap: 4, fontSize: 11 }}>
                  <div><span style={{ color: "var(--muted)" }}>SEO Title:</span> {a.seo_title || "-"}</div>
                  <div><span style={{ color: "var(--muted)" }}>Meta:</span> {a.meta_description || "-"}</div>
                  <div><span style={{ color: "var(--muted)" }}>Slug:</span> /{a.slug || "-"}</div>
                </div>

                {/* Actions */}
                <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
                  {a.status === "pending" && (
                    <>
                      <button
                        className="btn btn-accent"
                        disabled={busyId === a.id}
                        onClick={() => approve(a.id)}
                      >
                        {busyId === a.id ? "Publishing..." : "Approve & Publish to WordPress"}
                      </button>
                      <button className="btn" onClick={() => (isEditing ? setEditingId(null) : startEdit(a))}>
                        {isEditing ? "Close Editor" : "Edit"}
                      </button>
                      <button className="btn btn-danger" disabled={busyId === a.id} onClick={() => reject(a.id)}>
                        Reject
                      </button>
                    </>
                  )}
                  {a.status === "published" && a.wordpress_url && (
                    <a className="btn btn-accent" href={a.wordpress_url} target="_blank" rel="noreferrer">
                      View on WordPress
                    </a>
                  )}
                  <button className="btn" onClick={() => setExpanded(isExpanded ? null : a.id)}>
                    {isExpanded ? "Hide Preview" : "Preview"}
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

                {/* Editor */}
                {isEditing && (
                  <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
                    <input
                      className="input"
                      style={{ width: "100%", padding: "6px 10px", fontSize: 12, border: "1px solid var(--line)", background: "var(--input-bg)", color: "var(--ink)" }}
                      value={editDraft.title ?? ""}
                      onChange={(e) => setEditDraft({ ...editDraft, title: e.target.value })}
                      placeholder="Title"
                    />
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                      <input
                        style={{ padding: "6px 10px", fontSize: 12, border: "1px solid var(--line)", background: "var(--input-bg)", color: "var(--ink)" }}
                        value={editDraft.seo_title ?? ""}
                        onChange={(e) => setEditDraft({ ...editDraft, seo_title: e.target.value })}
                        placeholder="SEO title (<60 chars)"
                      />
                      <input
                        style={{ padding: "6px 10px", fontSize: 12, border: "1px solid var(--line)", background: "var(--input-bg)", color: "var(--ink)" }}
                        value={editDraft.slug ?? ""}
                        onChange={(e) => setEditDraft({ ...editDraft, slug: e.target.value })}
                        placeholder="Slug"
                      />
                    </div>
                    <input
                      style={{ padding: "6px 10px", fontSize: 12, border: "1px solid var(--line)", background: "var(--input-bg)", color: "var(--ink)" }}
                      value={editDraft.meta_description ?? ""}
                      onChange={(e) => setEditDraft({ ...editDraft, meta_description: e.target.value })}
                      placeholder="Meta description (<160 chars)"
                    />
                    <textarea
                      style={{ width: "100%", minHeight: 220, padding: "8px 10px", fontSize: 12, fontFamily: "IBM Plex Mono, monospace", border: "1px solid var(--line)", background: "var(--input-bg)", color: "var(--ink)" }}
                      value={editDraft.html_content ?? ""}
                      onChange={(e) => setEditDraft({ ...editDraft, html_content: e.target.value })}
                      placeholder="Elementor-safe HTML"
                    />
                    <div style={{ display: "flex", gap: 8 }}>
                      <button className="btn btn-primary" disabled={busyId === a.id} onClick={() => saveEdit(a.id)}>
                        {busyId === a.id ? "Saving..." : "Save Changes"}
                      </button>
                      <button className="btn" onClick={() => setEditingId(null)}>Cancel</button>
                    </div>
                  </div>
                )}

                {/* Preview (WordPress-like rendering) */}
                {isExpanded && !isEditing && (
                  <div
                    style={{
                      marginTop: 12,
                      background: "#fff",
                      color: "#111",
                      border: "1px solid var(--line)",
                      padding: "20px 24px",
                      fontFamily: "Georgia, serif",
                      fontSize: 14,
                      lineHeight: 1.6,
                      maxHeight: 420,
                      overflowY: "auto",
                    }}
                    dangerouslySetInnerHTML={{ __html: a.html_content }}
                  />
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
