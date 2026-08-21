"use client";

import { useEffect, useState } from "react";
import {
  WordPressSite,
  connectWordPress,
  deleteWordPressSite,
  listWordPressSites,
  testWordPress,
} from "@/lib/wordpress";

export default function WordPressConnect() {
  const [siteUrl, setSiteUrl] = useState("");
  const [username, setUsername] = useState("");
  const [appPassword, setAppPassword] = useState("");
  const [sites, setSites] = useState<WordPressSite[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadSites = async () => {
    try {
      setSites(await listWordPressSites());
    } catch (e: any) {
      setError(e.message || "Failed to load connected sites");
    }
  };

  useEffect(() => {
    loadSites();
  }, []);

  const credentials = () => ({
    site_url: siteUrl.trim(),
    username: username.trim(),
    app_password: appPassword.trim(),
  });

  const missingFields = !siteUrl.trim() || !username.trim() || !appPassword.trim();

  const handleTest = async () => {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const result = await testWordPress(credentials());
      setStatus(`Connection OK - authenticated as ${result.user?.name || username}`);
    } catch (e: any) {
      setError(e.message || "Connection test failed");
    } finally {
      setBusy(false);
    }
  };

  const handleConnect = async () => {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      await testWordPress(credentials());
      const result = await connectWordPress(credentials());
      setStatus(`Connected - ${result?.site?.site_url || siteUrl}`);
      setAppPassword("");
      await loadSites();
    } catch (e: any) {
      setError(e.message || "Failed to connect site");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (site: WordPressSite) => {
    setBusy(true);
    setError(null);
    try {
      await deleteWordPressSite(site.id);
      await loadSites();
    } catch (e: any) {
      setError(e.message || "Failed to remove site");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel" style={{ marginBottom: "14px" }}>
      <div className="panel-head">
        <span className="panel-label">WordPress — Application Password</span>
        <span className={`badge ${sites.length > 0 ? "badge-green" : "badge-muted"}`}>
          {sites.length > 0 ? "Connected" : "Not Connected"}
        </span>
      </div>
      <div className="panel-body">
        <div className="grid-2">
          <div>
            <div className="field-group">
              <div className="field-label">WordPress URL</div>
              <input
                className="field"
                type="text"
                value={siteUrl}
                placeholder="https://example.com"
                onChange={(e) => setSiteUrl(e.target.value)}
              />
            </div>
            <div className="field-group">
              <div className="field-label">Username</div>
              <input
                className="field"
                type="text"
                value={username}
                placeholder="wp-admin username"
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
          </div>
          <div>
            <div className="field-group">
              <div className="field-label">Application Password</div>
              <input
                className="field"
                type="password"
                value={appPassword}
                placeholder="xxxx xxxx xxxx xxxx xxxx xxxx"
                onChange={(e) => setAppPassword(e.target.value)}
              />
              <div className="field-hint">
                WP Admin → Users → Your User → Application Passwords → New → Copy
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", gap: "8px", marginBottom: "12px" }}>
          <button className="btn" disabled={busy || missingFields} onClick={handleTest}>
            {busy ? "Working..." : "Test Connection"}
          </button>
          <button className="btn btn-accent" disabled={busy || missingFields} onClick={handleConnect}>
            Connect Site
          </button>
        </div>

        {status && <div className="notice info"><span className="notice-sq"></span>{status}</div>}
        {error && <div className="notice warn"><span className="notice-sq"></span>{error}</div>}

        <div className="field-label" style={{ marginTop: "12px", marginBottom: "6px" }}>
          Connected Sites ({sites.length})
        </div>
        {sites.length === 0 ? (
          <div style={{ fontSize: "11px", color: "var(--muted)" }}>No WordPress site connected yet.</div>
        ) : (
          sites.map((site) => (
            <div key={site.id} className="check-row">
              <div className="ci pass">✓</div>
              <div className="ck-label">
                {site.site_url} — {site.username}
                {site.source === "env" ? " (from .env)" : ""}
              </div>
              <span className="badge badge-green">Connected</span>
              {site.source !== "env" && (
                <button
                  className="btn btn-danger"
                  style={{ fontSize: "9px", padding: "3px 9px", marginLeft: "8px" }}
                  disabled={busy}
                  onClick={() => handleDelete(site)}
                >
                  Remove
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
