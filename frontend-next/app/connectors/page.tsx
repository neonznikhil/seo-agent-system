"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface Connector {
  id: string;
  name: string;
  description: string;
  connected: boolean;
  version?: string | null;
  last_sync?: string;
  error?: string;
}

export default function ConnectorsPage() {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [websiteId, setWebsiteId] = useState<string>("");

  const loadConnectors = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);
    if (!wid) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = await get(`/api/connectors/${wid}`);
      const list = Array.isArray(data) ? data : data?.connectors || [];
      setConnectors(list);
    } catch (e: any) {
      console.warn("Connectors fetch error:", e);
      setError(e.message || "Failed to load connectors");
      setConnectors([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConnectors();
    const handleChanged = () => loadConnectors();
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [loadConnectors]);

  if (loading && connectors.length === 0) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px auto" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Loading service connectors & API bridges...
        </p>
      </div>
    );
  }

  if (!websiteId) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">Service Connectors</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No data yet — add a website first.</strong> Connect your website to configure WordPress, GSC, PageSpeed, and Slack bridges.
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
      <div className="page-heading">Service Connectors & Integrations</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        WordPress REST API · Google Search Console · PageSpeed · Slack Webhooks
        {error && (
          <span className="badge badge-amber" style={{ marginLeft: "12px" }}>
            {error}
          </span>
        )}
      </div>

      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Active Connector Integrations</span>
          <button className="panel-action" onClick={loadConnectors}>
            Refresh
          </button>
        </div>
        <div className="panel-body">
          {connectors.length === 0 ? (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              No third-party connectors active. Configure WordPress and other integrations in Settings.
              <div style={{ marginTop: "12px" }}>
                <Link href="/settings" className="btn btn-accent" style={{ textDecoration: "none", fontSize: "11px" }}>
                  Go to Settings
                </Link>
              </div>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "16px" }}>
              {connectors.map((c) => (
                <div key={c.id} style={{ padding: "16px", border: "1px solid var(--line)", background: "var(--surface)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                    <span style={{ fontWeight: 600, fontSize: "14px" }}>{c.name}</span>
                    <span className={`badge ${c.connected ? "badge-green" : "badge-amber"}`}>
                      {c.connected ? "Connected" : "Disconnected"}
                    </span>
                  </div>
                  <p style={{ fontSize: "12px", color: "var(--muted)", marginBottom: "12px" }}>{c.description}</p>
                  <Link
                    href="/settings"
                    className="btn"
                    style={{ display: "inline-block", textDecoration: "none", fontSize: "11px", padding: "4px 10px" }}
                  >
                    Configure
                  </Link>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
