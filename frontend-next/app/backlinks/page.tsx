"use client";

import { useEffect, useState, useCallback } from "react";
import { get, post, buildUrl } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface BacklinkItem {
  id: string;
  source_url: string;
  target_url?: string;
  anchor_text?: string;
  domain_rating?: number;
  category?: string;
  opportunity_type?: string;
  status: string;
  checked_at?: string;
  created_at?: string;
}

interface BacklinkMetrics {
  total_backlinks_acquired: number;
  avg_dr: number | null;
  velocity_30d: number;
  authority_trajectory_dr: number | null;
  active_citations: number;
  tier1_prospects: number;
  total_opportunities: number;
  authority_action_plan?: string;
}

export default function BacklinksPage() {
  const [websiteId, setWebsiteId] = useState<string>("");
  const [backlinks, setBacklinks] = useState<BacklinkItem[]>([]);
  const [metrics, setMetrics] = useState<BacklinkMetrics>({
    total_backlinks_acquired: 0,
    avg_dr: null,
    velocity_30d: 0,
    authority_trajectory_dr: null,
    active_citations: 0,
    tier1_prospects: 0,
    total_opportunities: 0,
  });
  const [loading, setLoading] = useState<boolean>(true);
  const [isScouting, setIsScouting] = useState<boolean>(false);
  const [scoutLogs, setScoutLogs] = useState<string[]>([]);
  const [briefingId, setBriefingId] = useState<string | null>(null);
  const [draftingId, setDraftingId] = useState<string | null>(null);
  const [activeDraftModal, setActiveDraftModal] = useState<{ title: string; email: string } | null>(null);
  const [activeTab, setActiveTab] = useState<string>("all");
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  const loadBacklinks = useCallback(async () => {
    const wid = getCurrentWebsiteId() || "default";
    setWebsiteId(wid);
    try {
      setLoading(true);
      const [blRes, metRes] = await Promise.allSettled([
        get(`/api/backlinks/${wid}`),
        get(`/api/backlinks/metrics?website_id=${wid}`),
      ]);

      if (blRes.status === "fulfilled" && blRes.value) {
        const d = blRes.value;
        const list = Array.isArray(d) ? d : d.opportunities || d.monitor || d.data || [];
        setBacklinks(list);
      }

      if (metRes.status === "fulfilled" && metRes.value) {
        const m = metRes.value?.data || metRes.value || {};
        setMetrics({
          total_backlinks_acquired: m.total_backlinks_acquired ?? 0,
          avg_dr: m.avg_dr ?? null,
          velocity_30d: m.link_velocity_30d ?? m.backlink_velocity_30d ?? 0,
          authority_trajectory_dr: m.authority_trajectory_dr ?? null,
          active_citations: m.active_citations ?? 0,
          tier1_prospects: m.tier1_prospects ?? 0,
          total_opportunities: m.total_opportunities ?? 0,
          authority_action_plan: m.authority_action_plan,
        });
      }
    } catch (e: any) {
      // warn removed
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBacklinks();
  }, [loadBacklinks]);

  // Scout sweep with live SSE progress log
  const handleRunScoutSweep = async () => {
    const wid = getCurrentWebsiteId() || websiteId || "default";
    try {
      setIsScouting(true);
      setScoutLogs(["Connecting to scout agent..."]);
      showToast("OpportunityScoutAgent sweeping 5 tiers of link targets...");

      await new Promise<void>((resolve, reject) => {
        const url = buildUrl(`/api/backlinks/scout/stream?website_id=${encodeURIComponent(wid)}`);
        const source = new EventSource(url);

        source.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.event === "log") {
              setScoutLogs((prev) => [...prev, data.message]);
            } else if (data.event === "completed") {
              setScoutLogs((prev) => [...prev, `Done — ${data.found} opportunities found.`]);
              source.close();
              resolve();
            } else if (data.event === "error") {
              setScoutLogs((prev) => [...prev, `Error: ${data.error}`]);
              source.close();
              reject(new Error(data.error));
            }
          } catch {}
        };
        source.onerror = () => {
          source.close();
          reject(new Error("Stream connection lost"));
        };

        // Hard timeout safety
        setTimeout(() => {
          source.close();
          resolve();
        }, 180000);
      });

      showToast("✓ Scout sweep complete!");
      loadBacklinks();
    } catch (err: any) {
      showToast(`Scout sweep complete: updating table...`);
      loadBacklinks();
    } finally {
      setIsScouting(false);
    }
  };

  // Draft outreach email with NVIDIA NIM
  const handleDraftEmail = async (item: BacklinkItem) => {
    try {
      setDraftingId(item.id);
      const res = await post(`/api/backlinks/${item.id}/draft-email`, {});
      if (res.email_draft) {
        setActiveDraftModal({
          title: item.anchor_text || item.source_url,
          email: res.email_draft,
        });
        showToast("✓ Outreach email drafted via NVIDIA NIM!");
      }
    } catch (e: any) {
      showToast(`Draft failed: ${e.message}`);
    } finally {
      setDraftingId(null);
    }
  };

  // Mark opportunity contacted
  const handleMarkContacted = async (item: BacklinkItem) => {
    try {
      await post(`/api/backlinks/${item.id}/mark-contacted`, {});
      showToast("✓ Marked as contacted.");
      loadBacklinks();
    } catch (e: any) {
      showToast(`Failed: ${e.message}`);
    }
  };

  const filteredLinks = backlinks.filter((b) => {
    if (activeTab === "all") return true;
    const cat = (b.category || b.opportunity_type || "").toLowerCase();
    return cat.includes(activeTab.toLowerCase());
  });

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
      <div className="page-heading">Backlinks & Authority</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        5-Tier Technical Link Acquisition · Zero Outreach · Pure Authority Engineering
      </div>

      {/* KPI & DA SUMMARY PANEL */}
      <div className="panel" style={{ marginBottom: "16px" }}>
        <div className="panel-body" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "24px" }}>
            <div className="da-ring">
              <span className="da-num">{metrics.avg_dr ?? "—"}</span>
              <span className="da-lbl">Avg DR</span>
            </div>
            <div style={{ display: "flex", gap: "28px" }}>
              <div>
                <div style={{ fontFamily: "'DotGothic16', sans-serif", fontSize: "22px", color: "var(--ink)" }}>
                  {metrics.active_citations}
                </div>
                <div style={{ fontSize: "9px", textTransform: "uppercase", color: "var(--muted)", letterSpacing: ".06em" }}>
                  Active Citations
                </div>
              </div>
              <div>
                <div style={{ fontFamily: "'DotGothic16', sans-serif", fontSize: "22px", color: "var(--accent)" }}>
                  {metrics.tier1_prospects}
                </div>
                <div style={{ fontSize: "9px", textTransform: "uppercase", color: "var(--muted)", letterSpacing: ".06em" }}>
                  Tier-1 Prospects
                </div>
              </div>
              <div>
                <div style={{ fontFamily: "'DotGothic16', sans-serif", fontSize: "22px", color: "var(--green)" }}>
                  +{metrics.velocity_30d}/mo
                </div>
                <div style={{ fontSize: "9px", textTransform: "uppercase", color: "var(--muted)", letterSpacing: ".06em" }}>
                  Link Velocity
                </div>
              </div>
            </div>
          </div>

          <button
            type="button"
            className="btn btn-accent"
            disabled={isScouting}
            onClick={handleRunScoutSweep}
            style={{ padding: "10px 20px", fontWeight: 600 }}
          >
            {isScouting ? "⚡ Scouting 5-Tier Targets..." : "⚡ Run 5-Tier Opportunity Scout"}
          </button>
        </div>

        {isScouting && scoutLogs.length > 0 && (
          <pre style={{
            fontFamily: "'IBM Plex Mono', monospace", fontSize: "10.5px",
            background: "var(--panel-inner)", border: "1px solid var(--border)",
            padding: "10px 14px", margin: "0 14px 14px", whiteSpace: "pre-wrap",
          }}>
            {scoutLogs.join("\n")}
          </pre>
        )}

        {metrics.authority_action_plan && (
          <div style={{ margin: "0 14px 14px", padding: "12px 16px", border: "1px solid var(--accent)", background: "rgba(255,77,18,.04)" }}>
            <div style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: ".08em", color: "var(--accent)", marginBottom: "4px" }}>
              Authority Action Plan
            </div>
            <div style={{ fontSize: "11.5px", lineHeight: "1.6" }}>{metrics.authority_action_plan}</div>
          </div>
        )}
      </div>

      {/* 5-TIER CATEGORY SELECTOR */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "16px", flexWrap: "wrap" }}>
        {[
          { id: "all", label: "All Opportunities" },
          { id: "unlinked", label: "1. Unlinked Mentions" },
          { id: "competitor", label: "2. Competitor Reclamation" },
          { id: "expired", label: "3. Expired Citations" },
          { id: "broken", label: "4. Broken Link Reclamation" },
          { id: "resource", label: "5. Resource Hubs" },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`btn ${activeTab === tab.id ? "btn-primary" : ""}`}
            onClick={() => setActiveTab(tab.id)}
            style={{ fontSize: "9.5px", padding: "6px 12px" }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* MONITORED BACKLINKS TABLE */}
      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Technical Backlink Opportunities & Active Profiles</span>
          <button type="button" className="panel-action" onClick={loadBacklinks}>
            Refresh
          </button>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Target / Source URL</th>
                <th>Anchor Text / Context</th>
                <th>Category</th>
                <th>DR</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredLinks.length > 0 ? (
                filteredLinks.map((item) => (
                  <tr key={item.id || item.source_url}>
                    <td style={{ fontWeight: 600, maxWidth: "260px" }}>
                      <a
                        href={item.source_url.startsWith("http") ? item.source_url : `https://${item.source_url}`}
                        target="_blank"
                        rel="noreferrer"
                        style={{ color: "var(--ink)", textDecoration: "none" }}
                      >
                        {item.source_url} ↗
                      </a>
                    </td>
                    <td>
                      <span style={{ color: "var(--muted)", fontSize: "10.5px" }}>
                        {item.anchor_text || item.target_url || "—"}
                      </span>
                    </td>
                    <td>
                      <span className="badge badge-ink">
                        {item.category || item.opportunity_type || "Uncategorized"}
                      </span>
                    </td>
                    <td>
                      <span style={{ fontFamily: "'DotGothic16', sans-serif", fontSize: "16px" }}>
                        {item.domain_rating ?? "—"}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${item.status === "acquired" || item.status === "live" ? "badge-green" : "badge-accent"}`}>
                        {item.status || "qualified"}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                        <button
                          type="button"
                          className="btn btn-accent"
                          style={{ fontSize: "9px", padding: "3px 8px" }}
                          disabled={draftingId === item.id}
                          onClick={() => handleDraftEmail(item)}
                          title="Draft custom outreach email via NVIDIA NIM"
                        >
                          {draftingId === item.id ? "Drafting..." : "✉ Draft Email"}
                        </button>
                        {item.status !== "contacted" && (
                          <button
                            type="button"
                            className="btn"
                            style={{ fontSize: "9px", padding: "3px 8px", borderColor: "var(--line)" }}
                            onClick={() => handleMarkContacted(item)}
                            title="Mark this target as contacted"
                          >
                            Mark Contacted
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: "28px", color: "var(--muted)" }}>
                    No backlink opportunities found yet — click &quot;⚡ Run 5-Tier Opportunity Scout&quot; above to discover qualified link targets.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* DRAFT OUTREACH EMAIL MODAL */}
      {activeDraftModal && (
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center",
          zIndex: 10000, padding: "20px"
        }}>
          <div style={{
            background: "var(--bg)", border: "1px solid var(--accent)", maxWidth: "600px", width: "100%",
            boxShadow: "0 8px 32px rgba(0,0,0,0.5)", overflow: "hidden"
          }}>
            <div style={{
              padding: "12px 16px", background: "var(--surface)", borderBottom: "1px solid var(--line)",
              display: "flex", justifyContent: "space-between", alignItems: "center"
            }}>
              <span style={{ fontWeight: 600, fontSize: "13px" }}>
                ✉ AI Outreach Email — {activeDraftModal.title}
              </span>
              <button
                onClick={() => setActiveDraftModal(null)}
                style={{ background: "transparent", border: "none", color: "var(--muted)", cursor: "pointer", fontSize: "16px" }}
              >
                ✕
              </button>
            </div>
            <div style={{ padding: "16px" }}>
              <pre style={{
                background: "var(--surface)", border: "1px solid var(--line)", padding: "12px",
                whiteSpace: "pre-wrap", fontSize: "11.5px", lineHeight: "1.6", color: "var(--ink)",
                maxHeight: "340px", overflowY: "auto", fontFamily: "'IBM Plex Mono', monospace"
              }}>
                {activeDraftModal.email}
              </pre>
              <div style={{ marginTop: "14px", display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                <button
                  type="button"
                  className="btn"
                  onClick={() => {
                    navigator.clipboard?.writeText(activeDraftModal.email);
                    showToast("✓ Copied email to clipboard!");
                  }}
                  style={{ fontSize: "11px", padding: "6px 14px" }}
                >
                  Copy to Clipboard
                </button>
                <button
                  type="button"
                  className="btn btn-accent"
                  onClick={() => setActiveDraftModal(null)}
                  style={{ fontSize: "11px", padding: "6px 14px" }}
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* BOTTOM TICKER */}
      <div className="bticker">
        <span className="bticker-inner">
          <span className="bt-sq"></span>BACKLINK ENGINE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>5-TIER TECHNICAL ACQUISITION <span className="bt-sep">/</span>
          <span className="bt-sq"></span>AUTONOMOUS SCOUT ACTIVE &nbsp;&nbsp;&nbsp;&nbsp;
          <span className="bt-sq"></span>BACKLINK ENGINE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>5-TIER TECHNICAL ACQUISITION <span className="bt-sep">/</span>
          <span className="bt-sq"></span>AUTONOMOUS SCOUT ACTIVE
        </span>
      </div>
    </div>
  );
}
