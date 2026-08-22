"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface HealthData {
  status: string;
  checks?: Record<string, string>;
  degraded_reasons?: string[];
}

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [noticeMsg, setNoticeMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [websiteId, setWebsiteId] = useState<string>("");

  // WordPress credentials state
  const [wpUrl, setWpUrl] = useState("");
  const [wpUser, setWpUser] = useState("");
  const [wpPassword, setWpPassword] = useState("");
  const [isTestingWp, setIsTestingWp] = useState(false);
  const [isSavingWp, setIsSavingWp] = useState(false);
  const [wpConnected, setWpConnected] = useState<boolean | null>(null);

  const loadSettingsAndDiagnostics = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);

    try {
      setLoading(true);
      setError(null);

      const [healthRes, statsRes, siteRes] = await Promise.allSettled([
        get("/health"),
        wid ? get(`/api/stats?website_id=${wid}`) : Promise.resolve(null),
        wid ? get(`/api/websites`) : Promise.resolve([]),
      ]);

      if (healthRes.status === "fulfilled" && healthRes.value) {
        setHealth(healthRes.value);
      }

      if (statsRes.status === "fulfilled" && statsRes.value) {
        setStats(statsRes.value);
      }

      if (siteRes.status === "fulfilled" && Array.isArray(siteRes.value) && wid) {
        const site = siteRes.value.find((s: any) => s.id === wid);
        if (site) {
          setWpUrl(site.cms_url || site.wordpress_url || "");
          setWpUser(site.cms_user || site.wordpress_user || "");
        }
      }
    } catch (err: any) {
      console.warn("Diagnostics error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSettingsAndDiagnostics();
    const handleChanged = () => loadSettingsAndDiagnostics();
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [loadSettingsAndDiagnostics]);

  const handleTestWordPress = async () => {
    if (!wpUrl.trim() || !wpUser.trim() || !wpPassword.trim()) {
      setError("Please fill in WordPress URL, Username, and Application Password to test.");
      return;
    }

    try {
      setIsTestingWp(true);
      setError(null);
      setNoticeMsg(null);

      const payload = {
        url: wpUrl.trim(),
        username: wpUser.trim(),
        password: wpPassword.trim(),
      };

      const res = await post(`/api/wordpress/${websiteId || "default"}/test`, payload);
      if (res && res.connected) {
        setWpConnected(true);
        setNoticeMsg("✅ WordPress connection test successful! Ready to create drafts.");
      } else {
        setWpConnected(false);
        setError(res?.message || "WordPress connection failed. Check credentials and Application Password.");
      }
    } catch (err: any) {
      setWpConnected(false);
      setError(`WordPress test failed: ${err.message}`);
    } finally {
      setIsTestingWp(false);
    }
  };

  const handleSaveWordPress = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!websiteId) {
      setError("Please select or add a website first.");
      return;
    }

    try {
      setIsSavingWp(true);
      setError(null);

      await post(`/api/wordpress/${websiteId}/credentials`, {
        wordpress_url: wpUrl.trim(),
        wordpress_user: wpUser.trim(),
        wordpress_password: wpPassword.trim(),
      });

      setNoticeMsg("✓ WordPress credentials saved to database!");
      loadSettingsAndDiagnostics();
    } catch (err: any) {
      setError(`Failed to save credentials: ${err.message}`);
    } finally {
      setIsSavingWp(false);
    }
  };

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      <div className="page-heading">Settings & Service Integrations</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        WordPress Application Passwords · Live Health Diagnostics · Zero Mock Data
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
        {/* WORDPRESS INTEGRATION FORM */}
        <div>
          <div className="panel">
            <div className="panel-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="panel-label">WordPress Integration</span>
              {wpConnected === true && <span className="badge badge-green">Connected ✅</span>}
              {wpConnected === false && <span className="badge badge-red">Disconnected ✕</span>}
            </div>
            <div className="panel-body">
              <form onSubmit={handleSaveWordPress} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                    WordPress Site URL
                  </label>
                  <input
                    type="url"
                    value={wpUrl}
                    onChange={(e) => setWpUrl(e.target.value)}
                    placeholder="https://example.com"
                    className="field"
                    style={{ width: "100%", padding: "8px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
                    required
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                    WordPress Username / Email
                  </label>
                  <input
                    type="text"
                    value={wpUser}
                    onChange={(e) => setWpUser(e.target.value)}
                    placeholder="admin"
                    className="field"
                    style={{ width: "100%", padding: "8px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
                    required
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                    Application Password
                  </label>
                  <input
                    type="password"
                    value={wpPassword}
                    onChange={(e) => setWpPassword(e.target.value)}
                    placeholder="xxxx xxxx xxxx xxxx"
                    className="field"
                    style={{ width: "100%", padding: "8px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
                    required
                  />
                </div>

                <div style={{ display: "flex", gap: "10px", marginTop: "8px" }}>
                  <button
                    type="button"
                    onClick={handleTestWordPress}
                    disabled={isTestingWp}
                    className="btn"
                    style={{ padding: "8px 16px", fontSize: "11px" }}
                  >
                    {isTestingWp ? "Testing..." : "🔍 Test Connection"}
                  </button>
                  <button
                    type="submit"
                    disabled={isSavingWp || !websiteId}
                    className="btn btn-accent"
                    style={{ padding: "8px 16px", fontSize: "11px" }}
                  >
                    {isSavingWp ? "Saving..." : "💾 Save Credentials"}
                  </button>
                </div>
              </form>
            </div>
          </div>

          {/* POSTS STATUS BREAKDOWN */}
          <div className="panel" style={{ marginTop: "20px" }}>
            <div className="panel-head">
              <span className="panel-label">WordPress Posts Status Breakdown</span>
            </div>
            <div className="panel-body">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                <div style={{ padding: "12px", border: "1px solid var(--line)", background: "var(--surface)" }}>
                  <div style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>Draft Posts</div>
                  <div style={{ fontSize: "20px", fontWeight: "bold", color: "var(--accent)", marginTop: "4px" }}>
                    {stats?.pending_articles ?? 0}
                  </div>
                  <div style={{ fontSize: "10px", color: "var(--muted)", marginTop: "2px" }}>Awaiting human approval</div>
                </div>
                <div style={{ padding: "12px", border: "1px solid var(--line)", background: "var(--surface)" }}>
                  <div style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>Published Live</div>
                  <div style={{ fontSize: "20px", fontWeight: "bold", color: "var(--green)", marginTop: "4px" }}>
                    {Math.max(0, (stats?.total_articles ?? 0) - (stats?.pending_articles ?? 0))}
                  </div>
                  <div style={{ fontSize: "10px", color: "var(--muted)", marginTop: "2px" }}>Live on WordPress</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* SYSTEM HEALTH DIAGNOSTICS */}
        <div>
          <div className="panel">
            <div className="panel-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="panel-label">Backend Diagnostics</span>
              <button className="panel-action" onClick={loadSettingsAndDiagnostics}>
                Re-check
              </button>
            </div>
            <div className="panel-body">
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 12px", border: "1px solid var(--line)" }}>
                  <span style={{ fontSize: "12px" }}>NVIDIA NIM (Llama-3.1-70B)</span>
                  <span className={`badge ${health?.checks?.nim === "configured" ? "badge-green" : "badge-red"}`}>
                    {health?.checks?.nim || "Checking"}
                  </span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 12px", border: "1px solid var(--line)" }}>
                  <span style={{ fontSize: "12px" }}>Supabase Database</span>
                  <span className={`badge ${health?.checks?.supabase === "ok" ? "badge-green" : "badge-red"}`}>
                    {health?.checks?.supabase || "Checking"}
                  </span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 12px", border: "1px solid var(--line)" }}>
                  <span style={{ fontSize: "12px" }}>Overall API Health</span>
                  <span className={`badge ${health?.status === "ok" ? "badge-green" : "badge-amber"}`}>
                    {health?.status || "Checking"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
