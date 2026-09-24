"use client";

/**
 * Multi-site portfolio: one table of every site with health, indexation,
 * clicks and open issues. A network cannot be managed one site at a time.
 *
 * Sites with no collected metrics render as "no data" instead of 0, so an
 * unconnected source never looks like a genuine zero.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Portfolio,
  PortfolioSite,
  fetchPortfolio,
  fmtNum,
  fmtPct,
} from "@/lib/intelligence";

function healthColor(score: number | null): string {
  if (score === null) return "var(--muted)";
  if (score >= 80) return "var(--green)";
  if (score >= 60) return "var(--amber)";
  return "var(--red)";
}

function HealthCell({ site }: { site: PortfolioSite }) {
  if (site.health_score === null) {
    return <span style={{ color: "var(--muted)", fontSize: "10.5px" }}>no data</span>;
  }
  const color = healthColor(site.health_score);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <span style={{ fontWeight: 700, color, fontSize: "13px", minWidth: "26px" }}>
        {site.health_score}
      </span>
      <div
        style={{
          flex: 1,
          height: "4px",
          background: "var(--line)",
          borderRadius: "2px",
          overflow: "hidden",
          minWidth: "40px",
        }}
        title={site.health_formula}
      >
        <div
          style={{
            width: `${site.health_score}%`,
            height: "100%",
            background: color,
          }}
        />
      </div>
    </div>
  );
}

export function PortfolioTable() {
  const [data, setData] = useState<Portfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setData(await fetchPortfolio());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load portfolio");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const sites = data?.sites ?? [];

  return (
    <>
      {data && (
        <div className="stat-strip">
          <div className="stat-cell">
            <div className="stat-label">Sites</div>
            <div className="stat-val">{data.totals.sites}</div>
            <div className="stat-sub">in portfolio</div>
          </div>
          <div className="stat-cell">
            <div className="stat-label">Clicks</div>
            <div className="stat-val">
              {data.totals.clicks === null ? "—" : fmtNum(data.totals.clicks)}
            </div>
            <div className="stat-sub">
              {data.totals.clicks === null ? "not connected" : "last 28 days"}
            </div>
          </div>
          <div className="stat-cell">
            <div className="stat-label">Open Issues</div>
            <div className="stat-val">{fmtNum(data.totals.open_issues)}</div>
            <div className="stat-sub">across all sites</div>
          </div>
          <div className="stat-cell">
            <div className="stat-label">Critical</div>
            <div
              className="stat-val"
              style={{
                color:
                  data.totals.critical_issues > 0 ? "var(--red)" : "var(--green)",
              }}
            >
              {fmtNum(data.totals.critical_issues)}
            </div>
            <div className="stat-sub">needs attention</div>
          </div>
        </div>
      )}

      {data && !data.data_available && (
        <div
          className="panel"
          style={{ padding: "12px 16px", borderColor: "var(--amber)" }}
        >
          <div style={{ fontSize: "11.5px", color: "var(--ink)", lineHeight: 1.5 }}>
            <strong>Metrics not connected.</strong> {data.note} Health, indexation
            and clicks stay blank until Google Search Console is connected.
            Storage backend: <code>{data.storage}</code>.
          </div>
        </div>
      )}

      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">All Sites</span>
          <button className="panel-action" onClick={load} disabled={loading}>
            {loading ? "Loading" : "Refresh"}
          </button>
        </div>
        <div className="panel-body" style={{ padding: 0 }}>
          {error && (
            <div style={{ padding: "16px", fontSize: "11.5px", color: "var(--red)" }}>
              {error}
            </div>
          )}

          {!error && !loading && sites.length === 0 && (
            <div
              style={{
                padding: "32px 16px",
                textAlign: "center",
                fontSize: "11.5px",
                color: "var(--muted)",
              }}
            >
              No websites in the portfolio yet.{" "}
              <Link href="/onboarding" style={{ color: "var(--accent)" }}>
                Add your first site
              </Link>
              .
            </div>
          )}

          {sites.length > 0 && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Site</th>
                  <th style={{ width: "130px" }}>Health</th>
                  <th style={{ width: "130px" }}>Indexation</th>
                  <th style={{ width: "90px" }}>Clicks</th>
                  <th style={{ width: "90px" }}>Avg pos</th>
                  <th style={{ width: "90px" }}>Open issues</th>
                  <th style={{ width: "80px" }} />
                </tr>
              </thead>
              <tbody>
                {sites.map((s) => (
                  <tr key={s.website_id}>
                    <td>
                      <div
                        style={{
                          fontWeight: 600,
                          fontSize: "11.5px",
                          color: "var(--ink)",
                        }}
                      >
                        {s.domain}
                      </div>
                      <div
                        style={{
                          fontSize: "9.5px",
                          color: "var(--muted)",
                        }}
                      >
                        {s.status}
                        {s.metrics_as_of ? ` · as of ${s.metrics_as_of}` : ""}
                      </div>
                    </td>
                    <td>
                      <HealthCell site={s} />
                    </td>
                    <td>
                      {s.indexed_pages === null ? (
                        <span
                          style={{ color: "var(--muted)", fontSize: "10.5px" }}
                        >
                          no data
                        </span>
                      ) : (
                        <div>
                          <div style={{ fontSize: "12px", fontWeight: 600 }}>
                            {fmtNum(s.indexed_pages)} indexed
                          </div>
                          <div style={{ fontSize: "9.5px", color: "var(--muted)" }}>
                            {fmtNum(s.excluded_pages, "0")} excluded ·{" "}
                            {fmtNum(s.errors, "0")} errors
                          </div>
                        </div>
                      )}
                    </td>
                    <td style={{ fontWeight: 600 }}>
                      {s.clicks === null ? "—" : fmtNum(s.clicks)}
                    </td>
                    <td>
                      {s.avg_position === null
                        ? "—"
                        : s.avg_position.toFixed(1)}
                    </td>
                    <td>
                      <span
                        className={`badge ${
                          s.critical_issues > 0
                            ? "badge-red"
                            : s.open_issues > 0
                            ? "badge-amber"
                            : "badge-green"
                        }`}
                      >
                        {s.open_issues}
                      </span>
                      {s.critical_issues > 0 && (
                        <div
                          style={{
                            fontSize: "9px",
                            color: "var(--red)",
                            marginTop: "2px",
                          }}
                        >
                          {s.critical_issues} critical
                        </div>
                      )}
                    </td>
                    <td>
                      <Link
                        href="/actions"
                        className="panel-action"
                        style={{ textDecoration: "none", display: "inline-block" }}
                      >
                        Actions
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {data && (
        <div className="panel" style={{ padding: "14px 16px" }}>
          <div
            style={{
              fontSize: "10px",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              color: "var(--muted)",
              marginBottom: "8px",
            }}
          >
            Data sources
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
              gap: "8px",
            }}
          >
            {Object.values(data.integrations).map((i) => (
              <div
                key={i.name}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  fontSize: "10.5px",
                }}
              >
                <span
                  className="status-dot"
                  style={{
                    background:
                      i.status === "ok" ? "var(--green)" : "var(--muted)",
                  }}
                />
                <span style={{ fontWeight: 600, textTransform: "uppercase" }}>
                  {i.name}
                </span>
                <span style={{ color: "var(--muted)" }}>
                  {i.status === "ok" ? "connected" : "not connected"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}