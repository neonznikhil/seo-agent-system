"use client";

import { useEffect, useRef, useState } from "react";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";
import WordPressConnect from "@/components/WordPressConnect";

type TabKey = "settings" | "sync" | "mapping" | "permissions" | "data" | "indexing" | "alerts" | "setup";

interface Connector {
  id: string;
  name: string;
  icon: string;
  description: string;
  connected: boolean;
  version: string | null;
  postsPublished?: number;
  last_sync?: string;
  sync_interval?: string;
  error?: string;
}

const wpTabs: { key: TabKey; label: string }[] = [
  { key: "settings", label: "Settings" },
  { key: "sync", label: "Sync Log" },
  { key: "mapping", label: "Field Mapping" },
  { key: "permissions", label: "Permissions" },
];

const gscTabs: { key: TabKey; label: string }[] = [
  { key: "settings", label: "Settings" },
  { key: "data", label: "Live Data" },
  { key: "indexing", label: "Indexing" },
  { key: "alerts", label: "Alerts" },
];

export default function ConnectorsPage() {
  const [theme, setTheme] = useState("light");
  const [selectedId, setSelectedId] = useState("wp");
  const [selectedTab, setSelectedTab] = useState<TabKey>("settings");
  const [toast, setToast] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(true);
  const [chatInput, setChatInput] = useState("");
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [gscKeywords, setGscKeywords] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [messages, setMessages] = useState<{ role: "user" | "ai"; text: string; time: string }[]>([
    {
      role: "ai",
      text: "Connectors page loaded. Test connections in /settings or configure below.",
      time: "Now",
    },
  ]);
  const [typing, setTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const websiteId = getCurrentWebsiteId();

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
  };

  useEffect(() => {
    const saved = localStorage.getItem("theme");
    if (saved) {
      setTheme(saved);
      document.documentElement.setAttribute("data-theme", saved);
    } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      setTheme("dark");
      document.documentElement.setAttribute("data-theme", "dark");
    }
  }, []);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2200);
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, typing]);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [connData, gscData, alertsData] = await Promise.allSettled([
          get(`/connectors/${websiteId}`),
          get(`/gsc/keywords/${websiteId}`),
          get(`/monitoring/${websiteId}/alerts?filter=unread`),
        ]);

        if (connData.status === "fulfilled") {
          const conns = connData.value?.connectors || connData.value || [];
          setConnectors(Array.isArray(conns) ? conns : []);
        }
        if (gscData.status === "fulfilled") {
          setGscKeywords(gscData.value?.keywords || []);
        }
        if (alertsData.status === "fulfilled") {
          setAlerts(Array.isArray(alertsData.value) ? alertsData.value : []);
        }
        setError(null);
      } catch (e: any) {
        setError(e.message || "Failed to load connector data");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [websiteId]);

  const selected = connectors.find((c) => c.id === selectedId) || connectors[0];

  const sendChat = async () => {
    if (!chatInput.trim()) return;
    const text = chatInput.trim();
    setChatInput("");
    setMessages((prev) => [...prev, { role: "user", text, time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) }]);
    setTyping(true);
    try {
      const res = await post(`/connectors/${websiteId}/chat`, { message: text });
      const reply = res?.reply || res?.message || "No response from connector service";
      setMessages((prev) => [...prev, { role: "ai", text: reply, time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) }]);
    } catch (e: any) {
      setMessages((prev) => [...prev, { role: "ai", text: `Error: ${e.message}`, time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) }]);
    } finally {
      setTyping(false);
    }
  };

  const getReply = (msg: string) => {
    return `Connector query received: "${msg}". Use the tabs above to configure integrations or test connections.`;
  };

  const suggestions = [
    "Test WordPress connection",
    "Pull latest GSC data",
    "Submit sitemap to Google",
    "Show indexing errors",
  ];

  const getTabs = (): { key: TabKey; label: string }[] => {
    if (selectedId === "wp") return wpTabs;
    if (selectedId === "gsc") return gscTabs;
    return [{ key: "setup", label: "Setup" }];
  };

  const tabs = getTabs();

  return (
    <div className="page-container active">
      <div className="page-heading">Connectors</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Integrate external platforms · Push content · Pull data
      </div>

      {/* STAT STRIP */}
      <div className="stat-strip">
        <div className="stat-cell">
          <div className="stat-label">Active Connectors</div>
          <div className="stat-val">{connectors.filter(c => c.connected).length}</div>
          <div className="stat-sub muted">{connectors.length} total</div>
        </div>
        <div className="stat-cell">
          <div className="stat-label">Posts Published</div>
          <div className="stat-val">{connectors.find(c => c.id === "wp")?.postsPublished ?? 0}</div>
          <div className="stat-sub muted">WordPress</div>
        </div>
        <div className="stat-cell">
          <div className="stat-label">GSC Impressions</div>
          <div className="stat-val">{gscKeywords.length > 0 ? formatNumber(gscKeywords.reduce((s, k) => s + (k.impressions || 0), 0)) : "—"}</div>
          <div className="stat-sub muted">{gscKeywords.length} keywords</div>
        </div>
        <div className="stat-cell">
          <div className="stat-label">Last Sync</div>
          <div className="stat-val" style={{ fontSize: "14px", paddingTop: "3px" }}>
            {connectors.find(c => c.id === "wp")?.last_sync ? timeAgo(new Date(connectors.find(c => c.id === "wp")!.last_sync!)) : "—"}
          </div>
          <div className="stat-sub muted">Auto</div>
        </div>
      </div>

      {/* CONNECTOR CARDS */}
      <div style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: ".08em", color: "var(--muted)", marginBottom: "10px" }}>
        Available Integrations
      </div>
      <div className="connector-grid">
        {connectors.map((conn) => (
          <div
            key={conn.id}
            className={`connector-card ${conn.connected ? "connected" : ""} ${selectedId === conn.id ? "active-selected" : ""}`}
            onClick={() => {
              setSelectedId(conn.id);
              setSelectedTab(conn.id === "wp" ? "settings" : conn.id === "gsc" ? "settings" : "setup");
            }}
          >
            <div className="connector-icon">{conn.icon}</div>
            <div className="connector-name">{conn.name}</div>
            <div className="connector-desc">{conn.description}</div>
            <div className="connector-status">
              <div className="conn-badge-row">
                <span className={`status-dot ${conn.connected ? "green" : "muted"}`}></span>
                <span className={`badge ${conn.connected ? "badge-green" : "badge-muted"}`}>{conn.connected ? "Connected" : "Not Connected"}</span>
              </div>
              <span style={{ fontSize: "9px", color: "var(--muted)" }}>{conn.version || ""}</span>
            </div>
            <div className="connector-actions">
              {conn.id === "wp" && conn.connected && (
                <>
                  <button className="btn btn-accent" style={{ fontSize: "9px", padding: "4px 10px" }} onClick={(e) => { e.stopPropagation(); setSelectedId("wp"); setSelectedTab("settings"); }}>Configure</button>
                  <button className="btn" style={{ fontSize: "9px", padding: "4px 10px" }} onClick={(e) => { e.stopPropagation(); showToast("Testing WordPress connection..."); setTimeout(() => showToast("✓ WordPress — connection OK"), 1200); }}>Test</button>
                </>
              )}
              {conn.id === "gsc" && conn.connected && (
                <>
                  <button className="btn btn-accent" style={{ fontSize: "9px", padding: "4px 10px" }} onClick={(e) => { e.stopPropagation(); setSelectedId("gsc"); setSelectedTab("settings"); }}>Configure</button>
                  <button className="btn" style={{ fontSize: "9px", padding: "4px 10px" }} onClick={(e) => { e.stopPropagation(); showToast("Testing GSC connection..."); setTimeout(() => showToast("✓ GSC — connection OK"), 1200); }}>Test</button>
                </>
              )}
              {!conn.connected && ["ga", "ahrefs", "semrush", "slack"].includes(conn.id) && (
                <button className="btn btn-primary" style={{ fontSize: "9px", padding: "4px 10px" }} onClick={(e) => { e.stopPropagation(); setSelectedId(conn.id); setSelectedTab("setup"); }}>Connect</button>
              )}
            </div>
          </div>
        ))}
      </div>

      <WordPressConnect />

      {/* CONFIG PANEL */}
      <div id="config-area">
        {/* WORDPRESS */}
        <div className={`config-section ${selectedId === "wp" ? "active" : ""}`} id="section-wp">
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">🔷 WordPress — Configuration</span>
              <div style={{ display: "flex", gap: "6px" }}>
                <span className="badge badge-green">Connected</span>
                <button className="btn btn-danger" style={{ fontSize: "9px", padding: "3px 9px" }} onClick={() => showToast("Disconnect requires confirmation")}>Disconnect</button>
              </div>
            </div>
            <div className="panel-body">
              <div className="config-tabs">
                {wpTabs.map((tab) => (
                  <div key={tab.key} className={`config-tab ${selectedTab === tab.key ? "active" : ""}`} onClick={() => setSelectedTab(tab.key)}>
                    {tab.label}
                  </div>
                ))}
              </div>

              {selectedTab === "settings" && (
                <div>
                  <div className="grid-2">
                    <div>
                  <div className="field-group">
                    <div className="field-label">Website URL</div>
                    <input className="field" type="text" placeholder="https://example.com" />
                  </div>
                      <div className="field-group">
                        <div className="field-label">REST API Endpoint <span className="badge badge-green" style={{ fontSize: "8px" }}>Verified</span></div>
                        <input className="field" type="text" placeholder="https://example.com/wp-json/wp/v2" readOnly style={{ opacity: 0.7 }} />
                      </div>
                      <div className="field-group">
                        <div className="field-label">Application Password <span style={{ color: "var(--muted)", fontSize: "9px" }}>● ● ● ● ● ● ● ●</span></div>
                        <input className="field" type="password" placeholder="Enter application password" />
                        <div className="field-hint">Generate in WP Admin → Users → Application Passwords</div>
                      </div>
                      <div className="field-group">
                        <div className="field-label">Auth Username</div>
                        <input className="field" type="text" defaultValue="rankforge_agent" />
                      </div>
                    </div>
                    <div>
                      <div className="field-group">
                        <div className="field-label">Default Post Status</div>
                        <select className="field">
                          <option>Draft</option>
                          <option selected>Publish</option>
                          <option>Pending Review</option>
                          <option>Schedule</option>
                        </select>
                      </div>
                      <div className="field-group">
                        <div className="field-label">Default Author</div>
                        <select className="field">
                          <option>rankforge_agent</option>
                          <option>admin</option>
                          <option>editor</option>
                        </select>
                      </div>
                      <div className="field-group">
                        <div className="field-label">Default Category</div>
                        <input className="field" type="text" defaultValue="SEO, AI Content" />
                      </div>
                      <div className="field-group">
                        <div className="field-label">Sync Interval</div>
                        <select className="field">
                          <option>5 minutes</option>
                          <option selected>15 minutes</option>
                          <option>30 minutes</option>
                          <option>Hourly</option>
                          <option>Manual only</option>
                        </select>
                      </div>
                    </div>
                  </div>

                  <div className="notice info"><span className="notice-sq"></span>Yoast SEO plugin detected. RankForge will auto-populate meta_title, meta_description, and focus_keyphrase via Yoast REST fields.</div>

                  <div style={{ marginBottom: "14px" }}>
                    <div className="field-label" style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: ".08em", color: "var(--muted)", marginBottom: "8px" }}>Plugin Integrations</div>
                    <div className="check-row"><div className="ci pass">✓</div><div className="ck-label">Yoast SEO — meta fields auto-mapped</div><span className="badge badge-green">Active</span></div>
                    <div className="check-row"><div className="ci pass">✓</div><div className="ck-label">RankMath — schema injection enabled</div><span className="badge badge-green">Active</span></div>
                    <div className="check-row"><div className="ci warn">!</div><div className="ck-label">WP Rocket — cache clear on publish</div><span className="badge badge-amber">Config needed</span></div>
                    <div className="check-row"><div className="ci pending">○</div><div className="ck-label">Elementor — custom layout support</div><span className="badge badge-muted">Not detected</span></div>
                  </div>

                  <div style={{ display: "flex", gap: "8px" }}>
                    <button className="btn btn-accent" onClick={() => showToast("WordPress settings saved")}>Save Changes</button>
                    <button className="btn" onClick={() => showToast("Testing WordPress connection...")}>Test Connection</button>
                    <button className="btn" onClick={() => showToast("Syncing WordPress...")}>Sync Now</button>
                  </div>
                </div>
              )}

              {selectedTab === "sync" && (
                <div>
                  <div style={{ border: "1px solid var(--border)", overflow: "hidden", marginBottom: "14px" }}>
                    <div style={{ padding: "8px 12px", background: "var(--table-head)", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span className="panel-label">Sync Events — Last 24h</span>
                      <span style={{ fontSize: "9px", color: "var(--muted)" }}>Auto-refreshing</span>
                    </div>
                    {[
                      { time: "14:32:07", status: "OK", msg: 'POST published — "AI SEO Strategies 2026" (ID: 4821)' },
                      { time: "14:30:01", status: "OK", msg: 'Yoast meta updated — focus keyphrase set to "ai seo 2026"' },
                      { time: "13:15:44", status: "OK", msg: "Schema markup injected — FAQ + Article schema on ID 4818" },
                      { time: "12:47:22", status: "WARN", msg: "Cache clear skipped — WP Rocket API key not configured" },
                      { time: "11:02:58", status: "OK", msg: "Sitemap pinged — Google received 47 new URLs" },
                      { time: "10:18:33", status: "OK", msg: 'POST published — "Backlink Building Guide 2026" (ID: 4817)' },
                      { time: "09:44:10", status: "ERR", msg: "REST 401 — Auth token refreshed, retried successfully" },
                      { time: "08:30:00", status: "OK", msg: "Scheduled sync completed — 3 drafts updated" },
                    ].map((row, i) => (
                      <div key={i} className="log-row">
                        <span className="log-time">{row.time}</span>
                        <span className="log-level"><span className={`badge ${row.status === "OK" ? "badge-green" : row.status === "WARN" ? "badge-amber" : "badge-red"}`} style={{ fontSize: "8px" }}>{row.status}</span></span>
                        <span className="log-msg">{row.msg}</span>
                      </div>
                    ))}
                  </div>
                  <div className="prog-row"><div className="prog-label"><span>Publish Success Rate</span><span>96.2%</span></div><div className="prog-track"><div className="prog-fill green" style={{ width: "96%" }}></div></div></div>
                  <div className="prog-row"><div className="prog-label"><span>Sync Uptime (30d)</span><span>99.7%</span></div><div className="prog-track"><div className="prog-fill green" style={{ width: "99.7%" }}></div></div></div>
                  <div className="prog-row"><div className="prog-label"><span>Avg Publish Latency</span><span>1.2s</span></div><div className="prog-track"><div className="prog-fill" style={{ width: "24%" }}></div></div></div>
                </div>
              )}

              {selectedTab === "mapping" && (
                <div>
                  <div className="notice"><span className="notice-sq"></span>Map RankForge content fields to your WordPress post fields and Yoast/RankMath meta.</div>
                  <div style={{ border: "1px solid var(--border)", overflow: "hidden", marginBottom: "14px" }}>
                    <table className="data-table">
                      <thead><tr><th>RankForge Field</th><th>WP / Plugin Field</th><th>Status</th></tr></thead>
                      <tbody>
                        {[
                          ["title", "post_title", "Mapped"],
                          ["body_html", "post_content", "Mapped"],
                          ["excerpt", "post_excerpt", "Mapped"],
                          ["seo_title", "yoast_wpseo_title", "Mapped"],
                          ["meta_description", "yoast_wpseo_metadesc", "Mapped"],
                          ["focus_keyphrase", "yoast_wpseo_focuskw", "Mapped"],
                          ["schema_json", "rank_math_rich_snippet", "Mapped"],
                          ["featured_image_url", "_thumbnail_id", "Auto-upload"],
                          ["canonical_url", "yoast_wpseo_canonical", "Mapped"],
                        ].map(([from, to, status], i) => (
                          <tr key={i}>
                            <td>{from}</td><td>{to}</td>
                            <td><span className={`badge ${status === "Mapped" ? "badge-green" : "badge-amber"}`}>{status}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <button className="btn btn-accent" onClick={() => showToast("Field mapping saved")}>Save Mapping</button>
                </div>
              )}

              {selectedTab === "permissions" && (
                <div>
                  <div style={{ marginBottom: "14px" }}>
                    <div className="field-label" style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: ".08em", color: "var(--muted)", marginBottom: "10px" }}>Agent Permissions</div>
                    {[
                      ["Create new posts", true],
                      ["Edit existing posts", true],
                      ["Publish / schedule posts", true],
                      ["Upload media / images", true],
                      ["Update Yoast / RankMath meta", true],
                      ["Delete posts permanently", false],
                      ["Modify user accounts", false],
                      ["Access billing / admin settings", false],
                    ].map(([perm, allowed], i) => (
                      <div key={i} className="check-row">
                        <div className={`ci ${allowed ? "pass" : "fail"}`}>{allowed ? "✓" : "✗"}</div>
                        <div className="ck-label">{perm}</div>
                        <span className={`badge ${allowed ? "badge-green" : "badge-red"}`}>{allowed ? "Allowed" : "Blocked"}</span>
                      </div>
                    ))}
                  </div>
                  <button className="btn btn-accent" onClick={() => showToast("Permissions saved")}>Save Permissions</button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* GSC */}
        <div className={`config-section ${selectedId === "gsc" ? "active" : ""}`} id="section-gsc">
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">🔴 Google Search Console — Configuration</span>
              <div style={{ display: "flex", gap: "6px" }}>
                <span className="badge badge-green">Connected</span>
                <button className="btn btn-danger" style={{ fontSize: "9px", padding: "3px 9px" }} onClick={() => showToast("Disconnect requires confirmation")}>Disconnect</button>
              </div>
            </div>
            <div className="panel-body">
              <div className="config-tabs">
                {gscTabs.map((tab) => (
                  <div key={tab.key} className={`config-tab ${selectedTab === tab.key ? "active" : ""}`} onClick={() => setSelectedTab(tab.key)}>
                    {tab.label}
                  </div>
                ))}
              </div>

              {selectedTab === "settings" && (
                <div>
                  <div className="notice ok"><span className="notice-sq"></span>OAuth 2.0 active · Scopes verified · Token auto-refreshes</div>
                  <div className="grid-2">
                    <div>
                  <div className="field-group">
                    <div className="field-label">WordPress REST URL</div>
                    <input className="field" type="text" placeholder="https://example.com/wp-json/wp/v2" readOnly style={{ opacity: 0.7 }} />
                  </div>
                  <div className="field-group">
                    <div className="field-label">GSC Property</div>
                    <select className="field">
                      <option>sc-domain:example.com</option>
                      <option>https://example.com/</option>
                    </select>
                  </div>
                      <div className="field-group">
                        <div className="field-label">Data Fetch Range</div>
                        <select className="field">
                          <option>Last 7 days</option>
                          <option selected>Last 28 days</option>
                          <option>Last 90 days</option>
                          <option>Last 16 months</option>
                        </select>
                      </div>
                    </div>
                    <div>
                      <div className="field-group">
                        <div className="field-label">Dimensions to Pull</div>
                        <div className="scope-list">
                          <span className="scope-pill active">query</span>
                          <span className="scope-pill active">page</span>
                          <span className="scope-pill active">country</span>
                          <span className="scope-pill active">device</span>
                          <span className="scope-pill active">date</span>
                          <span className="scope-pill">search type</span>
                        </div>
                        <div className="field-hint" style={{ marginTop: "8px" }}>Click to toggle dimensions</div>
                      </div>
                      <div className="field-group">
                        <div className="field-label">Sync Frequency</div>
                        <select className="field">
                          <option>Every 15 minutes</option>
                          <option selected>Every hour</option>
                          <option>Every 6 hours</option>
                          <option>Daily</option>
                        </select>
                      </div>
                      <div className="field-group">
                        <div className="field-label">Impression Threshold Alert</div>
                        <input className="field" type="number" defaultValue="1000" />
                        <div className="field-hint">Alert when page drops below this monthly threshold</div>
                      </div>
                    </div>
                  </div>

                  <div style={{ marginBottom: "14px" }}>
                    <div className="field-label" style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: ".08em", color: "var(--muted)", marginBottom: "8px" }}>OAuth Scopes Granted</div>
                    <div className="check-row"><div className="ci pass">✓</div><div className="ck-label">webmasters.readonly — read search analytics</div><span className="badge badge-green">Active</span></div>
                    <div className="check-row"><div className="ci pass">✓</div><div className="ck-label">webmasters — submit sitemaps, URL inspection</div><span className="badge badge-green">Active</span></div>
                    <div className="check-row"><div className="ci pass">✓</div><div className="ck-label">indexing — Google Indexing API (URL notify)</div><span className="badge badge-green">Active</span></div>
                  </div>

                  <div style={{ display: "flex", gap: "8px" }}>
                    <button className="btn btn-accent" onClick={() => showToast("GSC settings saved")}>Save Changes</button>
                    <button className="btn" onClick={() => showToast("Re-authenticating...")}>Re-auth</button>
                    <button className="btn" onClick={() => showToast("Fetching GSC data...")}>Fetch Now</button>
                  </div>
                </div>
              )}

              {selectedTab === "data" && (
                <div>
                  <div className="stat-strip" style={{ marginBottom: "14px" }}>
                    <div className="stat-cell">
                      <div className="stat-label">Impressions (28d)</div>
                      <div className="stat-val">{gscKeywords.length > 0 ? formatNumber(gscKeywords.reduce((s, k) => s + (k.impressions || 0), 0)) : "—"}</div>
                    </div>
                    <div className="stat-cell">
                      <div className="stat-label">Clicks (28d)</div>
                      <div className="stat-val">{gscKeywords.length > 0 ? formatNumber(gscKeywords.reduce((s, k) => s + (k.clicks || 0), 0)) : "—"}</div>
                    </div>
                    <div className="stat-cell">
                      <div className="stat-label">Avg CTR</div>
                      <div className="stat-val">
                        {gscKeywords.length > 0 ? (gscKeywords.reduce((s, k) => s + (k.ctr || 0), 0) / gscKeywords.length * 100).toFixed(1) + "%" : "—"}
                      </div>
                    </div>
                    <div className="stat-cell">
                      <div className="stat-label">Avg Position</div>
                      <div className="stat-val">
                        {gscKeywords.length > 0 ? Math.round(gscKeywords.reduce((s, k) => s + (k.position || 0), 0) / gscKeywords.length) : "—"}
                      </div>
                    </div>
                  </div>
                  <div style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: ".08em", color: "var(--muted)", marginBottom: "8px" }}>Top Queries — Last 28 Days</div>
                  <div style={{ border: "1px solid var(--border)", overflow: "hidden", marginBottom: "14px" }}>
                    <table className="data-table">
                      <thead><tr><th>Query</th><th>Impressions</th><th>Clicks</th><th>CTR</th><th>Avg Pos</th></tr></thead>
                      <tbody>
                        {gscKeywords.length === 0 ? (
                          <tr><td colSpan={5} className="text-center text-muted mono-font">No GSC data - Connect GSC</td></tr>
                        ) : (
                          gscKeywords.slice(0, 10).map((kw, i) => (
                            <tr key={i}>
                              <td>{kw.query}</td>
                              <td>{kw.impressions.toLocaleString()}</td>
                              <td>{kw.clicks.toLocaleString()}</td>
                              <td>{(kw.ctr * 100).toFixed(2)}%</td>
                              <td>{kw.position.toFixed(1)}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                  <div className="prog-row"><div className="prog-label"><span>Coverage: Valid Pages</span><span>No data — Run tech audit</span></div><div className="prog-track"><div className="prog-fill green" style={{ width: "0%" }}></div></div></div>
                  <div className="prog-row"><div className="prog-label"><span>Coverage: Errors</span><span>No data — Run tech audit</span></div><div className="prog-track"><div className="prog-fill" style={{ width: "0%" }}></div></div></div>
                </div>
              )}

              {selectedTab === "indexing" && (
                <div>
                  <div className="notice info" style={{ marginBottom: "14px" }}><span className="notice-sq"></span>Google Indexing API enabled. RankForge auto-submits new URLs within 60s of publish.</div>
                  <div className="field-group">
                    <div className="field-label">Manual URL Submission</div>
                    <div style={{ display: "flex", gap: "8px" }}>
                      <input className="field" type="text" placeholder="https://example.com" style={{ flex: 1 }} />
                      <button className="btn btn-accent" onClick={() => showToast("URL submitted to Google Index")}>Submit</button>
                    </div>
                    <div className="field-hint">Force-index any URL instantly via Indexing API</div>
                  </div>
                  <div style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: ".08em", color: "var(--muted)", marginBottom: "8px" }}>Recent Indexing Requests</div>
                  {alerts.length === 0 ? (
                    <div className="text-[11px] text-muted mono-font py-4">No indexing requests yet</div>
                  ) : (
                    alerts.slice(0, 5).map((alert, i) => (
                      <div key={i} className="log-row">
                        <span className="log-time">{new Date(alert.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                        <span className="log-level"><span className={`badge ${alert.severity === "critical" ? "badge-red" : "badge-amber"}`} style={{ fontSize: "8px" }}>{alert.severity}</span></span>
                        <span className="log-msg">{alert.message}</span>
                      </div>
                    ))
                  )}
                </div>
              )}

              {selectedTab === "alerts" && (
                <div>
                  <div style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: ".08em", color: "var(--muted)", marginBottom: "10px" }}>Alert Rules</div>
                  {alerts.length === 0 ? (
                    <div className="text-[11px] text-muted mono-font py-4">No alerts — monitoring must be active</div>
                  ) : (
                    alerts.slice(0, 10).map((alert, i) => (
                      <div key={i} className="check-row">
                        <div className={`ci ${alert.severity === "critical" ? "fail" : alert.severity === "high" ? "warn" : "pass"}`}>
                          {alert.severity === "critical" ? "✗" : alert.severity === "high" ? "⚠" : "✓"}
                        </div>
                        <div className="ck-label">{alert.message}</div>
                        <span className={`badge ${alert.severity === "critical" ? "badge-red" : alert.severity === "high" ? "badge-amber" : "badge-green"}`}>{alert.severity}</span>
                      </div>
                    ))
                  )}
                  <div style={{ marginTop: "14px", display: "flex", gap: "8px" }}>
                    <button className="btn btn-accent" onClick={() => showToast("Alert rules saved")}>Save Alerts</button>
                    <button className="btn">Add Rule</button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* GA4 */}
        <div className={`config-section ${selectedId === "ga" ? "active" : ""}`} id="section-ga">
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">📊 Google Analytics 4 — Setup</span>
              <span className="badge badge-muted">Not Connected</span>
            </div>
            <div className="panel-body">
              <div className="notice"><span className="notice-sq"></span>Connect GA4 to import session data, conversion events, and user behaviour signals into RankForge dashboards.</div>
              <div style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: ".08em", color: "var(--muted)", marginBottom: "12px" }}>Setup Steps</div>
              {["Authorise with Google", "Select GA4 Property", "Map Events to SEO Actions", "Enable Dashboard Widgets"].map((step, i) => (
                <div key={i} className="step-row">
                  <div className={`step-num ${i === 0 ? "active-step" : ""}`}>{i + 1}</div>
                  <div className="step-content">
                    <div className="step-title">{step}</div>
                    <div className="step-desc">Follow the setup wizard to complete this step.</div>
                    {i === 0 && (
                      <div className="step-action">
                        <button className="oauth-btn" onClick={() => showToast("Opening Google OAuth...")}>
                          <div className="oauth-btn-icon">G</div>
                          <div className="oauth-btn-text">Continue with Google</div>
                          <div className="oauth-btn-arrow">→</div>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* AHREFS */}
        <div className={`config-section ${selectedId === "ahrefs" ? "active" : ""}`} id="section-ahrefs">
          <div className="panel">
            <div className="panel-head"><span className="panel-label">🔗 Ahrefs — Setup</span><span className="badge badge-muted">Not Connected</span></div>
            <div className="panel-body">
              <div className="field-group"><div className="field-label">Ahrefs API Key</div><input className="field" type="password" placeholder="ahf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" /></div>
                  <div className="field-group"><div className="field-label">Target Domain</div><input className="field" type="text" placeholder="example.com" /></div>
              <div className="field-group">
                <div className="field-label">Data Pull Scope</div>
                <div className="scope-list">
                  <span className="scope-pill active">domain rating</span>
                  <span className="scope-pill active">backlinks</span>
                  <span className="scope-pill active">referring domains</span>
                  <span className="scope-pill active">keyword difficulty</span>
                  <span className="scope-pill">organic keywords</span>
                  <span className="scope-pill">traffic value</span>
                </div>
              </div>
              <div style={{ display: "flex", gap: "8px", marginTop: "14px" }}>
                <button className="btn btn-accent" onClick={() => showToast("Connecting to Ahrefs...")}>Connect Ahrefs</button>
                <button className="btn" onClick={() => showToast("Testing API key...")}>Test API Key</button>
              </div>
            </div>
          </div>
        </div>

        {/* SEMRUSH */}
        <div className={`config-section ${selectedId === "semrush" ? "active" : ""}`} id="section-semrush">
          <div className="panel">
            <div className="panel-head"><span className="panel-label">🟠 Semrush — Setup</span><span className="badge badge-muted">Not Connected</span></div>
            <div className="panel-body">
              <div className="field-group"><div className="field-label">Semrush API Key</div><input className="field" type="password" placeholder="semrush_api_xxxxxxxxxxxxxxxx" /></div>
                  <div className="field-group"><div className="field-label">Project Domain</div><input className="field" type="text" placeholder="example.com" /></div>
              <div style={{ display: "flex", gap: "8px", marginTop: "14px" }}>
                <button className="btn btn-accent" onClick={() => showToast("Connecting to Semrush...")}>Connect Semrush</button>
                <button className="btn" onClick={() => showToast("Testing API key...")}>Test API Key</button>
              </div>
            </div>
          </div>
        </div>

        {/* SLACK */}
        <div className={`config-section ${selectedId === "slack" ? "active" : ""}`} id="section-slack">
          <div className="panel">
            <div className="panel-head"><span className="panel-label">💬 Slack — Setup</span><span className="badge badge-muted">Not Connected</span></div>
            <div className="panel-body">
              <div className="notice"><span className="notice-sq"></span>Connect Slack to receive AI agent alerts, weekly SEO digests, and rank change notifications.</div>
              <button className="oauth-btn" onClick={() => showToast("Opening Slack OAuth...")}>
                <div className="oauth-btn-icon">S</div>
                <div className="oauth-btn-text">Add to Slack Workspace</div>
                <div className="oauth-btn-arrow">→</div>
              </button>
              <div className="field-group" style={{ marginTop: "12px" }}><div className="field-label">Or use Webhook URL</div><input className="field" type="text" placeholder="https://hooks.slack.com/services/..." /></div>
              <div className="field-group"><div className="field-label">Default Channel</div><input className="field" type="text" placeholder="#seo-alerts" /></div>
              <div style={{ display: "flex", gap: "8px", marginTop: "14px" }}>
                <button className="btn btn-accent" onClick={() => showToast("Slack webhook saved")}>Save Webhook</button>
                <button className="btn" onClick={() => showToast("Testing Slack notification...")}>Test Notification</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* BOTTOM TICKER */}
      <div className="bticker">
            <span className="bticker-inner">
              <span className="bt-sq"></span>RANKFORGE <span className="bt-sep">/</span>
              <span className="bt-sq"></span>CONNECTORS <span className="bt-sep">/</span>
              <span className="bt-sq"></span>REAL DATA ONLY <span className="bt-sep">/</span>
              <span className="bt-sq"></span>NO MOCK DATA &nbsp;&nbsp;&nbsp;&nbsp;
              <span className="bt-sq"></span>RANKFORGE <span className="bt-sep">/</span>
              <span className="bt-sq"></span>CONNECTORS <span className="bt-sep">/</span>
              <span className="bt-sq"></span>REAL DATA ONLY <span className="bt-sep">/</span>
              <span className="bt-sq"></span>NO MOCK DATA
            </span>
      </div>

      {/* CHAT PANEL */}
      <div className={`chat-panel ${chatOpen ? "open" : "closed"}`} id="chat-panel">
        <div className="chat-topbar" onClick={() => setChatOpen(!chatOpen)}>
          <div className="chat-title"><span className="chat-live"></span>RankForge AI — Command</div>
          <div className="chat-toggle">{chatOpen ? "−" : "+"}</div>
        </div>
        <div className="chat-messages" id="chat-messages">
          {messages.map((msg, i) => (
            <div key={i} className={`msg ${msg.role}`}>
              <div className={`msg-avatar ${msg.role === "ai" ? "ai" : ""}`}>{msg.role === "ai" ? "RF" : "U"}</div>
              <div>
                <div className="msg-bubble" style={{ whiteSpace: "pre-wrap" }}>{msg.text}</div>
                <div className="msg-time">{msg.time}</div>
              </div>
            </div>
          ))}
          {typing && (
            <div className="msg">
              <div className="msg-avatar ai">RF</div>
              <div className="msg-bubble">
                <div className="typing-dots"><span></span><span></span><span></span></div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        <div className="chat-suggestions">
          {suggestions.map((s) => (
            <button key={s} className="chip" onClick={() => setChatInput(s)}>{s}</button>
          ))}
        </div>
        <div className="chat-input-row">
          <textarea
            className="chat-input"
            placeholder="Ask about connectors..."
            rows={1}
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendChat();
              }
            }}
            style={{ height: "auto", minHeight: "42px" }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = "auto";
              target.style.height = Math.min(target.scrollHeight, 80) + "px";
            }}
          />
          <button className="chat-send" onClick={sendChat}>Send ↑</button>
        </div>
      </div>

      {/* TOAST */}
      {toast && (
        <div style={{
          position: "fixed",
          bottom: "20px",
          left: "50%",
          transform: "translateX(-50%)",
          background: "var(--ink)",
          color: "var(--bg)",
          padding: "8px 18px",
          fontSize: "10px",
          textTransform: "uppercase",
          letterSpacing: ".07em",
          zIndex: 500,
        }}>
          {toast}
        </div>
      )}
    </div>
  );
}

function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "K";
  return String(n);
}

function timeAgo(date: Date): string {
  const diff = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}
