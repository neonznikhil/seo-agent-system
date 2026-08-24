"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

const MASK = "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022";

interface ConnectorStatus {
  wordpress?: { is_configured?: boolean };
  serper?: { is_configured?: boolean; fallback_active?: boolean };
  nvidia?: { is_configured?: boolean; available?: boolean };
  slack?: { connected?: boolean; workspace_name?: string | null; oauth_ready?: boolean };
  gsc?: { is_configured?: boolean };
  ga4?: { is_configured?: boolean };
}

function CredentialField({
  value,
  onChange,
  saved,
  placeholder,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  saved: boolean;
  placeholder: string;
  disabled?: boolean;
}) {
  return (
    <input
      type="password"
      className="field"
      autoComplete="new-password"
      autoCorrect="off"
      spellCheck={false}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={saved ? MASK : placeholder}
      disabled={disabled}
    />
  );
}

export default function ConnectorsPage() {
  const [websiteId, setWebsiteId] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  // WordPress credentials form
  const [wpUrl, setWpUrl] = useState("");
  const [wpUser, setWpUser] = useState("");
  const [wpPass, setWpPass] = useState("");
  const [wpSaved, setWpSaved] = useState(false);
  const [wpEditing, setWpEditing] = useState(false);
  const [isTestingWp, setIsTestingWp] = useState(false);

  // Serper API Key
  const [serperKey, setSerperKey] = useState("");
  const [serperSaved, setSerperSaved] = useState(false);
  const [serperEditing, setSerperEditing] = useState(false);
  const [isTestingSerper, setIsTestingSerper] = useState(false);

  // Slack
  const [slackConnected, setSlackConnected] = useState(false);
  const [slackWorkspace, setSlackWorkspace] = useState<string | null>(null);

  // GA4 / GSC
  const [ga4Result, setGa4Result] = useState<string | null>(null);
  const [gscProps, setGscProps] = useState<string[]>([]);
  const [gscSelected, setGscSelected] = useState("");

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  const loadConnectorStatuses = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);
    try {
      setLoading(true);
      const qs = wid ? `?website_id=${wid}` : "";
      const res: ConnectorStatus = await get(`/api/connectors/status${qs}`);
      if (!res) return;

      if (res.wordpress?.is_configured) {
        setWpSaved(true);
        setWpEditing(false);
        setWpPass(""); // never prefill the stored credential
      }
      if (res.serper?.is_configured) {
        setSerperSaved(true);
        setSerperEditing(false);
        setSerperKey("");
      }
      if (res.slack?.connected) {
        setSlackConnected(true);
        setSlackWorkspace(res.slack.workspace_name || null);
      }
      if (wid && res.wordpress?.is_configured === undefined) {
        // Fallback to per-website endpoint for site URL/username display
        try {
          const detail = await get(`/api/websites/${wid}/connector-status`);
          if (detail?.wordpress?.is_configured) {
            setWpSaved(true);
            setWpUrl(detail.wordpress.site_url || "");
            setWpUser(detail.wordpress.username || "");
          }
          if (detail?.serper?.is_configured) setSerperSaved(true);
          if (detail?.slack?.connected) {
            setSlackConnected(true);
            setSlackWorkspace(detail.slack.workspace_name || null);
          }
          if (detail?.gsc?.property) setGscSelected(detail.gsc.property);
        } catch {}
      }
    } catch {
      // Status endpoint unavailable — leave defaults
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConnectorStatuses();
  }, [loadConnectorStatuses]);

  // 1-Click Slack OAuth (popup + postMessage)
  const handleSlackOAuth = () => {
    const wid = getCurrentWebsiteId() || websiteId || "";
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const base = apiBase.replace(/\/+$/, "").replace(/\/api$/, "");
    const authUrl = `${base}/api/connectors/slack/oauth/start?website_id=${encodeURIComponent(wid)}`;
    const popup = window.open(authUrl, "SlackOAuth", "width=600,height=700");
    showToast("Opening Slack authorization window...");

    const onMessage = (event: MessageEvent) => {
      if (event.data && event.data.success === true && event.data.integration === "slack") {
        clearInterval(checkInterval);
        popup?.close();
        setSlackConnected(true);
        setSlackWorkspace(event.data.workspace || null);
        showToast(`✓ Slack connected — ${event.data.workspace || "workspace linked"}!`);
        loadConnectorStatuses();
      }
    };
    window.addEventListener("message", onMessage);

    const checkInterval = setInterval(() => {
      if (popup && popup.closed) {
        clearInterval(checkInterval);
        window.removeEventListener("message", onMessage);
        loadConnectorStatuses();
      }
    }, 800);
  };

  const handleDisconnectSlack = async () => {
    try {
      await post("/api/connectors/slack/disconnect", { website_id: getCurrentWebsiteId() });
      setSlackConnected(false);
      setSlackWorkspace(null);
      showToast("Slack disconnected.");
    } catch (e: any) {
      showToast(`Disconnect failed: ${e.message}`);
    }
  };

  // Save & Verify WordPress
  const handleTestWordPress = async () => {
    if (!wpPass.trim()) {
      showToast("Enter an Application Password first (generate one in WP Admin → Users → Profile).");
      return;
    }
    try {
      setIsTestingWp(true);
      showToast("Verifying WordPress REST connection...");
      const res = await post("/api/connectors/save-wordpress", {
        site_url: wpUrl,
        wp_username: wpUser,
        wp_app_password: wpPass,
        website_id: getCurrentWebsiteId() || websiteId,
      });
      const newWid = res?.website_id;
      if (newWid) {
        setCurrentWebsiteId(newWid);
        setWebsiteId(newWid);
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("website-changed", { detail: newWid }));
        }
      }
      setWpPass("");
      setWpSaved(true);
      setWpEditing(false);
      showToast("✓ WordPress connected — credentials encrypted & saved!");
      loadConnectorStatuses();
    } catch (err: any) {
      showToast(`WordPress error: ${err.message || "Verification failed"}`);
    } finally {
      setIsTestingWp(false);
    }
  };

  const startWpEdit = () => {
    setWpEditing(true);
    setWpSaved(false);
    setWpPass("");
    showToast("Enter a new Application Password to reconnect.");
  };

  // Save Serper key
  const handleSaveSerper = async () => {
    if (!serperKey.trim()) {
      showToast("Please enter your Serper.dev API key");
      return;
    }
    try {
      setIsTestingSerper(true);
      showToast("Validating Serper.dev API key...");
      const res = await post("/api/connectors/serper/save-key", { api_key: serperKey.trim() });
      if (res?.success) {
        setSerperKey("");
        setSerperSaved(true);
        setSerperEditing(false);
        const credits = res.status?.credits_remaining;
        showToast(credits ? `✓ Serper verified — ~${credits} credits remaining!` : "✓ Serper.dev API connected & verified!");
        loadConnectorStatuses();
      } else {
        showToast(res?.error || "Invalid API key — check it at serper.dev");
      }
    } catch (err: any) {
      showToast(`Serper error: ${err.message || "Invalid API key"}`);
    } finally {
      setIsTestingSerper(false);
    }
  };

  const startSerperEdit = () => {
    setSerperEditing(true);
    setSerperSaved(false);
    setSerperKey("");
  };

  // Test GA4 stream
  const handleTestGa4 = async () => {
    try {
      setGa4Result(null);
      const res = await post("/api/connectors/ga4/test", { website_id: getCurrentWebsiteId() });
      if (res?.connected) {
        setGa4Result(`✓ GA4 Connected — ${res.sessions_last_7_days} sessions in last 7 days.`);
      } else {
        setGa4Result(`GA4 not available: ${res?.error || "credentials missing in Connectors."}`);
      }
    } catch (e: any) {
      setGa4Result(`GA4 test failed: ${e.message}`);
    }
  };

  // Sync GSC properties
  const handleSyncGsc = async () => {
    try {
      showToast("Fetching verified Search Console properties...");
      const res = await post("/api/connectors/gsc/properties", { website_id: getCurrentWebsiteId() });
      const props: string[] = res?.properties || [];
      if (props.length > 0) {
        setGscProps(props);
        showToast(`✓ Found ${props.length} verified GSC properties.`);
      } else {
        showToast(res?.error || "No verified GSC properties found for these credentials.");
      }
    } catch (e: any) {
      showToast(`GSC sync failed: ${e.message}`);
    }
  };

  const saveGscProperty = async (prop: string) => {
    setGscSelected(prop);
    try {
      await post("/api/connectors/gsc/select-property", {
        website_id: getCurrentWebsiteId(),
        property: prop,
      });
      showToast(`GSC property saved: ${prop}`);
    } catch {}
  };

  return (
    <div className="page-container active">
      {toastMsg && (
        <div
          style={{
            position: "fixed",
            bottom: "24px",
            left: "50%",
            transform: "translateX(-50%)",
            background: "var(--ink)",
            color: "var(--bg)",
            padding: "10px 22px",
            fontSize: "10.5px",
            textTransform: "uppercase",
            letterSpacing: ".07em",
            zIndex: 9999,
            fontFamily: "'IBM Plex Mono', monospace",
            border: "1px solid var(--accent)",
            boxShadow: "0 4px 24px rgba(0,0,0,.4)",
          }}
        >
          {toastMsg}
        </div>
      )}

      {/* PAGE HEADER */}
      <div className="page-heading">Connectors & Integrations</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        One-Click OAuth · Direct CMS Publishing · Live Search Telemetry
      </div>

      {/* 1-CLICK OAUTH & INTEGRATION CARDS */}
      <div className="grid-3" style={{ marginBottom: "20px" }}>
        {/* SLACK */}
        <div className="panel" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div>
            <div className="panel-head">
              <span className="panel-label">💬 Slack Intelligence</span>
              <span className={`badge ${slackConnected ? "badge-green" : "badge-amber"}`}>
                {slackConnected ? `Connected${slackWorkspace ? ` — ${slackWorkspace}` : ""}` : "Not Connected"}
              </span>
            </div>
            <div className="panel-body">
              <p style={{ fontSize: "11px", color: "var(--muted)", lineHeight: "1.5", marginBottom: "14px" }}>
                Receive daily morning briefs, evening summaries, backlink discoveries, and crisis alerts automatically inside #rankforge-daily, #rankforge-backlinks, #rankforge-weekly and #rankforge-alerts.
              </p>
            </div>
          </div>
          <div style={{ padding: "0 14px 14px", display: "flex", gap: "8px" }}>
            {!slackConnected ? (
              <button
                type="button"
                className="btn btn-accent"
                style={{ width: "100%", padding: "9px" }}
                onClick={handleSlackOAuth}
              >
                ⚡ Connect Slack (1-Click OAuth)
              </button>
            ) : (
              <button
                type="button"
                className="btn"
                style={{ width: "100%", padding: "9px" }}
                onClick={handleDisconnectSlack}
              >
                Disconnect
              </button>
            )}
          </div>
        </div>

        {/* GOOGLE SEARCH CONSOLE */}
        <div className="panel" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div>
            <div className="panel-head">
              <span className="panel-label">🔴 Google Search Console</span>
              <span className={`badge ${gscSelected ? "badge-green" : "badge-amber"}`}>
                {gscSelected ? "Connected" : "Awaiting Sync"}
              </span>
            </div>
            <div className="panel-body">
              <p style={{ fontSize: "11px", color: "var(--muted)", lineHeight: "1.5", marginBottom: "10px" }}>
                Pulls live keyword impressions, click-through rates, average search positions, and index status directly into the autonomous keyword engine.
              </p>
              {gscProps.length > 0 && (
                <select
                  className="field"
                  value={gscSelected}
                  onChange={(e) => saveGscProperty(e.target.value)}
                  style={{ width: "100%", marginBottom: "8px" }}
                >
                  <option value="">Select property…</option>
                  {gscProps.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              )}
            </div>
          </div>
          <div style={{ padding: "0 14px 14px" }}>
            <button
              type="button"
              className="btn btn-primary"
              style={{ width: "100%", padding: "9px" }}
              onClick={handleSyncGsc}
            >
              Sync GSC Properties
            </button>
          </div>
        </div>

        {/* GOOGLE ANALYTICS 4 */}
        <div className="panel" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div>
            <div className="panel-head">
              <span className="panel-label">📊 Google Analytics 4</span>
              <span className={`badge ${ga4Result?.startsWith("✓") ? "badge-green" : "badge-amber"}`}>
                {ga4Result?.startsWith("✓") ? "Connected" : "Ready"}
              </span>
            </div>
            <div className="panel-body">
              <p style={{ fontSize: "11px", color: "var(--muted)", lineHeight: "1.5", marginBottom: "10px" }}>
                Tracks organic visitor conversions, engagement time, scroll depth, and goal completion to teach the Brain what content converts.
              </p>
              {ga4Result && (
                <p style={{ fontSize: "10.5px", color: ga4Result.startsWith("✓") ? "var(--green)" : "var(--muted)" }}>
                  {ga4Result}
                </p>
              )}
            </div>
          </div>
          <div style={{ padding: "0 14px 14px" }}>
            <button
              type="button"
              className="btn"
              style={{ width: "100%", padding: "9px" }}
              onClick={handleTestGa4}
            >
              Test GA4 Stream
            </button>
          </div>
        </div>
      </div>

      {/* DETAILED WORDPRESS & SERPER CONFIGURATION */}
      <div className="grid-2">
        {/* WORDPRESS MANAGER */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">🔷 WordPress REST API Direct Connection</span>
            <span className={`badge ${wpSaved ? "badge-green" : "badge-amber"}`}>{wpSaved ? "Connected" : "Not Configured"}</span>
          </div>
          <div className="panel-body">
            <div style={{ marginBottom: "10px" }}>
              <label style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", display: "block", marginBottom: "4px" }}>
                WordPress Site URL
              </label>
              <input
                className="field"
                value={wpUrl}
                onChange={(e) => setWpUrl(e.target.value)}
                placeholder="https://your-site.com"
                disabled={wpSaved && !wpEditing}
              />
            </div>
            <div style={{ marginBottom: "10px" }}>
              <label style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", display: "block", marginBottom: "4px" }}>
                Auth Username / Email
              </label>
              <input
                className="field"
                value={wpUser}
                onChange={(e) => setWpUser(e.target.value)}
                placeholder="wordpress_username"
                disabled={wpSaved && !wpEditing}
              />
            </div>
            <div style={{ marginBottom: "6px" }}>
              <label style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", display: "block", marginBottom: "4px" }}>
                Application Password (encrypted with Fernet at rest)
              </label>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <CredentialField
                  value={wpPass}
                  onChange={setWpPass}
                  saved={wpSaved && !wpEditing}
                  placeholder="xxxx xxxx xxxx xxxx xxxx xxxx"
                  disabled={wpSaved && !wpEditing}
                />
                {wpSaved && !wpEditing && (
                  <span className="badge badge-green" style={{ whiteSpace: "nowrap" }}>Saved ✓</span>
                )}
              </div>
              <span style={{ fontSize: "8.5px", color: "var(--muted)", marginTop: "3px", display: "block" }}>
                Generate in WP Admin → Users → Edit Profile → Application Passwords. Stored encrypted — never displayed again.
              </span>
            </div>

            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              {(!wpSaved || wpEditing) ? (
                <button
                  type="button"
                  className="btn btn-accent"
                  disabled={isTestingWp}
                  onClick={handleTestWordPress}
                >
                  {isTestingWp ? "Verifying..." : "Save & Verify Connection"}
                </button>
              ) : (
                <button type="button" className="btn" onClick={startWpEdit}>
                  Reconnect / Update Credentials
                </button>
              )}
              <Link href="/wordpress" className="btn" style={{ textDecoration: "none", display: "inline-block" }}>
                View WP Posts
              </Link>
            </div>
          </div>
        </div>

        {/* SERPER & EXTERNAL INTELLIGENCE */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">⚡ Serper.dev & External Intelligence</span>
            <span className={`badge ${serperSaved ? "badge-green" : "badge-amber"}`}>
              {serperSaved ? "LIVE API" : "Fallback Mode"}
            </span>
          </div>
          <div className="panel-body">
            <div style={{ marginBottom: "12px" }}>
              <label style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", display: "block", marginBottom: "4px" }}>
                Serper.dev API Key (Google SERP Intelligence)
              </label>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <CredentialField
                  value={serperKey}
                  onChange={setSerperKey}
                  saved={serperSaved && !serperEditing}
                  placeholder="Enter your Serper.dev API key"
                  disabled={serperSaved && !serperEditing}
                />
                {serperSaved && !serperEditing && (
                  <span className="badge badge-green" style={{ whiteSpace: "nowrap" }}>Saved ✓</span>
                )}
              </div>
              <span style={{ fontSize: "8.5px", color: "var(--muted)", marginTop: "3px", display: "block" }}>
                Automatic fallback: Crawlee headless SERP scraper activates when no key is present.
              </span>
            </div>

            <div style={{ display: "flex", gap: "8px", marginBottom: "18px" }}>
              {(!serperSaved || serperEditing) ? (
                <button
                  type="button"
                  className="btn btn-accent"
                  disabled={isTestingSerper}
                  onClick={handleSaveSerper}
                >
                  {isTestingSerper ? "Validating..." : "Save Serper Key"}
                </button>
              ) : (
                <button type="button" className="btn" onClick={startSerperEdit}>
                  Update Key
                </button>
              )}
            </div>

            <div style={{ borderTop: "1px solid var(--border)", paddingTop: "14px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <span style={{ fontSize: "11px", fontWeight: 600 }}>NVIDIA NIM Microservice</span>
                <span className="badge badge-green">Llama-3.1-70B Live</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <span style={{ fontSize: "11px", fontWeight: 600 }}>Supabase pgvector (1024d)</span>
                <span className="badge badge-green">Connected</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "11px", fontWeight: 600 }}>Fernet Token Encryption</span>
                <span className="badge badge-green">Active</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* BOTTOM TICKER */}
      <div className="bticker">
        <span className="bticker-inner">
          <span className="bt-sq"></span>CONNECTORS & OAUTH <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SLACK 1-CLICK OAUTH LIVE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>WORDPRESS REST API ACTIVE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>CREDENTIALS ENCRYPTED AT REST &nbsp;&nbsp;&nbsp;&nbsp;
          <span className="bt-sq"></span>CONNECTORS & OAUTH <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SLACK 1-CLICK OAUTH LIVE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>WORDPRESS REST API ACTIVE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>CREDENTIALS ENCRYPTED AT REST
        </span>
      </div>
    </div>
  );
}
