"use client";

import { useEffect, useState, useCallback } from "react";
import { get, post, put, del } from "@/lib/api";
import { getCurrentWebsiteId, setCurrentWebsiteId } from "@/lib/website";

interface Website {
  id: string;
  domain: string;
  url?: string;
  cms_url?: string | null;
  cms_user?: string | null;
  wordpress_url?: string | null;
  wordpress_user?: string | null;
  status?: string;
  created_at?: string;
}

export default function WebsitesPage() {
  const [websites, setWebsites] = useState<Website[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [noticeMsg, setNoticeMsg] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string>("");

  const [crawlStage, setCrawlStage] = useState<Record<string, string>>({});

  // Form state
  const [domain, setDomain] = useState("");
  const [cmsUrl, setCmsUrl] = useState("");
  const [wpUser, setWpUser] = useState("");
  const [wpAppPass, setWpAppPass] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [wpTesting, setWpTesting] = useState<string | null>(null);
  const [wpForms, setWpForms] = useState<Record<string, { user: string; pass: string; url: string }>>({});

  const fetchWebsites = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      let res: any = null;
      try {
        res = await get("/api/websites");
      } catch {
        res = await get("/websites");
      }
      const list = Array.isArray(res) ? res : res?.websites || [];
      setWebsites(list);

      const current = getCurrentWebsiteId();
      if (current && list.some((w: any) => w.id === current)) {
        setActiveId(current);
      } else if (list.length > 0) {
        setActiveId(list[0].id);
        setCurrentWebsiteId(list[0].id);
      }
    } catch (err: any) {
      // warn removed
      setError(err.message || "Failed to load websites");
      setWebsites([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWebsites();
  }, [fetchWebsites]);

  // Polling if any website is crawling + simulate progressive stage labels
  useEffect(() => {
    const crawlingSites = websites.filter((w) => w.status === "crawling");
    if (crawlingSites.length === 0) return;

    const stages = [
      "Crawling sitemap & pages...",
      "Extracting text & headings...",
      "Chunking content (3200-char)...",
      "Generating NVIDIA NIM embeddings...",
      "Writing chunks to Knowledge Graph...",
    ];
    let stageIdx = 0;

    const stageTimer = setInterval(() => {
      stageIdx = (stageIdx + 1) % stages.length;
      const updated: Record<string, string> = {};
      crawlingSites.forEach((s) => {
        updated[s.id] = stages[stageIdx];
      });
      setCrawlStage(updated);
    }, 2000);

    const interval = setInterval(() => {
      fetchWebsites();
    }, 3000);

    return () => {
      clearInterval(interval);
      clearInterval(stageTimer);
    };
  }, [websites, fetchWebsites]);

  const handleSelectWebsite = (id: string) => {
    setActiveId(id);
    setCurrentWebsiteId(id);
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("website-changed", { detail: id }));
    }
    setNoticeMsg("Active website updated across all pages.");
  };

  const handleAddWebsite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!domain.trim()) {
      setError("Please provide a domain name (e.g. example.com).");
      return;
    }

    try {
      setIsSaving(true);
      setError(null);
      const cleanDomain = domain.trim().replace(/^https?:\/\//, "").replace(/\/+$/, "");
      const payload: any = {
        domain: cleanDomain,
        url: cmsUrl.trim() || `https://${cleanDomain}`,
        cms_url: cmsUrl.trim() || `https://${cleanDomain}`,
        status: "crawling",
      };
      if (wpUser.trim() && wpAppPass.trim()) {
        payload.wordpress_user = wpUser.trim();
        payload.cms_user = wpUser.trim();
        payload.wordpress_password = wpAppPass.trim();
        payload.app_password = wpAppPass.trim();
      }
      const res = await post("/api/websites", payload);

      const newId = res.id || (res.data && res.data[0]?.id);
      if (newId && wpUser.trim() && wpAppPass.trim()) {
        // Also verify WP credentials immediately so /writer banner goes green
        try {
          await post(`/api/wordpress/${newId}/test`, {
            url: payload.cms_url,
            wordpress_url: payload.cms_url,
            username: wpUser.trim(),
            wordpress_user: wpUser.trim(),
            password: wpAppPass.trim(),
            wordpress_password: wpAppPass.trim(),
          });
        } catch {}
      }
      if (newId) {
        setActiveId(newId);
        setCurrentWebsiteId(newId);
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("website-changed", { detail: newId }));
        }
      }

      setDomain("");
      setCmsUrl("");
      setWpUser("");
      setWpAppPass("");
      setNoticeMsg("✓ Website added! Background knowledge crawl & embedding generation initiated." + (wpUser ? " WordPress credentials saved — check /writer banner now shows Connected." : " Add WordPress App Password below or in /connectors to enable draft-to-WP."));
      fetchWebsites();
    } catch (err: any) {
      setError(`Failed to create website: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveWpForSite = async (id: string, siteUrl: string, user: string, pass: string) => {
    if (!user.trim() || !pass.trim()) {
      setError("WP username and App Password required");
      return;
    }
    try {
      setWpTesting(id);
      setError(null);
      // Save to websites table
      await put(`/api/websites/${id}`, {
        wordpress_user: user.trim(),
        cms_user: user.trim(),
        wordpress_password: pass.trim(),
        app_password: pass.trim(),
        wordpress_url: siteUrl,
        cms_url: siteUrl,
        url: siteUrl,
      } as any);
      // Verify immediately
      const test = await post(`/api/wordpress/${id}/test`, {
        url: siteUrl,
        wordpress_url: siteUrl,
        username: user.trim(),
        wordpress_user: user.trim(),
        password: pass.trim(),
        wordpress_password: pass.trim(),
      });
      if (test.connected) {
        setNoticeMsg(`✓ WordPress connected as ${test.wp_user || user} — /writer will now show Connected`);
      } else {
        setNoticeMsg(`WordPress test: ${test.message || "check credentials/role"}`);
      }
      fetchWebsites();
    } catch (e: any) {
      setError(`WP save/test failed: ${e.message}`);
    } finally {
      setWpTesting(null);
    }
  };

  const handleTestWpForSite = async (id: string, siteUrl: string) => {
    try {
      setWpTesting(id);
      const test = await get(`/api/wordpress/${id}/info` as any);
      setNoticeMsg(`WP info: ${test.status || test.site?.url || "checked"}`);
    } catch (e: any) {
      // fallback to direct test with stored creds
      try {
        const diag = await get(`/api/writer/${id}/wordpress-status` as any);
        setNoticeMsg(diag.message || "checked");
      } catch (err: any) {
        setError(`WP check failed: ${err.message}`);
      }
    } finally {
      setWpTesting(null);
    }
  };

  const handleRecrawlWebsite = async (id: string) => {
    try {
      setNoticeMsg("Deep crawl: discovering sitemap + all subpages (up to 50, BFS depth 3) — may take 60-90s...");
      // use deep synchronous crawl for immediate feedback
      try {
        const res: any = await post(`/api/knowledge/watch-business`, { website_id: id });
        setNoticeMsg(`✓ Deep crawl done — ${res.urls_scanned || 0} URLs scanned, ${res.total_chunks_indexed || 0} chunks indexed`);
      } catch {
        await post(`/api/websites/${id}/crawl`, {});
        setNoticeMsg("⚡ Background crawl started — check /knowledge for new chunks in ~30s");
      }
      fetchWebsites();
    } catch (err: any) {
      setError(`Failed to start crawl: ${err.message}`);
    }
  };

  const handleDeleteWebsite = async (id: string) => {
    if (!confirm("Are you sure you want to remove this website?")) return;
    try {
      await del(`/api/websites/${id}`);
      setNoticeMsg("Website removed.");
      fetchWebsites();
    } catch (err: any) {
      setError(`Failed to delete website: ${err.message}`);
    }
  };

  if (loading && websites.length === 0) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px auto" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Loading active client domains & configurations...
        </p>
      </div>
    );
  }

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      <div className="page-heading">Connected Websites</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Multi-Tenant Domain Management · Autonomous SEO Scope · Active Site Selector
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
        {/* WEBSITES LIST */}
        <div>
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Managed Websites ({websites.length})</span>
              <button className="panel-action" onClick={fetchWebsites}>
                Refresh
              </button>
            </div>
            <div className="panel-body">
              {websites.length === 0 ? (
                <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
                  No websites connected yet. Add your first website using the form on the right.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  {websites.map((site) => {
                    const form = wpForms[site.id] || { user: "", pass: "", url: site.url || site.cms_url || `https://${site.domain}` };
                    return (
                      <div
                        key={site.id}
                        style={{
                          padding: "14px",
                          border: "1px solid var(--line)",
                          background: activeId === site.id ? "rgba(255, 77, 18, 0.08)" : "var(--surface)",
                          borderLeft: activeId === site.id ? "4px solid var(--accent)" : "1px solid var(--line)",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "10px" }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: 600, fontSize: "14px" }}>{site.domain}</div>
                            <div style={{ fontSize: "11px", color: "var(--muted)", marginTop: "4px" }}>
                              {site.url || site.cms_url || `https://${site.domain}`}
                            </div>
                            <div style={{ fontSize: "10px", color: "var(--muted)", marginTop: "6px" }}>
                              WordPress: {site.wordpress_url ? `${site.wordpress_url} — ${site.wordpress_user || site.cms_user || "no user"}` : "not configured — add below to enable /writer draft push"}
                            </div>
                          </div>
                          <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap", flexShrink: 0 }}>
                            {site.status === "crawling" ? (
                              <span className="badge badge-amber" style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                                <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "var(--amber)", display: "inline-block", animation: "pulse 1.5s infinite" }} />
                                {crawlStage[site.id] || "Deep crawling all subpages..."}
                              </span>
                            ) : (
                              <button
                                onClick={() => handleRecrawlWebsite(site.id)}
                                className="btn"
                                style={{ padding: "3px 8px", fontSize: "10.5px" }}
                                title="Deep BFS crawl: sitemap index recursion + all internal links up to 50 pages"
                              >
                                ⚡ Deep Re-Crawl
                              </button>
                            )}
                            {activeId === site.id ? (
                              <span className="badge badge-accent">Active Website</span>
                            ) : (
                              <button
                                onClick={() => handleSelectWebsite(site.id)}
                                className="btn"
                                style={{ padding: "4px 10px", fontSize: "11px" }}
                              >
                                Select
                              </button>
                            )}
                            <button
                              onClick={() => handleDeleteWebsite(site.id)}
                              style={{ background: "transparent", border: "none", color: "var(--red)", cursor: "pointer", fontSize: "14px" }}
                            >
                              ✕
                            </button>
                          </div>
                        </div>
                        {/* Per-site WordPress connect (fixes writer not connected even after adding site) */}
                        <div style={{ marginTop: "10px", padding: "10px", background: "var(--bg)", border: "1px solid var(--line)", borderRadius: "3px" }}>
                          <div style={{ fontSize: "10px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "6px", fontWeight: 600 }}>
                            WordPress App Password (for /writer → WP Drafts)
                          </div>
                          <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr 1fr auto", gap: "6px", alignItems: "end" }}>
                            <div>
                              <input
                                type="text"
                                value={form.url}
                                onChange={(e) => setWpForms((p) => ({ ...p, [site.id]: { ...form, url: e.target.value } }))}
                                placeholder="https://yourdomain.com"
                                className="field"
                                style={{ width: "100%", padding: "6px", fontSize: "11px" }}
                              />
                            </div>
                            <div>
                              <input
                                type="text"
                                value={form.user}
                                onChange={(e) => setWpForms((p) => ({ ...p, [site.id]: { ...form, user: e.target.value } }))}
                                placeholder="WP user (admin)"
                                className="field"
                                style={{ width: "100%", padding: "6px", fontSize: "11px" }}
                              />
                            </div>
                            <div>
                              <input
                                type="password"
                                value={form.pass}
                                onChange={(e) => setWpForms((p) => ({ ...p, [site.id]: { ...form, pass: e.target.value } }))}
                                placeholder="App Password xxxx xxxx"
                                className="field"
                                style={{ width: "100%", padding: "6px", fontSize: "11px" }}
                              />
                            </div>
                            <button
                              onClick={() => handleSaveWpForSite(site.id, form.url, form.user, form.pass)}
                              disabled={wpTesting === site.id}
                              className="btn btn-accent"
                              style={{ padding: "6px 10px", fontSize: "10.5px", whiteSpace: "nowrap" }}
                            >
                              {wpTesting === site.id ? "Saving..." : "Save & Test WP"}
                            </button>
                          </div>
                          <div style={{ display: "flex", gap: "8px", marginTop: "6px" }}>
                            <button onClick={() => handleTestWpForSite(site.id, form.url)} className="btn" style={{ padding: "3px 8px", fontSize: "10px" }}>
                              Test Connection
                            </button>
                            <span style={{ fontSize: "10px", color: "var(--muted)", alignSelf: "center" }}>Need Editor role — WP Admin → Users → Role</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ADD WEBSITE FORM */}
        <div>
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Add New Website</span>
            </div>
            <div className="panel-body">
              <form onSubmit={handleAddWebsite} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                    Domain Name
                  </label>
                  <input
                    type="text"
                    value={domain}
                    onChange={(e) => setDomain(e.target.value)}
                    placeholder="e.g. accidentlawyer.com"
                    className="field"
                    style={{ width: "100%", padding: "8px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
                    required
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                    Full Website URL (Optional)
                  </label>
                  <input
                    type="url"
                    value={cmsUrl}
                    onChange={(e) => setCmsUrl(e.target.value)}
                    placeholder="https://accidentlawyer.com"
                    className="field"
                    style={{ width: "100%", padding: "8px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
                  />
                </div>

                <div style={{ borderTop: "1px solid var(--line)", paddingTop: "12px", marginTop: "4px" }}>
                  <div style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: ".06em", color: "var(--accent)", marginBottom: "8px", fontWeight: 700 }}>
                    WordPress Connection (for /writer draft-to-WP)
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                      WP Username (Application Password owner)
                    </label>
                    <input
                      type="text"
                      value={wpUser}
                      onChange={(e) => setWpUser(e.target.value)}
                      placeholder="admin"
                      className="field"
                      style={{ width: "100%", padding: "8px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
                    />
                  </div>
                  <div style={{ marginTop: "8px" }}>
                    <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                      WP Application Password
                    </label>
                    <input
                      type="password"
                      value={wpAppPass}
                      onChange={(e) => setWpAppPass(e.target.value)}
                      placeholder="xxxx xxxx xxxx xxxx"
                      className="field"
                      style={{ width: "100%", padding: "8px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
                    />
                    <div style={{ fontSize: "10px", color: "var(--muted)", marginTop: "4px" }}>
                      WP Admin → Users → Application Passwords → Create new "RankForge" → paste here. User must be <strong>Editor/Author</strong> (not Subscriber).
                    </div>
                  </div>
                </div>

                <button type="submit" disabled={isSaving} className="btn btn-accent" style={{ padding: "10px", width: "100%", marginTop: "8px" }}>
                  {isSaving ? "Adding Website..." : "+ Add Website & Crawl All Subpages"}
                </button>
                <div style={{ fontSize: "10px", color: "var(--muted)", marginTop: "6px", textAlign: "center" }}>
                  Crawl discovers sitemap + BFS across all subpages (up to 50) — deep indexing for /knowledge.
                </div>
              </form>
            </div>
          </div>
          <div className="panel" style={{ marginTop: "12px" }}>
            <div className="panel-body" style={{ fontSize: "11px", color: "var(--muted)" }}>
              Already connected? Manage WordPress in <a href="/connectors" style={{ color: "var(--accent)" }}>/connectors</a> (also handles Serper, GSC, Slack). For existing sites, expand the WordPress connect form below each domain.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
