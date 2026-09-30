"use client";

import { useEffect, useState, useCallback } from "react";
import { get } from "@/lib/api";
import { setCurrentWebsiteId } from "@/lib/website";

interface SiteOverview {
  id: string;
  domain: string;
  site_name: string;
  health_score: number;
  indexation_rate: number;
  indexed_pages: number;
  submitted_pages: number;
  clicks_28d: number;
  impressions_28d: number;
  open_issues_count: number;
  critical_issues: number;
  warning_issues: number;
  last_audit_date: string;
  trend: string;
}

interface NetworkOverviewResponse {
  success: boolean;
  sites: SiteOverview[];
  total_sites: number;
  network_health_avg: number;
  network_indexation_avg: number;
  network_clicks_28d: number;
  total_open_issues: number;
}

interface NetworkOverviewTableProps {
  onSelectSite?: (siteId: string) => void;
  activeWebsiteId?: string;
}

export function NetworkOverviewTable({ onSelectSite, activeWebsiteId }: NetworkOverviewTableProps) {
  const [data, setData] = useState<NetworkOverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [healthFilter, setHealthFilter] = useState<"all" | "healthy" | "warning" | "critical">("all");

  const fetchOverview = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await get("/api/network/overview");
      setData(res);
    } catch (err: any) {
      setError(err?.message || "Failed to load network overview");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  const handleSwitchSite = (siteId: string) => {
    setCurrentWebsiteId(siteId);
    if (onSelectSite) {
      onSelectSite(siteId);
    }
  };

  const filteredSites = (data?.sites || []).filter((s) => {
    const matchesSearch =
      (s.domain || "").toLowerCase().includes(searchTerm.toLowerCase()) ||
      (s.site_name || "").toLowerCase().includes(searchTerm.toLowerCase());

    if (!matchesSearch) return false;

    if (healthFilter === "healthy") return s.health_score >= 80;
    if (healthFilter === "warning") return s.health_score >= 60 && s.health_score < 80;
    if (healthFilter === "critical") return s.health_score < 60;
    return true;
  });

  return (
    <div className="panel" style={{ marginBottom: "24px" }}>
      <div className="panel-head" style={{ flexWrap: "wrap", gap: "10px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontSize: "16px" }}>🌐</span>
          <span className="panel-label" style={{ fontSize: "12px", fontWeight: 700, color: "var(--ink)" }}>
            Multi-Site Network Portfolio
          </span>
          <span className="badge badge-accent">
            {data?.total_sites || 0} Domains Monitored
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button
            onClick={fetchOverview}
            disabled={loading}
            className="btn"
            style={{
              padding: "4px 10px",
              fontSize: "10.5px",
              display: "flex",
              alignItems: "center",
              gap: "4px",
              background: "var(--panel-inner)",
              border: "1px solid var(--border)",
              cursor: "pointer",
            }}
          >
            <span>🔄</span> {loading ? "Refreshing..." : "Refresh Network"}
          </button>
        </div>
      </div>

      <div className="panel-body" style={{ padding: "16px" }}>
        {/* KPI SUMMARY CARDS */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
            gap: "12px",
            marginBottom: "20px",
          }}
        >
          <div
            style={{
              padding: "14px 16px",
              background: "var(--panel-inner)",
              border: "1px solid var(--line)",
              borderRadius: "4px",
            }}
          >
            <div style={{ fontSize: "10px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "6px" }}>
              Network Avg Health
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
              <span style={{ fontFamily: "DotGothic16, monospace", fontSize: "28px", color: "var(--green)" }}>
                {data?.network_health_avg ? Math.round(data.network_health_avg) : "--"}
              </span>
              <span style={{ fontSize: "12px", color: "var(--muted)" }}>/ 100</span>
            </div>
          </div>

          <div
            style={{
              padding: "14px 16px",
              background: "var(--panel-inner)",
              border: "1px solid var(--line)",
              borderRadius: "4px",
            }}
          >
            <div style={{ fontSize: "10px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "6px" }}>
              Indexation Average
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
              <span style={{ fontFamily: "DotGothic16, monospace", fontSize: "28px", color: (data?.network_indexation_avg || 0) >= 80 ? "var(--green)" : "var(--amber)" }}>
                {data?.network_indexation_avg ? Number(data.network_indexation_avg).toFixed(1) : "--"}%
              </span>
              <span style={{ fontSize: "11px", color: "var(--muted)" }}>gate: 80%</span>
            </div>
          </div>

          <div
            style={{
              padding: "14px 16px",
              background: "var(--panel-inner)",
              border: "1px solid var(--line)",
              borderRadius: "4px",
            }}
          >
            <div style={{ fontSize: "10px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "6px" }}>
              28-Day Clicks (Total)
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
              <span style={{ fontFamily: "DotGothic16, monospace", fontSize: "28px", color: "var(--ink)" }}>
                {data?.network_clicks_28d ? data.network_clicks_28d.toLocaleString() : "0"}
              </span>
              <span style={{ fontSize: "11px", color: "var(--green)" }}>↑ GSC Total</span>
            </div>
          </div>

          <div
            style={{
              padding: "14px 16px",
              background: "var(--panel-inner)",
              border: "1px solid var(--line)",
              borderRadius: "4px",
            }}
          >
            <div style={{ fontSize: "10px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "6px" }}>
              Open SEO Issues
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
              <span style={{ fontFamily: "DotGothic16, monospace", fontSize: "28px", color: (data?.total_open_issues || 0) > 0 ? "var(--red)" : "var(--green)" }}>
                {data?.total_open_issues ?? 0}
              </span>
              <span style={{ fontSize: "11px", color: "var(--muted)" }}>Across sites</span>
            </div>
          </div>
        </div>

        {/* SEARCH AND FILTERS */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "10px",
            marginBottom: "14px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flex: 1, minWidth: "260px" }}>
            <input
              type="text"
              placeholder="Search by domain or site name..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                width: "100%",
                maxWidth: "340px",
                padding: "8px 12px",
                fontSize: "12px",
                background: "var(--panel-inner)",
                border: "1px solid var(--border)",
                color: "var(--ink)",
                fontFamily: "'IBM Plex Mono', monospace",
                outline: "none",
              }}
            />
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11px" }}>
            <span style={{ color: "var(--muted)", marginRight: "4px" }}>Filter:</span>
            {(["all", "healthy", "warning", "critical"] as const).map((filter) => (
              <button
                key={filter}
                onClick={() => setHealthFilter(filter)}
                style={{
                  padding: "5px 10px",
                  fontSize: "10.5px",
                  textTransform: "uppercase",
                  background: healthFilter === filter ? "var(--accent)" : "var(--panel-inner)",
                  color: healthFilter === filter ? "#fff" : "var(--ink)",
                  border: `1px solid ${healthFilter === filter ? "var(--accent)" : "var(--line)"}`,
                  cursor: "pointer",
                }}
              >
                {filter}
              </button>
            ))}
          </div>
        </div>

        {/* ERROR STATE */}
        {error && (
          <div
            style={{
              padding: "12px",
              background: "rgba(239, 68, 68, 0.1)",
              border: "1px solid var(--red)",
              color: "var(--red)",
              fontSize: "12px",
              marginBottom: "14px",
            }}
          >
            ⚠️ {error}
          </div>
        )}

        {/* TABLE */}
        <div style={{ overflowX: "auto", border: "1px solid var(--border)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "11.5px", textAlign: "left" }}>
            <thead>
              <tr style={{ background: "var(--table-head)", borderBottom: "1px solid var(--border)" }}>
                <th style={{ padding: "10px 14px", fontWeight: 700, color: "var(--ink)" }}>Site / Domain</th>
                <th style={{ padding: "10px 14px", fontWeight: 700, color: "var(--ink)" }}>Health</th>
                <th style={{ padding: "10px 14px", fontWeight: 700, color: "var(--ink)" }}>Indexation</th>
                <th style={{ padding: "10px 14px", fontWeight: 700, color: "var(--ink)" }}>28d Clicks</th>
                <th style={{ padding: "10px 14px", fontWeight: 700, color: "var(--ink)" }}>Issues</th>
                <th style={{ padding: "10px 14px", fontWeight: 700, color: "var(--ink)" }}>Last Audit</th>
                <th style={{ padding: "10px 14px", textAlign: "right", fontWeight: 700, color: "var(--ink)" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {loading && (!data?.sites || data.sites.length === 0) ? (
                <tr>
                  <td colSpan={7} style={{ padding: "32px", textAlign: "center", color: "var(--muted)" }}>
                    Loading network sites...
                  </td>
                </tr>
              ) : filteredSites.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: "32px", textAlign: "center", color: "var(--muted)" }}>
                    No websites match your filter criteria.
                  </td>
                </tr>
              ) : (
                filteredSites.map((site) => {
                  const isCurrent = site.id === activeWebsiteId;
                  const healthColor =
                    site.health_score >= 80 ? "var(--green)" : site.health_score >= 60 ? "var(--amber)" : "var(--red)";

                  return (
                    <tr
                      key={site.id}
                      style={{
                        borderBottom: "1px solid var(--line)",
                        background: isCurrent ? "rgba(255, 90, 31, 0.05)" : "transparent",
                        transition: "background 0.15s ease",
                      }}
                    >
                      <td style={{ padding: "12px 14px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <span
                            style={{
                              width: "8px",
                              height: "8px",
                              borderRadius: "50%",
                              background: isCurrent ? "var(--accent)" : healthColor,
                              display: "inline-block",
                            }}
                          />
                          <div>
                            <div style={{ fontWeight: 700, color: "var(--ink)" }}>
                              {site.site_name || site.domain}
                            </div>
                            <div style={{ fontSize: "10px", color: "var(--muted)" }}>
                              {site.domain}
                              {isCurrent && (
                                <span
                                  style={{
                                    marginLeft: "6px",
                                    padding: "1px 4px",
                                    background: "var(--accent)",
                                    color: "#fff",
                                    fontSize: "8.5px",
                                    borderRadius: "2px",
                                  }}
                                >
                                  Active
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>

                      <td style={{ padding: "12px 14px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <span
                            style={{
                              fontWeight: 700,
                              color: healthColor,
                              fontFamily: "DotGothic16, monospace",
                              fontSize: "14px",
                            }}
                          >
                            {site.health_score}
                          </span>
                          <span style={{ fontSize: "9.5px", color: "var(--muted)" }}>/100</span>
                        </div>
                      </td>

                      <td style={{ padding: "12px 14px" }}>
                        <div>
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px", fontSize: "10.5px" }}>
                            <span>{Number(site.indexation_rate ?? 0).toFixed(1)}%</span>
                            <span style={{ color: "var(--muted)" }}>
                              {site.indexed_pages}/{site.submitted_pages}
                            </span>
                          </div>
                          <div
                            style={{
                              width: "110px",
                              height: "4px",
                              background: "var(--line)",
                              borderRadius: "2px",
                              overflow: "hidden",
                            }}
                          >
                            <div
                              style={{
                                width: `${Math.min(100, Math.max(0, site.indexation_rate))}%`,
                                height: "100%",
                                background: site.indexation_rate >= 80 ? "var(--green)" : "var(--amber)",
                              }}
                            />
                          </div>
                        </div>
                      </td>

                      <td style={{ padding: "12px 14px" }}>
                        <div style={{ fontWeight: 600 }}>{Number(site.clicks_28d ?? 0).toLocaleString()}</div>
                        <div style={{ fontSize: "9.5px", color: "var(--muted)" }}>
                          {Number(site.impressions_28d ?? 0).toLocaleString()} imp
                        </div>
                      </td>

                      <td style={{ padding: "12px 14px" }}>
                        <div style={{ display: "flex", gap: "6px" }}>
                          {site.critical_issues > 0 ? (
                            <span
                              style={{
                                padding: "2px 6px",
                                background: "rgba(239, 68, 68, 0.15)",
                                color: "var(--red)",
                                fontSize: "10px",
                                fontWeight: 700,
                                borderRadius: "2px",
                              }}
                            >
                              {site.critical_issues} Crit
                            </span>
                          ) : (
                            <span style={{ fontSize: "10px", color: "var(--green)" }}>0 Crit</span>
                          )}
                          {site.warning_issues > 0 && (
                            <span
                              style={{
                                padding: "2px 6px",
                                background: "rgba(245, 158, 11, 0.15)",
                                color: "var(--amber)",
                                fontSize: "10px",
                                borderRadius: "2px",
                              }}
                            >
                              {site.warning_issues} Warn
                            </span>
                          )}
                        </div>
                      </td>

                      <td style={{ padding: "12px 14px", color: "var(--muted)", fontSize: "10.5px" }}>
                        {site.last_audit_date ? site.last_audit_date.split("T")[0] : "Pending"}
                      </td>

                      <td style={{ padding: "12px 14px", textAlign: "right" }}>
                        <button
                          onClick={() => handleSwitchSite(site.id)}
                          className="btn"
                          style={{
                            padding: "5px 12px",
                            fontSize: "11px",
                            background: isCurrent ? "var(--accent)" : "var(--panel-inner)",
                            color: isCurrent ? "#fff" : "var(--ink)",
                            border: `1px solid ${isCurrent ? "var(--accent)" : "var(--border)"}`,
                            cursor: "pointer",
                            fontWeight: 600,
                          }}
                        >
                          {isCurrent ? "Selected" : "Switch Site →"}
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
