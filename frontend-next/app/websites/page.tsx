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
  status?: string;
  created_at?: string;
}

export default function WebsitesPage() {
  const [websites, setWebsites] = useState<Website[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [noticeMsg, setNoticeMsg] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string>("");

  // Form state
  const [domain, setDomain] = useState("");
  const [cmsUrl, setCmsUrl] = useState("");
  const [isSaving, setIsSaving] = useState(false);

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
      if (current) {
        setActiveId(current);
      } else if (list.length > 0) {
        setActiveId(list[0].id);
        setCurrentWebsiteId(list[0].id);
      }
    } catch (err: any) {
      console.warn("Failed to load websites:", err);
      setError(err.message || "Failed to load websites");
      setWebsites([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWebsites();
  }, [fetchWebsites]);

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
      const res = await post("/api/websites", {
        domain: cleanDomain,
        url: cmsUrl.trim() || `https://${cleanDomain}`,
        cms_url: cmsUrl.trim() || `https://${cleanDomain}`,
        status: "active",
      });

      const newId = res.id || (res.data && res.data[0]?.id);
      if (newId) {
        setActiveId(newId);
        setCurrentWebsiteId(newId);
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("website-changed", { detail: newId }));
        }
      }

      setDomain("");
      setCmsUrl("");
      setNoticeMsg("✓ Website successfully added and activated!");
      fetchWebsites();
    } catch (err: any) {
      setError(`Failed to create website: ${err.message}`);
    } finally {
      setIsSaving(false);
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
                  {websites.map((site) => (
                    <div
                      key={site.id}
                      style={{
                        padding: "14px",
                        border: "1px solid var(--line)",
                        background: activeId === site.id ? "rgba(255, 77, 18, 0.08)" : "var(--surface)",
                        borderLeft: activeId === site.id ? "4px solid var(--accent)" : "1px solid var(--line)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: "14px" }}>{site.domain}</div>
                          <div style={{ fontSize: "11px", color: "var(--muted)", marginTop: "4px" }}>
                            {site.url || site.cms_url || `https://${site.domain}`}
                          </div>
                        </div>
                        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
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
                    </div>
                  ))}
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

                <button type="submit" disabled={isSaving} className="btn btn-accent" style={{ padding: "10px", width: "100%", marginTop: "8px" }}>
                  {isSaving ? "Adding Website..." : "+ Add Website & Crawl"}
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
