"use client";

import React, { useEffect, useState, useCallback } from "react";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId, setCurrentWebsiteId, getWebsiteId } from "@/lib/website";

interface WordPressPost {
  id?: number | string;
  title: { rendered?: string } | string;
  status: string;
  link?: string;
  date?: string;
}

export default function WordPressPage() {
  const [wpUrl, setWpUrl] = useState<string>("");
  const [wpUser, setWpUser] = useState<string>("");
  const [wpPass, setWpPass] = useState<string>("");
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [connectedUser, setConnectedUser] = useState<string | null>(null);
  const [posts, setPosts] = useState<WordPressPost[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [noticeMsg, setNoticeMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [websiteId, setWebsiteId] = useState<string>("");

  const fetchLivePosts = async (targetWid?: string) => {
    const wid = targetWid || websiteId || getCurrentWebsiteId();
    if (!wid) return;

    try {
      setActionLoading(true);
      setNoticeMsg("Fetching live posts from WordPress REST API...");
      const res = await get(`/api/wordpress/${wid}/posts`);
      if (res?.posts && Array.isArray(res.posts)) {
        setPosts(res.posts);
        setNoticeMsg(`✓ Fetched ${res.posts.length} live posts from WordPress.`);
      } else {
        setPosts([]);
        setNoticeMsg("Fetched posts response: 0 posts found on WordPress.");
      }
    } catch (err: any) {
      setError(`Failed to fetch posts: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const loadStatus = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // 1. Resolve active website
      let wid = getCurrentWebsiteId() || getWebsiteId();
      let sites: any[] = [];
      try {
        const sitesRes = await get("/api/websites");
        sites = Array.isArray(sitesRes) ? sitesRes : [];
      } catch {}

      if (!wid && sites.length > 0) {
        wid = sites[0].id;
        setCurrentWebsiteId(wid);
        setWebsiteId(wid);
      }

      if (wid) {
        setWebsiteId(wid);
        const currentSite = sites.find((s: any) => s.id === wid) || (await get(`/api/websites/${wid}`).catch(() => null));
        if (currentSite) {
          const siteUrl = currentSite.wordpress_url || currentSite.cms_url || (currentSite.domain ? `https://${currentSite.domain}` : "");
          const siteUser = currentSite.wordpress_user || currentSite.cms_user || "";
          if (siteUrl) setWpUrl(siteUrl);
          if (siteUser) {
            setWpUser(siteUser);
            setConnectedUser(siteUser);
          }
          if (currentSite.app_password || currentSite.wordpress_password) {
            setIsConnected(true);
          }
        }

        // Try fetching live posts
        try {
          const postsRes = await get(`/api/wordpress/${wid}/posts`);
          if (postsRes?.posts && Array.isArray(postsRes.posts)) {
            setPosts(postsRes.posts);
            setIsConnected(true);
          }
        } catch {}
      }
    } catch (e: any) {
      console.warn("WP load error:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
    const handleWebsiteChange = (e: any) => {
      setWebsiteId(e.detail);
      loadStatus();
    };
    window.addEventListener("website-changed", handleWebsiteChange);
    return () => window.removeEventListener("website-changed", handleWebsiteChange);
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
      setNoticeMsg("Connecting to WordPress REST API and securing credentials...");

      let activeWid = websiteId || getCurrentWebsiteId();

      const res = await post(`/api/wordpress/${activeWid || "default"}/credentials`, {
        url: wpUrl.trim(),
        username: wpUser.trim(),
        password: wpPass.trim(),
      });

      const newWid = res?.website_id || activeWid;
      if (newWid) {
        setCurrentWebsiteId(newWid);
        setWebsiteId(newWid);
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("website-changed", { detail: newWid }));
        }
      }

      setIsConnected(true);
      setConnectedUser(wpUser.trim());
      setWpPass("");
      setNoticeMsg(`✓ Successfully connected to WordPress at ${wpUrl}!`);

      if (newWid) {
        await fetchLivePosts(newWid);
      }
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

      let activeWid = websiteId || getCurrentWebsiteId();

      const res = await post(`/api/wordpress/${activeWid || "default"}/test`, {
        url: wpUrl.trim(),
        username: wpUser.trim(),
        password: wpPass.trim(),
      });

      if (res && res.connected) {
        const newWid = res?.website_id || activeWid;
        if (newWid) {
          setCurrentWebsiteId(newWid);
          setWebsiteId(newWid);
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("website-changed", { detail: newWid }));
          }
        }
        setIsConnected(true);
        setConnectedUser(wpUser.trim());
        setNoticeMsg(`✓ WordPress REST connection verified: ${res.message}`);
        if (newWid) {
          await fetchLivePosts(newWid);
        }
      } else {
        setIsConnected(false);
        setError(res?.message || "WordPress connection test failed. Verify Application Password.");
      }
    } catch (err: any) {
      setIsConnected(false);
      setError(`Connection test failed: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div className="border-b border-ink/20 pb-4 flex items-center justify-between">
        <div>
          <h1 className="dot-font text-2xl text-ink font-bold tracking-wide">
            WORDPRESS MANAGER
          </h1>
          <p className="mono-font text-xs text-muted mt-1">
            Direct WordPress REST API Connection · 1-Click Publishing · Yoast & RankMath Meta Integration
          </p>
        </div>
        <div className="mono-font text-xs bg-stone border border-ink/40 px-3 py-1 text-accent flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-emerald-400" : "bg-amber-400"} animate-pulse`} />
          <span>{isConnected ? "STATUS: CONNECTED" : "STATUS: NOT CONNECTED"}</span>
        </div>
      </div>

      {noticeMsg && (
        <div className="p-3 bg-emerald-950/40 border border-emerald-500/50 text-emerald-400 mono-font text-xs flex items-center gap-2">
          <span>✓</span>
          <span>{noticeMsg}</span>
        </div>
      )}

      {error && (
        <div className="p-3 bg-red-950/40 border border-red-500/50 text-red-400 mono-font text-xs flex items-center gap-2">
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Credentials Form */}
        <div className="lg:col-span-7 bg-stone border border-ink/30 p-6">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-ink/20">
            <div className="flex items-center gap-2">
              <span className="text-accent text-sm">◆</span>
              <h2 className="dot-font text-sm text-ink font-bold tracking-wider">
                WORDPRESS CONNECTION
              </h2>
            </div>
            <span className={`mono-font text-[10px] px-2 py-0.5 border ${isConnected ? "bg-emerald-950/40 border-emerald-500/40 text-emerald-400" : "bg-amber-950/40 border-amber-500/40 text-amber-400"}`}>
              {isConnected ? "CONNECTED" : "UNCONFIGURED"}
            </span>
          </div>

          <form onSubmit={handleSaveAndConnect} className="space-y-4">
            <div>
              <label className="block mono-font text-xs text-muted mb-1 uppercase">
                WordPress Site URL
              </label>
              <input
                type="url"
                value={wpUrl}
                onChange={(e) => setWpUrl(e.target.value)}
                placeholder="https://yourdomain.com"
                className="w-full bg-paper border border-ink/30 px-3 py-2 text-ink mono-font text-sm focus:border-accent focus:outline-none"
                disabled={actionLoading}
                required
              />
            </div>

            <div>
              <label className="block mono-font text-xs text-muted mb-1 uppercase">
                Auth Username
              </label>
              <input
                type="text"
                value={wpUser}
                onChange={(e) => setWpUser(e.target.value)}
                placeholder="admin"
                className="w-full bg-paper border border-ink/30 px-3 py-2 text-ink mono-font text-sm focus:border-accent focus:outline-none"
                disabled={actionLoading}
                required
              />
            </div>

            <div>
              <label className="block mono-font text-xs text-muted mb-1 uppercase">
                Application Password
              </label>
              <input
                type="password"
                value={wpPass}
                onChange={(e) => setWpPass(e.target.value)}
                placeholder={isConnected ? "•••••••••••••••• (Saved)" : "abcd 1234 efgh 5678"}
                className="w-full bg-paper border border-ink/30 px-3 py-2 text-ink mono-font text-sm focus:border-accent focus:outline-none"
                autoComplete="new-password"
                autoCorrect="off"
                spellCheck={false}
                disabled={actionLoading}
              />
              <p className="mono-font text-[10px] text-muted mt-1">
                Generate in WP Admin → Users → Profile → Application Passwords. Stored Fernet-encrypted.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <button
                type="submit"
                disabled={actionLoading}
                className="px-5 py-2 bg-accent hover:bg-accent/90 text-paper font-bold mono-font text-xs uppercase tracking-wider transition-colors shadow-md disabled:opacity-50"
              >
                {actionLoading ? "SAVING..." : "SAVE & CONNECT"}
              </button>

              <button
                type="button"
                onClick={handleTestConnection}
                disabled={actionLoading}
                className="px-4 py-2 bg-paper hover:bg-stone border border-ink/40 text-ink mono-font text-xs uppercase tracking-wider transition-colors disabled:opacity-50"
              >
                TEST CONNECTION
              </button>

              <button
                type="button"
                onClick={() => fetchLivePosts()}
                disabled={actionLoading || !websiteId}
                className="px-4 py-2 bg-paper hover:bg-stone border border-ink/40 text-accent mono-font text-xs uppercase tracking-wider transition-colors disabled:opacity-50"
              >
                SYNC POSTS
              </button>
            </div>
          </form>
        </div>

        {/* Right Column: Publishing Capabilities & Engine Status */}
        <div className="lg:col-span-5 bg-stone border border-ink/30 p-6">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-ink/20">
            <h2 className="dot-font text-sm text-ink font-bold tracking-wider">
              PUBLISHING ENGINE & CAPABILITIES
            </h2>
            <span className="mono-font text-[10px] px-2 py-0.5 bg-emerald-950/40 border border-emerald-500/40 text-emerald-400">
              READY
            </span>
          </div>

          <p className="mono-font text-xs text-muted mb-4 leading-relaxed">
            When content is approved in RankForge, articles are pushed directly to WordPress with full Gutenberg/HTML formatting and Yoast/RankMath SEO focus keywords.
          </p>

          <div className="space-y-3 mono-font text-xs">
            <div className="p-2.5 bg-paper border border-ink/20 flex items-center justify-between">
              <span className="text-muted">✓ REST API endpoint: /wp-json/wp/v2/posts</span>
              <span className="text-emerald-400 font-bold">SUPPORTED</span>
            </div>
            <div className="p-2.5 bg-paper border border-ink/20 flex items-center justify-between">
              <span className="text-muted">✓ Post status: Draft, Pending, or Instant Publish</span>
              <span className="text-emerald-400 font-bold">CONFIGURED</span>
            </div>
            <div className="p-2.5 bg-paper border border-ink/20 flex items-center justify-between">
              <span className="text-muted">✓ Yoast / RankMath Focus Keyword mapping</span>
              <span className="text-emerald-400 font-bold">ACTIVE</span>
            </div>
            <div className="p-2.5 bg-paper border border-ink/20 flex items-center justify-between">
              <span className="text-muted">✓ Instant XML Sitemap Ping after publish</span>
              <span className="text-emerald-400 font-bold">ACTIVE</span>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Section: Live WordPress Published Articles */}
      <div className="bg-stone border border-ink/30 p-6">
        <div className="flex items-center justify-between mb-4 pb-2 border-b border-ink/20">
          <div className="flex items-center gap-2">
            <h2 className="dot-font text-sm text-ink font-bold tracking-wider">
              LIVE WORDPRESS PUBLISHED ARTICLES
            </h2>
            <span className="mono-font text-[10px] px-2 py-0.5 bg-paper border border-ink/30 text-accent">
              {posts.length} POSTS
            </span>
          </div>
          <button
            onClick={() => fetchLivePosts()}
            disabled={actionLoading || !websiteId}
            className="px-3 py-1 bg-accent/10 border border-accent/30 text-accent mono-font text-xs uppercase hover:bg-accent/20 transition-colors disabled:opacity-50"
          >
            FETCH POSTS
          </button>
        </div>

        {posts.length === 0 ? (
          <div className="py-12 text-center mono-font text-xs text-muted border border-dashed border-ink/20">
            No published WordPress posts fetched yet. Enter credentials above and click &quot;Save &amp; Connect&quot; or &quot;Sync Posts&quot;.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left mono-font text-xs">
              <thead className="border-b border-ink/20 text-muted uppercase text-[10px]">
                <tr>
                  <th className="py-2 px-3">Title</th>
                  <th className="py-2 px-3">Status</th>
                  <th className="py-2 px-3">Link</th>
                  <th className="py-2 px-3">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink/10">
                {posts.map((p, idx) => {
                  const postTitle = typeof p.title === "object" ? p.title?.rendered : p.title;
                  return (
                    <tr key={p.id || idx} className="hover:bg-paper/40 transition-colors">
                      <td className="py-3 px-3 font-bold text-ink max-w-md truncate" dangerouslySetInnerHTML={{ __html: postTitle || "Untitled Post" }} />
                      <td className="py-3 px-3">
                        <span className="px-2 py-0.5 bg-emerald-950/40 border border-emerald-500/40 text-emerald-400 text-[10px]">
                          {p.status || "published"}
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        {p.link ? (
                          <a href={p.link} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                            View on Site ↗
                          </a>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-muted">
                        {p.date ? new Date(p.date).toLocaleDateString() : "Recent"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
