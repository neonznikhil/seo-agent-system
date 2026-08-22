"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId, getWebsiteId } from "@/lib/website";

interface BlogArticle {
  id: string;
  title: string;
  keyword?: string;
  content?: string;
  status: string;
  created_at?: string;
  wp_post_id?: number | string;
  wp_draft_url?: string;
}

export default function ContentPage() {
  const [articles, setArticles] = useState<BlogArticle[]>([]);
  const [selectedArticle, setSelectedArticle] = useState<BlogArticle | null>(null);
  const [loading, setLoading] = useState(true);
  const [publishing, setPublishing] = useState<string | null>(null);
  const [noticeMsg, setNoticeMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [websiteId, setWebsiteId] = useState<string>("");

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

      let data: any = null;
      try {
        data = await get(`/api/writer/${wid}/content`);
      } catch {
        try {
          data = await get(`/api/content?website_id=${wid}`);
        } catch {
          data = await get(`/api/blogs?website_id=${wid}`);
        }
      }

      const list = Array.isArray(data) ? data : data?.data || [];
      setArticles(list);
      if (list.length > 0 && !selectedArticle) {
        setSelectedArticle(list[0]);
      }
    } catch (e: any) {
      console.warn("Articles load error:", e);
      setError(e.message || "Failed to load content log");
      setArticles([]);
    } finally {
      setLoading(false);
    }
  }, [selectedArticle]);

  const fetchContent = loadArticles;

  useEffect(() => {
    loadArticles();
    const handleChanged = () => loadArticles();
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [loadArticles]);

  const handlePublishToWordPress = async (contentId: string) => {
    setPublishing(contentId);
    try {
      const activeWebsiteId = getWebsiteId() || websiteId;
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

      // Step 1: Get the content
      const contentRes = await fetch(
        `${apiUrl}/content/${activeWebsiteId}/${contentId}`
      );
      if (!contentRes.ok) throw new Error("Could not load content");
      const content = await contentRes.json();

      // Step 2: Create WordPress draft
      const wpRes = await fetch(
        `${apiUrl}/wordpress/${activeWebsiteId}/create-draft`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-User-Id": "human-approved",
          },
          body: JSON.stringify({
            content_id: contentId,
            title: content.title,
            content: content.content || content.body,
          }),
        }
      );

      if (!wpRes.ok) {
        const err = await wpRes.json();
        throw new Error(err.detail || "WordPress push failed");
      }

      const wpData = await wpRes.json();

      if (wpData.success) {
        alert(`✅ Draft created in WordPress!\nEdit here: ${wpData.edit_url}`);
        // Refresh content list
        fetchContent();
      } else {
        alert(`❌ Failed: ${wpData.message}`);
      }
    } catch (err: any) {
      alert(`Error: ${err.message}\n\nMake sure:\n1. Backend is running on port 8000\n2. WordPress is connected in Settings`);
    } finally {
      setPublishing(null);
    }
  };

  if (loading && articles.length === 0) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px auto" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Loading content studio and articles log...
        </p>
      </div>
    );
  }

  if (!websiteId) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">Content Studio</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No data yet — add a website first.</strong> Connect your website to view autonomous articles, review drafts, and publish to WordPress.
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
      <div className="page-heading">Content Studio</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Autonomous Articles · Review Queue · Direct WordPress Dispatch · Supabase Content Log
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

      <div className="dash-grid">
        {/* LEFT COLUMN: ARTICLES LIST */}
        <div>
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Articles Log ({articles.length})</span>
              <button className="panel-action" onClick={loadArticles}>
                Refresh
              </button>
            </div>
            <div className="panel-body" style={{ maxHeight: "600px", overflowY: "auto" }}>
              {articles.length === 0 ? (
                <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
                  No content records found for this website.
                  <div style={{ marginTop: "10px" }}>
                    <Link href="/writer" className="btn btn-accent" style={{ textDecoration: "none", fontSize: "11px" }}>
                      ⚡ Write First Article
                    </Link>
                  </div>
                </div>
              ) : (
                articles.map((a) => (
                  <div
                    key={a.id}
                    onClick={() => setSelectedArticle(a)}
                    style={{
                      padding: "12px 14px",
                      borderBottom: "1px solid var(--line)",
                      cursor: "pointer",
                      background: selectedArticle?.id === a.id ? "rgba(255, 77, 18, 0.08)" : "transparent",
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: "13px" }}>{a.title}</div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "6px" }}>
                      <span className={`badge ${a.status === "published" ? "badge-green" : "badge-accent"}`}>
                        {a.status}
                      </span>
                      <span style={{ fontSize: "10px", color: "var(--muted)" }}>
                        {a.created_at ? new Date(a.created_at).toLocaleDateString() : "Recent"}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: PREVIEW */}
        <div>
          {selectedArticle ? (
            <div className="panel">
              <div className="panel-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="panel-label">Article Review</span>
                {selectedArticle.status !== "published" && (
                  <button
                    onClick={() => handlePublishToWordPress(selectedArticle.id)}
                    disabled={publishing === selectedArticle.id}
                    className="btn btn-accent"
                    style={{ padding: "6px 14px", fontSize: "11px" }}
                  >
                    {publishing === selectedArticle.id ? "Publishing..." : "🚀 Publish to WordPress"}
                  </button>
                )}
              </div>
              <div className="panel-body">
                <h1 style={{ fontSize: "18px", fontWeight: "bold", marginBottom: "12px" }}>{selectedArticle.title}</h1>
                <div
                  style={{
                    maxHeight: "500px",
                    overflowY: "auto",
                    padding: "16px",
                    background: "var(--surface)",
                    border: "1px solid var(--line)",
                    fontSize: "13px",
                    lineHeight: "1.6",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {selectedArticle.content || "No article content available."}
                </div>
              </div>
            </div>
          ) : (
            <div className="panel" style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              Select an article to review its content and publish status.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}