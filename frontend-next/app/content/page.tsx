"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import Link from "next/link";
import { get, post, del } from "@/lib/api";
import { getCurrentWebsiteId, getWebsiteId } from "@/lib/website";

interface BlogArticle {
  id: string;
  title: string;
  keyword?: string;
  primary_keyword?: string;
  content?: string;
  html_content?: string;
  seo_score?: number;
  word_count?: number;
  status: string;
  created_at?: string;
  wordpress_post_id?: number | string;
  wordpress_url?: string;
  wp_post_id?: number | string;
  wp_draft_url?: string;
  approval_id?: string;
}

interface TrackedRanking {
  id: string;
  website_id: string;
  title: string;
  target_keyword: string;
  keyword?: string;
  wp_url: string;
  published_at?: string;
  last_checked_at?: string;
  current_position?: number | null;
  best_position?: number | null;
  change?: number;
  status_label?: string;
  status: string;
  position_history?: Array<{ date: string; position: number | null }>;
}

export default function ContentPage() {
  const [articles, setArticles] = useState<BlogArticle[]>([]);
  const [rankings, setRankings] = useState<TrackedRanking[]>([]);
  const [tab, setTab] = useState<string>("all");
  const [previewArticle, setPreviewArticle] = useState<BlogArticle | null>(null);
  const [loading, setLoading] = useState(true);
  const [rankingsLoading, setRankingsLoading] = useState(false);
  const [checkingRanks, setCheckingRanks] = useState(false);
  const [publishing, setPublishing] = useState<string | null>(null);
  const [noticeMsg, setNoticeMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [websiteId, setWebsiteId] = useState<string>("");
  const [copied, setCopied] = useState<boolean>(false);

  const loadArticles = useCallback(async () => {
    const wid = getCurrentWebsiteId() || getWebsiteId();
    setWebsiteId(wid);
    if (!wid) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Fetch from blogs and approvals in parallel
      const [blogsRes, approvalsRes] = await Promise.allSettled([
        get(`/api/blogs?website_id=${wid}`),
        get(`/api/approvals?website_id=${wid}&limit=100`),
      ]);

      const blogList: BlogArticle[] = blogsRes.status === "fulfilled" && Array.isArray(blogsRes.value) ? blogsRes.value : [];
      const appList: any[] = approvalsRes.status === "fulfilled" && Array.isArray(approvalsRes.value) ? approvalsRes.value : [];

      // Combine by ID / title
      const combinedMap = new Map<string, BlogArticle>();
      for (const b of blogList) {
        combinedMap.set(b.id, {
          ...b,
          keyword: b.keyword || b.primary_keyword || "",
          html_content: b.html_content || b.content || "",
          word_count: b.word_count || (b.html_content || b.content || "").replace(/<[^>]+>/g, " ").split(/\s+/).filter(Boolean).length || 1200,
        });
      }
      for (const a of appList) {
        const existing = combinedMap.get(a.blog_id || a.id);
        if (existing) {
          existing.approval_id = a.id;
          existing.status = a.status === "approved" || a.status === "published" ? a.status : existing.status;
          existing.wordpress_url = a.wordpress_url || existing.wordpress_url;
        } else {
          combinedMap.set(a.id, {
            id: a.id,
            approval_id: a.id,
            title: a.title,
            keyword: a.keyword || a.target_keyword || "",
            html_content: a.html_content || "",
            seo_score: a.seo_score || 85,
            word_count: a.word_count || (a.html_content || "").replace(/<[^>]+>/g, " ").split(/\s+/).filter(Boolean).length || 1200,
            status: a.status,
            wordpress_url: a.wordpress_url,
            created_at: a.created_at,
          });
        }
      }

      setArticles(Array.from(combinedMap.values()));
    } catch (e: any) {
      console.warn("Articles load error:", e);
      setError(e.message || "Failed to load content log");
      setArticles([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadRankings = useCallback(async () => {
    const wid = getCurrentWebsiteId() || getWebsiteId();
    if (!wid) return;
    try {
      setRankingsLoading(true);
      const res = await get(`/api/rankings?website_id=${wid}`);
      if (res && Array.isArray(res.rankings)) {
        setRankings(res.rankings);
      }
    } catch (err) {
      console.warn("Rankings fetch note:", err);
    } finally {
      setRankingsLoading(false);
    }
  }, []);

  const handleCheckRankingsNow = async () => {
    const wid = getCurrentWebsiteId() || getWebsiteId();
    if (!wid) return;
    setCheckingRanks(true);
    try {
      const res = await post(`/api/rankings/check?website_id=${wid}`, {});
      setNoticeMsg(`Rank check completed: ${res.updated_count ?? 0} post positions evaluated.`);
      await loadRankings();
    } catch (err: any) {
      setNoticeMsg(`Rank check failed: ${err.message}`);
    } finally {
      setCheckingRanks(false);
    }
  };

  useEffect(() => {
    loadArticles();
    loadRankings();
    const handleChanged = () => {
      loadArticles();
      loadRankings();
    };
    window.addEventListener("website-changed", handleChanged);

    // Auto-refresh every 60 seconds
    const interval = setInterval(() => {
      loadRankings();
    }, 60000);

    return () => {
      window.removeEventListener("website-changed", handleChanged);
      clearInterval(interval);
    };
  }, [loadArticles, loadRankings]);

  const handleApprove = async (approvalId?: string) => {
    if (!approvalId) return;
    setPublishing(approvalId);
    try {
      const res = await post(`/api/approvals/${approvalId}/approve`, {});
      setNoticeMsg(`✓ Published to WordPress: ${res.wordpress_url || "Draft created"}`);
      loadArticles();
      loadRankings();
    } catch (err: any) {
      setNoticeMsg(`Approval failed: ${err.message}`);
    } finally {
      setPublishing(null);
    }
  };

  const handleDeleteArticle = async (id: string, title: string) => {
    if (!confirm(`Permanently delete article "${title}"?`)) return;
    try {
      await del(`/api/blogs/${id}`);
      setNoticeMsg("Article deleted successfully.");
      loadArticles();
    } catch (err: any) {
      setError(`Delete failed: ${err.message}`);
    }
  };

  const handleCopyHtml = (html: string) => {
    navigator.clipboard.writeText(html);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Filtered
  const filteredArticles = useMemo(() => {
    if (tab === "all") return articles;
    if (tab === "pending") return articles.filter((a) => a.status === "pending");
    if (tab === "published") return articles.filter((a) => a.status === "published" || a.status === "approved");
    if (tab === "draft") return articles.filter((a) => a.status === "draft" || a.status === "pending");
    return articles;
  }, [articles, tab]);

  // Position Color Badge Helper
  const getPositionBadge = (pos: number | null | undefined) => {
    if (pos == null) {
      return <span style={{ color: "var(--muted)", fontWeight: 600 }}>—</span>;
    }
    if (pos >= 1 && pos <= 3) {
      return (
        <span className="badge badge-green" style={{ fontWeight: 700 }}>
          #{pos} (Top 3)
        </span>
      );
    }
    if (pos >= 4 && pos <= 10) {
      return (
        <span className="badge" style={{ background: "rgba(245,158,11,0.15)", color: "#f59e0b", border: "1px solid rgba(245,158,11,0.3)", fontWeight: 700 }}>
          #{pos} (Page 1)
        </span>
      );
    }
    if (pos >= 11 && pos <= 20) {
      return (
        <span className="badge" style={{ background: "rgba(234,179,8,0.15)", color: "#eab308", border: "1px solid rgba(234,179,8,0.3)", fontWeight: 600 }}>
          #{pos} (Striking Distance)
        </span>
      );
    }
    return (
      <span className="badge badge-red" style={{ fontWeight: 600 }}>
        #{pos} (Needs Work)
      </span>
    );
  };

  // Change Direction Helper
  const getChangeIndicator = (change: number | undefined) => {
    if (change == null || change === 0) {
      return <span style={{ color: "var(--muted)" }}>—</span>;
    }
    if (change > 0) {
      return (
        <span style={{ color: "var(--green)", fontWeight: 700 }}>
          ▲ +{change}
        </span>
      );
    }
    return (
      <span style={{ color: "var(--red)", fontWeight: 700 }}>
        ▼ {change}
      </span>
    );
  };

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      <div className="page-heading">Content Studio & Performance</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Post-Publish Rank Tracking · SERP Position Telemetry · Multi-Agent Output · Live WordPress Sync
      </div>

      {error && (
        <div className="notice" style={{ borderColor: "var(--red)", background: "rgba(239,68,68,0.08)", marginBottom: "16px" }}>
          <span className="notice-sq" style={{ background: "var(--red)" }}></span>
          <span style={{ color: "var(--red)" }}>{error}</span>
        </div>
      )}

      {noticeMsg && (
        <div className="notice ok" style={{ marginBottom: "16px" }}>
          <span className="notice-sq"></span>
          <span>{noticeMsg}</span>
        </div>
      )}

      {/* SECTION 1: CONTENT PERFORMANCE TRACKING TABLE (TASK 1.2) */}
      <div className="panel" style={{ marginBottom: "24px" }}>
        <div className="panel-head">
          <span className="panel-label" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span>📈 Content Performance & Google Rank Tracking ({rankings.length})</span>
            <span style={{ fontSize: "10px", color: "var(--muted)", fontWeight: 400 }}>(Auto-refreshes every 60s · Serper 6h cron)</span>
          </span>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              className="btn btn-accent"
              style={{ fontSize: "11px", padding: "4px 10px" }}
              disabled={checkingRanks}
              onClick={handleCheckRankingsNow}
            >
              {checkingRanks ? "Searching Google..." : "🔍 Check Rankings Now"}
            </button>
            <button className="panel-action" onClick={loadRankings}>
              Refresh
            </button>
          </div>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Keyword</th>
                <th>Published</th>
                <th>Current Position</th>
                <th>Change</th>
                <th>Best</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rankingsLoading && rankings.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", padding: "24px", color: "var(--muted)" }}>
                    Loading ranking telemetry...
                  </td>
                </tr>
              ) : rankings.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", padding: "24px", color: "var(--muted)", fontSize: "12px" }}>
                    No published posts tracked yet. Approve an article below to publish to WordPress and start Google rank tracking.
                  </td>
                </tr>
              ) : (
                rankings.map((r) => (
                  <tr key={r.id}>
                    <td style={{ fontWeight: 600, maxWidth: "260px" }}>
                      {r.wp_url ? (
                        <a href={r.wp_url} target="_blank" rel="noreferrer" style={{ color: "var(--ink)", textDecoration: "none" }}>
                          {r.title} ↗
                        </a>
                      ) : (
                        r.title
                      )}
                    </td>
                    <td>
                      <span style={{ fontSize: "11px", color: "var(--ink)", fontWeight: 500 }}>
                        {r.target_keyword || r.keyword || "—"}
                      </span>
                    </td>
                    <td style={{ fontSize: "11px", color: "var(--muted)", whiteSpace: "nowrap" }}>
                      {r.published_at ? new Date(r.published_at).toLocaleDateString() : "Recent"}
                    </td>
                    <td>{getPositionBadge(r.current_position)}</td>
                    <td style={{ fontSize: "12px" }}>{getChangeIndicator(r.change)}</td>
                    <td style={{ fontSize: "11px", fontWeight: 600, color: "var(--ink)" }}>
                      {r.best_position != null ? `#${r.best_position}` : "—"}
                    </td>
                    <td>
                      <span className="badge badge-accent">
                        {r.status_label || r.status || "tracking"}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* FILTER TABS */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "10px" }}>
        <div style={{ display: "flex", gap: "8px" }}>
          {[
            { id: "all", label: "All Articles" },
            { id: "pending", label: "Pending Approval" },
            { id: "published", label: "Published" },
            { id: "draft", label: "Drafts" },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`btn ${tab === t.id ? "btn-accent" : ""}`}
              style={{ textTransform: "uppercase", padding: "6px 14px", fontSize: "11px" }}
            >
              {t.label} (
              {t.id === "all"
                ? articles.length
                : t.id === "pending"
                ? articles.filter((a) => a.status === "pending").length
                : t.id === "published"
                ? articles.filter((a) => a.status === "published" || a.status === "approved").length
                : articles.filter((a) => a.status === "draft" || a.status === "pending").length}
              )
            </button>
          ))}
        </div>
        <Link href="/writer" className="btn btn-accent" style={{ textDecoration: "none", fontSize: "11px", padding: "6px 14px" }}>
          ⚡ Generate New Article
        </Link>
      </div>

      {/* HTML PREVIEW MODAL */}
      {previewArticle && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div style={{ background: "var(--surface)", border: "1px solid var(--line)", padding: "24px", maxWidth: "800px", width: "90%", maxHeight: "85vh", display: "flex", flexDirection: "column", borderRadius: "4px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <div>
                <h3 style={{ fontSize: "15px", fontWeight: 600 }}>{previewArticle.title}</h3>
                <span style={{ fontSize: "11px", color: "var(--muted)" }}>Keyword: <b>{previewArticle.keyword || "General"}</b></span>
              </div>
              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  className="btn"
                  style={{ fontSize: "11px", padding: "4px 10px" }}
                  onClick={() => handleCopyHtml(previewArticle.html_content || previewArticle.content || "")}
                >
                  {copied ? "✓ Copied!" : "📋 Copy HTML"}
                </button>
                <button className="btn" style={{ fontSize: "11px", padding: "4px 10px" }} onClick={() => setPreviewArticle(null)}>
                  ✕ Close
                </button>
              </div>
            </div>
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                background: "#fff",
                color: "#111",
                border: "1px solid var(--line)",
                padding: "20px 24px",
                fontFamily: "Georgia, serif",
                fontSize: "13px",
                lineHeight: "1.6",
              }}
              dangerouslySetInnerHTML={{ __html: previewArticle.html_content || previewArticle.content || "" }}
            />
          </div>
        </div>
      )}

      {/* ARTICLES TABLE */}
      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Articles Registry ({filteredArticles.length})</span>
          <button className="panel-action" onClick={loadArticles}>
            Refresh
          </button>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Target Keyword</th>
                <th>SEO Score</th>
                <th>Word Count</th>
                <th>Status</th>
                <th>WordPress Link</th>
                <th>Date</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: "center", padding: "30px", color: "var(--muted)" }}>
                    Loading articles...
                  </td>
                </tr>
              ) : filteredArticles.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: "center", padding: "30px", color: "var(--muted)" }}>
                    No articles found in this category.
                  </td>
                </tr>
              ) : (
                filteredArticles.map((a) => {
                  const score = a.seo_score ?? 85;
                  const scoreBadge = score >= 85 ? "badge-green" : score >= 70 ? "badge-amber" : "badge-red";
                  const isPublished = a.status === "published" || a.status === "approved";
                  return (
                    <tr key={a.id}>
                      <td style={{ fontWeight: 600, maxWidth: "260px" }}>{a.title}</td>
                      <td>
                        <span style={{ fontSize: "11px", color: "var(--ink)" }}>{a.keyword || "—"}</span>
                      </td>
                      <td>
                        <span className={`badge ${scoreBadge}`}>{score}/100</span>
                      </td>
                      <td>
                        <span style={{ fontSize: "11px", color: "var(--muted)" }}>{a.word_count || 1200}w</span>
                      </td>
                      <td>
                        <span className={`badge ${isPublished ? "badge-green" : a.status === "pending" ? "badge-accent" : "badge-ink"}`}>
                          {a.status}
                        </span>
                      </td>
                      <td>
                        {a.wordpress_url ? (
                          <a href={a.wordpress_url} target="_blank" rel="noreferrer" style={{ color: "var(--accent)", fontSize: "11px" }}>
                            WordPress Draft Link ↗
                          </a>
                        ) : (
                          <span style={{ color: "var(--muted)", fontSize: "11px" }}>—</span>
                        )}
                      </td>
                      <td style={{ fontSize: "10px", color: "var(--muted)" }}>
                        {a.created_at ? new Date(a.created_at).toLocaleDateString() : "Recent"}
                      </td>
                      <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                        <div style={{ display: "flex", gap: "6px", justifyContent: "flex-end" }}>
                          <button
                            className="btn"
                            style={{ padding: "3px 8px", fontSize: "10.5px" }}
                            onClick={() => setPreviewArticle(a)}
                          >
                            Preview HTML
                          </button>
                          {a.status === "pending" && a.approval_id && (
                            <button
                              className="btn btn-accent"
                              style={{ padding: "3px 8px", fontSize: "10.5px" }}
                              disabled={publishing === a.approval_id}
                              onClick={() => handleApprove(a.approval_id)}
                            >
                              Approve
                            </button>
                          )}
                          <button
                            className="btn"
                            style={{ padding: "3px 6px", fontSize: "10.5px", color: "var(--red)", borderColor: "rgba(255,85,85,0.4)" }}
                            onClick={() => handleDeleteArticle(a.id, a.title)}
                          >
                            🗑️
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
