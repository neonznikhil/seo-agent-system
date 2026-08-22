"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId, getWebsiteId } from "@/lib/website";

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
  const [wpPass, setWpPass] = useState("");
  const [wpStatus, setWpStatus] = useState("");
  const [wpConnecting, setWpConnecting] = useState(false);
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

  const connectWordPress = async () => {
    if (!wpUrl || !wpUser || !wpPass) {
      alert("Fill all 3 WordPress fields first");
      return;
    }
    setWpConnecting(true);
    setWpStatus("");
    try {
      const activeWid = getWebsiteId() || websiteId;
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/wordpress/${activeWid}/connect`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            wordpress_url: wpUrl,
            wordpress_user: wpUser,
            wordpress_password: wpPass,
          }),
        }
      );
      const data = await res.json();
      if (data.success) {
        setWpStatus(`✅ ${data.message}`);
        setWpConnected(true);
        loadSettingsAndDiagnostics();
      } else {
        setWpStatus(`❌ ${data.message}`);
        setWpConnected(false);
      }
    } catch (err: any) {
      setWpStatus(`❌ Error: ${err.message}`);
      setWpConnected(false);
    } finally {
      setWpConnecting(false);
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
          <div style={{ border: "1px solid #333", padding: "1.5rem", marginTop: "1rem", background: "var(--panel)" }}>
            <h3>WordPress Integration</h3>
            <p style={{ color: "#888", fontSize: "0.85rem" }}>
              Connect your WordPress site to auto-publish approved content
            </p>

            <div style={{ marginTop: "1rem" }}>
              <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "#aaa", marginBottom: "4px" }}>
                WordPress URL
              </label>
              <input
                type="text"
                placeholder="https://yoursite.com"
                value={wpUrl}
                onChange={(e) => setWpUrl(e.target.value)}
                style={{ display: "block", width: "100%", padding: "8px", margin: "4px 0 12px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
              />

              <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "#aaa", marginBottom: "4px" }}>
                WordPress Username
              </label>
              <input
                type="text"
                placeholder="your-username"
                value={wpUser}
                onChange={(e) => setWpUser(e.target.value)}
                style={{ display: "block", width: "100%", padding: "8px", margin: "4px 0 12px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
              />

              <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "#aaa", marginBottom: "4px" }}>
                Application Password
              </label>
              <input
                type="password"
                placeholder="xxxx xxxx xxxx xxxx xxxx xxxx"
                value={wpPass}
                onChange={(e) => setWpPass(e.target.value)}
                style={{ display: "block", width: "100%", padding: "8px", margin: "4px 0 12px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
              />

              <p style={{ color: "#888", fontSize: "0.75rem", marginBottom: "12px" }}>
                Get App Password: WordPress → Users → Profile → scroll down → Application Passwords
              </p>

              <button
                onClick={connectWordPress}
                disabled={wpConnecting}
                style={{
                  padding: "10px 20px",
                  background: "#f60",
                  color: "#fff",
                  border: "none",
                  cursor: "pointer",
                  fontWeight: 600,
                }}
              >
                {wpConnecting ? "Testing Connection..." : "Connect WordPress"}
              </button>

              {wpStatus && (
                <p style={{ marginTop: "12px", fontSize: "0.9rem" }}>{wpStatus}</p>
              )}
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
