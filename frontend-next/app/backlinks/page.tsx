"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface BacklinkItem {
  id?: string;
  source_url?: string;
  backlink_url?: string;
  prospect_url?: string;
  anchor_text?: string;
  domain_rating?: number;
  status?: string;
  checked_at?: string;
  created_at?: string;
}

export default function BacklinksPage() {
  const [backlinks, setBacklinks] = useState<BacklinkItem[]>([]);
  const [prospects, setProspects] = useState<BacklinkItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [discovering, setDiscovering] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [noticeMsg, setNoticeMsg] = useState<string | null>(null);
  const [websiteId, setWebsiteId] = useState<string>("");

  const loadBacklinks = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);
    if (!wid) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const data = await get(`/api/backlinks/${wid}`);
      if (data) {
        setBacklinks(data.monitor || data.backlinks || []);
        setProspects(data.prospects || []);
      }
    } catch (e: any) {
      console.warn("Backlink load error:", e);
      setError(e.message || "Failed to load backlink intelligence");
      setBacklinks([]);
      setProspects([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBacklinks();
    const handleChanged = () => loadBacklinks();
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [loadBacklinks]);

  const handleRunProspects = async () => {
    if (!websiteId) return;
    try {
      setDiscovering(true);
      setError(null);
      setNoticeMsg("Running autonomous backlink prospect crawler...");

      await post(`/api/backlinks/${websiteId}/prospect`, {
        primary_keyword: "seo legal settlements",
      });

      setNoticeMsg("✓ Backlink prospect search completed!");
      loadBacklinks();
    } catch (err: any) {
      setError(`Prospect crawler error: ${err.message}`);
    } finally {
      setDiscovering(false);
    }
  };

  if (loading && backlinks.length === 0 && prospects.length === 0) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px auto" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Scanning inbound backlink profile & outreach prospects...
        </p>
      </div>
    );
  }

  if (!websiteId) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">Backlink Intelligence</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No data yet — add a website first.</strong> Connect your website to verify live backlinks and discover outreach prospects.
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
      <div className="page-heading">Backlinks & Authority Building</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Live Link Monitor · Broken Backlink Recovery · Outreach Opportunity Crawler
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

      <div className="kpi-strip" style={{ marginBottom: "20px" }}>
        <div className="kpi-cell">
          <div className="kpi-label">Monitored Backlinks</div>
          <div className="kpi-val">{backlinks.length}</div>
          <div className="kpi-delta">Active crawler verified</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Prospect Opportunities</div>
          <div className="kpi-val" style={{ color: "var(--accent)" }}>{prospects.length}</div>
          <div className="kpi-delta">Discovered link targets</div>
        </div>
      </div>

      <div className="dash-grid">
        {/* MONITORED BACKLINKS */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">Active Monitored Backlinks</span>
            <button className="panel-action" onClick={loadBacklinks}>
              Refresh
            </button>
          </div>
          <div className="panel-body" style={{ padding: "0" }}>
            {backlinks.length === 0 ? (
              <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
                No active backlinks recorded. The system continuously monitors referring domains.
              </div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "12px" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--line)", color: "var(--muted)", textTransform: "uppercase", fontSize: "10px" }}>
                    <th style={{ padding: "10px 14px" }}>Source Domain</th>
                    <th style={{ padding: "10px 14px" }}>Anchor Text</th>
                    <th style={{ padding: "10px 14px" }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {backlinks.map((b, i) => (
                    <tr key={b.id || i} style={{ borderBottom: "1px solid var(--line)" }}>
                      <td style={{ padding: "10px 14px", fontWeight: 600 }}>{b.source_url || b.backlink_url}</td>
                      <td style={{ padding: "10px 14px" }}>{b.anchor_text || "Brand Anchor"}</td>
                      <td style={{ padding: "10px 14px" }}>
                        <span className="badge badge-green">{b.status || "Active"}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* PROSPECTS */}
        <div className="panel">
          <div className="panel-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span className="panel-label">Link Outreach Targets</span>
            <button onClick={handleRunProspects} disabled={discovering} className="btn btn-accent" style={{ padding: "4px 10px", fontSize: "11px" }}>
              {discovering ? "Crawling Targets..." : "⚡ Discover Targets"}
            </button>
          </div>
          <div className="panel-body" style={{ padding: "0" }}>
            {prospects.length === 0 ? (
              <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
                No outreach targets discovered yet. Click "Discover Targets" above.
              </div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "12px" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--line)", color: "var(--muted)", textTransform: "uppercase", fontSize: "10px" }}>
                    <th style={{ padding: "10px 14px" }}>Target URL</th>
                    <th style={{ padding: "10px 14px" }}>Strategy</th>
                  </tr>
                </thead>
                <tbody>
                  {prospects.map((p, i) => (
                    <tr key={p.id || i} style={{ borderBottom: "1px solid var(--line)" }}>
                      <td style={{ padding: "10px 14px", fontWeight: 600 }}>{p.prospect_url || p.source_url}</td>
                      <td style={{ padding: "10px 14px" }}>
                        <span className="badge badge-accent">{p.status || "High Authority"}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}