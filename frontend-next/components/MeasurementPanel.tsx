"use client";

/**
 * Prove the work: after a fix ships, track that URL for 28 days and show the
 * position/traffic lift. This is what turns the tool into ROI evidence.
 *
 * Lift is control-adjusted where a control set exists, so seasonality is not
 * reported as a win. The UI shows raw and adjusted side by side.
 */

import { useCallback, useEffect, useState } from "react";
import {
  MeasurementReport,
  fetchMeasurementReport,
  fetchSiteWindows,
  fmtNum,
} from "@/lib/intelligence";

interface Props {
  websiteId: string;
}

interface WindowRow {
  id: string;
  target_url: string;
  keyword?: string | null;
  window_start: string;
  status: string;
}

function LiftStat({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="stat-cell">
      <div className="stat-label">{label}</div>
      <div className="stat-val" style={{ color: color || "var(--ink)" }}>
        {value}
      </div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

function MiniSeries({ report }: { report: MeasurementReport }) {
  const series = report.series ?? [];
  if (series.length < 2) return null;
  const max = Math.max(...series.map((p) => p.clicks ?? 0), 1);
  return (
    <div style={{ marginTop: "10px" }}>
      <div
        style={{
          fontSize: "9.5px",
          textTransform: "uppercase",
          color: "var(--muted)",
          marginBottom: "6px",
        }}
      >
        Clicks by day offset
      </div>
      <div style={{ display: "flex", alignItems: "flex-end", gap: "10px", height: "70px" }}>
        {series.map((p) => {
          const h = ((p.clicks ?? 0) / max) * 60;
          return (
            <div key={p.day} style={{ flex: 1, textAlign: "center" }}>
              <div
                style={{
                  height: `${h}px`,
                  background: "var(--accent)",
                  borderRadius: "2px 2px 0 0",
                  minHeight: "2px",
                }}
                title={`${p.clicks} clicks`}
              />
              <div style={{ fontSize: "9px", color: "var(--muted)", marginTop: "4px" }}>
                day {p.day}
              </div>
              <div style={{ fontSize: "9.5px", fontWeight: 600 }}>
                {fmtNum(p.clicks, "0")}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function MeasurementPanel({ websiteId }: Props) {
  const [windows, setWindows] = useState<WindowRow[]>([]);
  const [report, setReport] = useState<MeasurementReport | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadWindows = useCallback(async () => {
    if (!websiteId) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const res = await fetchSiteWindows(websiteId);
      setWindows(res.windows || []);
      if (res.windows?.length && !selected) {
        setSelected(res.windows[0].id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load measurement windows");
      setWindows([]);
    } finally {
      setLoading(false);
    }
  }, [websiteId, selected]);

  useEffect(() => {
    loadWindows();
  }, [loadWindows]);

  useEffect(() => {
    if (!selected) return;
    (async () => {
      try {
        setReport(await fetchMeasurementReport(selected));
      } catch {
        setReport(null);
      }
    })();
  }, [selected]);

  return (
    <>
      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">
            Shipped Fixes Under Measurement
            {windows.length > 0 && (
              <span className="badge badge-muted" style={{ marginLeft: "8px" }}>
                {windows.length}
              </span>
            )}
          </span>
          <button className="panel-action" onClick={loadWindows} disabled={loading}>
            {loading ? "Loading" : "Refresh"}
          </button>
        </div>
        <div className="panel-body" style={{ padding: 0 }}>
          {error && (
            <div style={{ padding: "16px", fontSize: "11.5px", color: "var(--red)" }}>
              {error}
            </div>
          )}
          {!error && !loading && windows.length === 0 && (
            <div
              style={{
                padding: "28px 16px",
                textAlign: "center",
                fontSize: "11.5px",
                color: "var(--muted)",
                lineHeight: 1.6,
              }}
            >
              No fixes under measurement yet.
              <br />A 28-day window opens automatically when a change is applied
              in Guardrails.
            </div>
          )}
          {windows.length > 0 && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>URL</th>
                  <th style={{ width: "150px" }}>Keyword</th>
                  <th style={{ width: "110px" }}>Started</th>
                  <th style={{ width: "110px" }}>Status</th>
                  <th style={{ width: "70px" }} />
                </tr>
              </thead>
              <tbody>
                {windows.map((w) => (
                  <tr
                    key={w.id}
                    onClick={() => setSelected(w.id)}
                    style={{
                      cursor: "pointer",
                      background: selected === w.id ? "var(--bg3)" : undefined,
                    }}
                  >
                    <td style={{ fontWeight: 600, fontSize: "11px" }}>{w.target_url}</td>
                    <td style={{ fontSize: "10.5px" }}>{w.keyword || "—"}</td>
                    <td style={{ fontSize: "10px", color: "var(--muted)" }}>
                      {w.window_start}
                    </td>
                    <td>
                      <span
                        className={`badge ${
                          w.status === "complete" ? "badge-green" : "badge-amber"
                        }`}
                      >
                        {w.status}
                      </span>
                    </td>
                    <td>
                      <button className="panel-action">View</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {report && report.ok && (
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">
              28-Day Lift · {report.window.target_url}
            </span>
            <span className="badge badge-muted">{report.status}</span>
          </div>
          <div className="panel-body">
            {report.status === "awaiting_data" ? (
              <div style={{ fontSize: "11.5px", color: "var(--muted)", lineHeight: 1.6 }}>
                {report.note}
                <br />
                Snapshots are expected at day{" "}
                {(report.note && "0, 7, 14 and 28") || ""}.
              </div>
            ) : (
              <>
                <div
                  className="stat-strip"
                  style={{ gridTemplateColumns: "repeat(4, 1fr)", marginBottom: "14px" }}
                >
                  <LiftStat
                    label="Adjusted lift"
                    value={`${(report.lift?.adjusted_clicks_lift ?? 0) > 0 ? "+" : ""}${fmtNum(
                      report.lift?.adjusted_clicks_lift,
                      "0"
                    )}`}
                    sub="clicks, control-adjusted"
                    color={
                      (report.lift?.adjusted_clicks_lift ?? 0) > 0
                        ? "var(--green)"
                        : "var(--red)"
                    }
                  />
                  <LiftStat
                    label="Percent lift"
                    value={
                      report.lift?.percent_lift === null ||
                      report.lift?.percent_lift === undefined
                        ? "—"
                        : `${report.lift.percent_lift > 0 ? "+" : ""}${report.lift.percent_lift}%`
                    }
                    sub="vs baseline"
                  />
                  <LiftStat
                    label="Position"
                    value={
                      report.lift?.position_improvement === null ||
                      report.lift?.position_improvement === undefined
                        ? "—"
                        : `${report.lift.position_improvement > 0 ? "↑" : "↓"} ${Math.abs(
                            report.lift.position_improvement
                          )}`
                    }
                    sub={
                      report.lift?.position_baseline !== null &&
                      report.lift?.position_current !== null
                        ? `${report.lift?.position_baseline} → ${report.lift?.position_current}`
                        : undefined
                    }
                    color={
                      (report.lift?.position_improvement ?? 0) > 0
                        ? "var(--green)"
                        : undefined
                    }
                  />
                  <LiftStat
                    label="Days"
                    value={`${report.days_elapsed ?? 0}/28`}
                    sub={`${report.days_remaining ?? 0} remaining`}
                  />
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                    gap: "10px",
                    fontSize: "10.5px",
                    marginBottom: "8px",
                  }}
                >
                  <div>
                    <span style={{ color: "var(--muted)" }}>Baseline: </span>
                    {fmtNum(report.lift?.baseline_clicks, "0")} clicks
                  </div>
                  <div>
                    <span style={{ color: "var(--muted)" }}>Now: </span>
                    {fmtNum(report.lift?.current_clicks, "0")} clicks
                  </div>
                  <div>
                    <span style={{ color: "var(--muted)" }}>Raw lift: </span>
                    {fmtNum(report.lift?.raw_clicks_lift, "0")}
                  </div>
                  <div>
                    <span style={{ color: "var(--muted)" }}>Control adjustment: </span>
                    {fmtNum(report.lift?.control_adjustment, "0")}
                  </div>
                </div>

                <MiniSeries report={report} />

                {report.control_note && (
                  <div
                    style={{
                      marginTop: "12px",
                      padding: "9px 12px",
                      background: "var(--surface)",
                      borderLeft: "3px solid var(--accent)",
                      fontSize: "10.5px",
                      color: "var(--ink)",
                      lineHeight: 1.5,
                    }}
                  >
                    {report.control_note}
                  </div>
                )}
                {report.method && (
                  <div style={{ marginTop: "8px", fontSize: "10px", color: "var(--muted)" }}>
                    {report.method}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}