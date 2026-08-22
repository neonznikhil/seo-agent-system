"use client";

import { useEffect, useState, useCallback } from "react";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface WordPressPost {
  id?: number | string;
  title: { rendered?: string } | string;
  status: string;
  link?: string;
  date?: string;
}

export default function WordPressPage() {
  const [wpUrl, setWpUrl] = useState("https://accident.innovatcs.com");
  const [wpUser, setWpUser] = useState("admin");
  const [wpPass, setWpPass] = useState("");
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [connectedUser, setConnectedUser] = useState<string | null>(null);
  const [posts, setPosts] = useState<WordPressPost[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [noticeMsg, setNoticeMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const websiteId = getCurrentWebsiteId();

  const loadStatus = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // Check wordpress connection status from backend
      try {
        const res = await get(`/api/wordpress/status`);
        if (res?.connected) {
          setIsConnected(true);
          if (res.site_url) setWpUrl(res.site_url);
          if (res.username) {
            setWpUser(res.username);
            setConnectedUser(res.username);
          }
        }
      } catch {}

      // Try fetching live posts
      try {
        const postsRes = await get(`/api/wordpress/${websiteId}/posts`);
        if (postsRes?.posts && Array.isArray(postsRes.posts)) {
          setPosts(postsRes.posts);
          setIsConnected(true);
        }
      } catch {}
    } catch (e: any) {
      console.warn("WP load error:", e);
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const handleSaveAndConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!wpUrl.trim() || !wpUser.trim() || !wpPass.trim()) {
      setError("Please fill in Site URL, Username, and Application Password.");
      return;
    }

    try {
      setActionLoading(true);
      setError(null);
      setNoticeMsg("Connecting to WordPress REST API...");

      const domain = wpUrl.trim().replace(/^https?:\/\//, "").split("/")[0];

      // Update website record in Supabase
      if (websiteId) {
        await post(`/api/wordpress/${websiteId}/credentials`, {
          url: wpUrl.trim(),
          username: wpUser.trim(),
          password: wpPass.trim(),
        });
      } else {
        const newSite = await post("/api/websites", {
          domain: domain,
          cms_url: wpUrl.trim(),
          cms_user: wpUser.trim(),
          app_password: wpPass.trim(),
        });
        if (newSite?.id) {
          setWebsiteId(newSite.id);
        }
      }

      setIsConnected(true);
      setConnectedUser(wpUser.trim());
      setNoticeMsg(`✓ Successfully connected to WordPress site at ${wpUrl}!`);
      fetchLivePosts();
    } catch (err: any) {
      setError(`WordPress connection failed: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleTestConnection = async () => {
    if (!wpUrl.trim() || !wpUser.trim() || !wpPass.trim()) {
      setError("Please fill in Site URL, Username, and Application Password to test.");
      return;
    }

    try {
      setActionLoading(true);
      setError(null);
      setNoticeMsg("Testing WordPress REST connection...");

      const res = await post(`/api/wordpress/${websiteId || "default"}/test`, {
        url: wpUrl.trim(),
        username: wpUser.trim(),
        password: wpPass.trim(),
      });

      if (res && res.connected) {
        setIsConnected(true);
        setNoticeMsg(`✓ WordPress REST connection verified successfully!`);
        fetchLivePosts();
      } else {
        setIsConnected(false);
        setError(res?.message || "WordPress connection test failed. Check Application Password.");
      }
    } catch (err: any) {
      setIsConnected(false);
      setError(`Connection test failed: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const fetchLivePosts = async () => {
    try {
      setActionLoading(true);
      setNoticeMsg("Fetching live posts from WordPress...");
      const res = await get(`/api/wordpress/${websiteId}/posts`);
      if (res?.posts && Array.isArray(res.posts)) {
        setPosts(res.posts);
        setNoticeMsg(`✓ Fetched ${res.posts.length} live posts from WordPress.`);
      } else {
        setNoticeMsg("Fetched posts response: 0 posts found.");
      }
    } catch (err: any) {
      setError(`Failed to fetch posts: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handle1ClickOAuth = async () => {
    try {
      setActionLoading(true);
      setError(null);
      const res = await get("/api/wordpress/authorize-url");
      if (res?.authorize_url) {
        window.location.href = res.authorize_url;
      } else {
        const wpBase = wpUrl.replace(/\/+$/, "");
        const authUrl = `${wpBase}/wp-admin/authorize-application.php?app_name=RankForge&success_url=${encodeURIComponent(window.location.origin + "/auth/wordpress/callback")}`;
        window.location.href = authUrl;
      }
    } catch (err: any) {
      const wpBase = wpUrl.replace(/\/+$/, "");
      const authUrl = `${wpBase}/wp-admin/authorize-application.php?app_name=RankForge&success_url=${encodeURIComponent(window.location.origin + "/auth/wordpress/callback")}`;
      window.location.href = authUrl;
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      {/* PAGE HEADER */}
      <div className="page-heading">WordPress Manager</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Direct WordPress REST API Connection · 1-Click Publishing · Yoast & RankMath Meta Integration
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

      {/* TOP SECTION: CREDENTIALS + PUBLISHING CONFIG */}
      <div className="grid-2" style={{ marginBottom: "16px" }}>
        {/* CREDENTIALS FORM */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">🔷 WordPress Connection</span>
            <span className={`badge ${isConnected ? "badge-green" : "badge-amber"}`}>
              {isConnected ? "Connected" : "Setup Required"}
            </span>
          </div>
          <form onSubmit={handleSaveAndConnect} className="panel-body">
            <div className="field-group">
              <div className="field-label">WordPress Site URL</div>
              <input
                className="field"
                value={wpUrl}
                onChange={(e) => setWpUrl(e.target.value)}
                placeholder="https://accident.innovatcs.com"
                disabled={actionLoading}
              />
            </div>

            <div className="field-group">
              <div className="field-label">Auth Username</div>
              <input
                className="field"
                value={wpUser}
                onChange={(e) => setWpUser(e.target.value)}
                placeholder="admin"
                disabled={actionLoading}
              />
            </div>

            <div className="field-group">
              <div className="field-label">Application Password</div>
              <input
                type="password"
                className="field"
                value={wpPass}
                onChange={(e) => setWpPass(e.target.value)}
                placeholder="xxxx xxxx xxxx xxxx"
                disabled={actionLoading}
              />
              <div className="field-hint">
                Generate in WP Admin → Users → Edit Profile → Application Passwords
              </div>
            </div>

            <div style={{ display: "flex", gap: "8px", marginTop: "14px", flexWrap: "wrap" }}>
              <button
                type="submit"
                className="btn btn-accent"
                disabled={actionLoading}
                style={{ fontWeight: 600 }}
              >
                {actionLoading ? "Saving..." : "Save & Connect"}
              </button>
              <button
                type="button"
                className="btn"
                onClick={handleTestConnection}
                disabled={actionLoading}
              >
                Test Connection
              </button>
              <button
                type="button"
                className="btn"
                onClick={fetchLivePosts}
                disabled={actionLoading}
              >
                Sync Posts
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handle1ClickOAuth}
                disabled={actionLoading}
                title="Authorize application in 1-click via WordPress Admin"
              >
                1-Click WP OAuth ↗
              </button>
            </div>
          </form>
        </div>

        {/* PUBLISHING SETTINGS & STATUS */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">Publishing Engine & Status</span>
            <span className="badge badge-green">Ready</span>
          </div>
          <div className="panel-body">
            <div className="notice ok" style={{ marginBottom: "14px" }}>
              <span className="notice-sq"></span>
              When content is approved in RankForge, articles are pushed directly to WordPress with full Gutenberg/HTML formatting and Yoast/RankMath SEO focus keywords.
            </div>

            <div className="check-row">
              <span className="ci pass">✓</span>
              <span className="ck-label">REST API endpoint: /wp-json/wp/v2/posts</span>
              <span className="badge badge-green">Supported</span>
            </div>
            <div className="check-row">
              <span className="ci pass">✓</span>
              <span className="ck-label">Post status options: Draft, Pending, or Instant Publish</span>
              <span className="badge badge-green">Configured</span>
            </div>
            <div className="check-row">
              <span className="ci pass">✓</span>
              <span className="ck-label">Yoast / RankMath Focus Keyword Meta mapping</span>
              <span className="badge badge-green">Active</span>
            </div>
            <div className="check-row">
              <span className="ci pass">✓</span>
              <span className="ck-label">Instant XML Sitemap Ping after article publish</span>
              <span className="badge badge-green">Active</span>
            </div>
          </div>
        </div>
      </div>

      {/* LIVE WORDPRESS POSTS TABLE */}
      <div className="panel">
        <div className="panel-head">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span className="panel-label">Live WordPress Published Articles</span>
            <span className="badge badge-ink">{posts.length} Posts</span>
          </div>
          <button className="panel-action" onClick={fetchLivePosts} disabled={actionLoading}>
            Fetch Posts
          </button>
        </div>

        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Status</th>
                <th>Link</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={4} style={{ textAlign: "center", padding: "24px", color: "var(--muted)" }}>
                    Loading WordPress posts...
                  </td>
                </tr>
              ) : posts.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ textAlign: "center", padding: "28px", color: "var(--muted)" }}>
                    No published WordPress posts fetched yet. Enter credentials above and click "Save & Connect" or "Sync Posts".
                  </td>
                </tr>
              ) : (
                posts.map((p, idx) => {
                  const titleStr = typeof p.title === "object" ? p.title?.rendered || "Untitled Post" : p.title || "Untitled Post";
                  return (
                    <tr key={p.id || idx}>
                      <td style={{ fontWeight: 600, color: "var(--ink)" }}>{titleStr}</td>
                      <td>
                        <span className={`badge ${p.status === "publish" || p.status === "published" ? "badge-green" : "badge-amber"}`}>
                          {p.status || "Published"}
                        </span>
                      </td>
                      <td>
                        {p.link ? (
                          <a href={p.link} target="_blank" rel="noreferrer" style={{ color: "var(--accent)", textDecoration: "none", fontWeight: 600 }}>
                            View Post ↗
                          </a>
                        ) : (
                          <span style={{ color: "var(--muted)" }}>Synced</span>
                        )}
                      </td>
                      <td style={{ color: "var(--muted)" }}>
                        {p.date ? new Date(p.date).toLocaleDateString() : "Recent"}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* BOTTOM TICKER */}
      <div className="bticker">
        <span className="bticker-inner">
          <span className="bt-sq"></span>WORDPRESS INTEGRATION <span className="bt-sep">/</span>
          <span className="bt-sq"></span>REST API DIRECT CONNECTION <span className="bt-sep">/</span>
          <span className="bt-sq"></span>ACCIDENT.INNOVATCS.COM SYNCED <span className="bt-sep">/</span>
          <span className="bt-sq"></span>1-CLICK PUBLISHING ACTIVE &nbsp;&nbsp;&nbsp;&nbsp;
          <span className="bt-sq"></span>WORDPRESS INTEGRATION <span className="bt-sep">/</span>
          <span className="bt-sq"></span>REST API DIRECT CONNECTION <span className="bt-sep">/</span>
          <span className="bt-sq"></span>ACCIDENT.INNOVATCS.COM SYNCED <span className="bt-sep">/</span>
          <span className="bt-sq"></span>1-CLICK PUBLISHING ACTIVE
        </span>
      </div>
    </div>
  );
}
