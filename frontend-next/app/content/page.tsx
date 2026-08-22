"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface BlogArticle {
  id: string;
  title: string;
  keyword?: string;
  content?: string;
  status: string;
  created_at?: string;
}

export default function ContentPage() {
  const [articles, setArticles] = useState<BlogArticle[]>([]);
  const [selectedArticle, setSelectedArticle] = useState<BlogArticle | null>(null);
  const [loading, setLoading] = useState(true);
  const [isPublishing, setIsPublishing] = useState(false);
  const [noticeMsg, setNoticeMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const websiteId = getCurrentWebsiteId();

  const loadArticles = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch from /api/blogs or fallback to /writer
      try {
        const res = await get(`/api/blogs?website_id=${websiteId}`);
        if (Array.isArray(res)) {
          setArticles(res);
          return;
        }
      } catch {}

      const data = await get(`/api/content?website_id=${websiteId}`);
      setArticles(Array.isArray(data) ? data : []);
    } catch (e: any) {
      console.warn("Articles load error:", e);
      setArticles([]);
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  useEffect(() => {
    loadArticles();
  }, [loadArticles]);

  const handlePublish = async (article: BlogArticle) => {
    try {
      setIsPublishing(true);
      setError(null);

      const res = await post("/api/wordpress/publish", {
        title: article.title,
        content: article.content || article.title,
        status: "publish",
      });

      setNoticeMsg(`✓ Successfully published "${article.title}" to WordPress!`);
      setArticles((prev) =>
        prev.map((a) => (a.id === article.id ? { ...a, status: "published" } : a))
      );
      if (selectedArticle?.id === article.id) {
        setSelectedArticle({ ...selectedArticle, status: "published" });
      }
    } catch (err: any) {
      setError(`WordPress publish error: ${err.message}`);
    } finally {
      setIsPublishing(false);
    }
  };

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      {/* PAGE HEADER */}
      <div className="page-heading">Content Studio</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Autonomous Articles · Review Queue · Direct WordPress Dispatch · Supabase Content Log
      </div>

      {/* NOTICES */}
      {error && (
        <div className="notice" style={{ borderColor: "var(--red)", background: "rgba(239,68,68,0.08)" }}>
          <span className="notice-sq" style={{ background: "var(--red)" }}></span>
          <span style={{ color: "var(--red)" }}>{error}</span>
        </div>
      )}

      {noticeMsg && (
        <div className="notice ok">
          <span className="notice-sq"></span>
          <span>{noticeMsg}</span>
        </div>
      )}

      {/* TOP ACTION BAR */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <span className="badge badge-ink">{articles.length} Articles Total</span>
          <span className="badge badge-green">
            {articles.filter((a) => a.status === "published").length} Published
          </span>
          <span className="badge badge-accent">
            {articles.filter((a) => a.status !== "published").length} Pending
          </span>
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          <button className="btn" onClick={loadArticles}>
            Refresh
          </button>
          <Link href="/generate" className="btn btn-accent" style={{ textDecoration: "none", fontWeight: 600 }}>
            + Generate New Article
          </Link>
        </div>
      </div>

      {/* ARTICLES TABLE */}
      <div className="panel" style={{ marginBottom: "16px" }}>
        <div className="panel-head">
          <span className="panel-label">Articles in Supabase Content Log</span>
        </div>

        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Title / Topic</th>
                <th>Target Keyword</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: "center", padding: "24px", color: "var(--muted)" }}>
                    Loading articles from Supabase...
                  </td>
                </tr>
              ) : articles.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: "center", padding: "32px", color: "var(--muted)" }}>
                    No articles found in content log. Click "+ Generate New Article" above to create your first post!
                  </td>
                </tr>
              ) : (
                articles.map((item) => (
                  <tr key={item.id}>
                    <td style={{ fontWeight: 600, color: "var(--ink)", maxWidth: "340px" }}>
                      {item.title}
                    </td>
                    <td style={{ color: "var(--muted)" }}>{item.keyword || "—"}</td>
                    <td>
                      <span className={`badge ${item.status === "published" ? "badge-green" : "badge-accent"}`}>
                        {item.status || "draft"}
                      </span>
                    </td>
                    <td style={{ color: "var(--muted)" }}>
                      {item.created_at ? new Date(item.created_at).toLocaleDateString() : "Recent"}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "6px" }}>
                        <button
                          className="btn"
                          style={{ padding: "3px 8px", fontSize: "9px" }}
                          onClick={() => setSelectedArticle(item)}
                        >
                          Preview
                        </button>
                        {item.status !== "published" && (
                          <button
                            className="btn btn-accent"
                            style={{ padding: "3px 8px", fontSize: "9px" }}
                            onClick={() => handlePublish(item)}
                            disabled={isPublishing}
                          >
                            Publish
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ARTICLE PREVIEW MODAL */}
      {selectedArticle && (
        <div className="modal-backdrop active">
          <div className="modal-card" style={{ maxWidth: "750px" }}>
            <div className="modal-head">
              <span className="modal-title">📄 {selectedArticle.title}</span>
              <button className="modal-close" onClick={() => setSelectedArticle(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <div style={{ display: "flex", gap: "10px", marginBottom: "12px" }}>
                <span className="badge badge-ink">Keyword: {selectedArticle.keyword || "General"}</span>
                <span className={`badge ${selectedArticle.status === "published" ? "badge-green" : "badge-accent"}`}>
                  {selectedArticle.status}
                </span>
              </div>
              <textarea
                className="field"
                rows={16}
                value={selectedArticle.content || selectedArticle.title}
                readOnly
                style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px", lineHeight: "1.7" }}
              />
            </div>
            <div className="modal-foot">
              <button className="btn" onClick={() => setSelectedArticle(null)}>
                Close
              </button>
              {selectedArticle.status !== "published" && (
                <button
                  className="btn btn-accent"
                  onClick={() => handlePublish(selectedArticle)}
                  disabled={isPublishing}
                  style={{ fontWeight: 600 }}
                >
                  {isPublishing ? "Publishing to WordPress..." : "🔷 Publish to WordPress"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* BOTTOM TICKER */}
      <div className="bticker">
        <span className="bticker-inner">
          <span className="bt-sq"></span>CONTENT STUDIO <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SUPABASE CONTENT LOG <span className="bt-sep">/</span>
          <span className="bt-sq"></span>WORDPRESS DISPATCH ACTIVE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>ZERO MOCK DATA &nbsp;&nbsp;&nbsp;&nbsp;
          <span className="bt-sq"></span>CONTENT STUDIO <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SUPABASE CONTENT LOG <span className="bt-sep">/</span>
          <span className="bt-sq"></span>WORDPRESS DISPATCH ACTIVE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>ZERO MOCK DATA
        </span>
      </div>
    </div>
  );
}