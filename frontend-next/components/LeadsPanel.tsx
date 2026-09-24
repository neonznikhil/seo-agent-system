"use client";

/**
 * Leads view: connect conversion data and show cost per lead by keyword.
 *
 * Clicks and positions mean nothing for lead-gen. Because GA4 cannot expose the
 * organic query behind a conversion, keywords are mapped to landing pages and
 * joined to conversions there. The attribution method and its confidence are
 * shown on every row, and the cost basis is labelled (organic has no ad spend).
 */

import { useCallback, useEffect, useState } from "react";
import {
  CplReport,
  addConversion,
  addEffortCost,
  computeCpl,
  fmtMoney,
  fmtNum,
  fmtPct,
} from "@/lib/intelligence";

interface Props {
  websiteId: string;
  defaultHourlyRate?: number;
}

interface PairRow {
  keyword: string;
  landingPage: string;
  clicks: string;
  pageSessions: string;
  attributedSessions: string;
}

function defaultPeriod() {
  const end = new Date();
  const start = new Date(end.getTime() - 29 * 24 * 3600 * 1000);
  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10),
  };
}

export function LeadsPanel({ websiteId, defaultHourlyRate = 60 }: Props) {
  const period = defaultPeriod();
  const [start, setStart] = useState(period.start);
  const [end, setEnd] = useState(period.end);
  const [hourlyRate, setHourlyRate] = useState(String(defaultHourlyRate));
  const [rows, setRows] = useState<PairRow[]>([
    { keyword: "", landingPage: "", clicks: "", pageSessions: "", attributedSessions: "" },
  ]);
  const [report, setReport] = useState<CplReport | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // manual data entry
  const [cPage, setCPage] = useState("");
  const [cDate, setCDate] = useState(period.end);
  const [cCount, setCCount] = useState("");
  const [cValue, setCValue] = useState("");
  const [costDate, setCostDate] = useState(period.end);
  const [costMinutes, setCostMinutes] = useState("");
  const [costRate, setCostRate] = useState(String(defaultHourlyRate));

  const flash = (m: string) => {
    setNotice(m);
    setTimeout(() => setNotice(null), 4500);
  };

  const updateRow = (i: number, patch: Partial<PairRow>) => {
    const next = [...rows];
    next[i] = { ...next[i], ...patch };
    setRows(next);
  };

  const runCpl = useCallback(async () => {
    if (!websiteId) return;
    const pairs = rows
      .filter((r) => r.keyword.trim() && r.landingPage.trim())
      .map((r) => ({
        keyword: r.keyword.trim(),
        landing_page: r.landingPage.trim(),
        clicks: Number(r.clicks || 0),
        page_sessions: r.pageSessions ? Number(r.pageSessions) : undefined,
        attributed_sessions: r.attributedSessions
          ? Number(r.attributedSessions)
          : undefined,
      }));
    if (pairs.length === 0) {
      flash("Add at least one keyword and landing page.");
      return;
    }
    try {
      setBusy("cpl");
      setReport(
        await computeCpl(websiteId, {
          period_start: start,
          period_end: end,
          hourly_rate: Number(hourlyRate || 0),
          keyword_page_pairs: pairs,
        })
      );
    } catch (e) {
      flash(e instanceof Error ? e.message : "Failed to compute cost per lead");
    } finally {
      setBusy(null);
    }
  }, [websiteId, rows, start, end, hourlyRate]);

  const saveConversion = async () => {
    if (!websiteId || !cPage || !cCount) {
      flash("Landing page and conversion count are required.");
      return;
    }
    try {
      setBusy("conv");
      await addConversion(websiteId, {
        conversion_date: cDate,
        landing_page: cPage,
        conversion_count: Number(cCount),
        conversion_value: Number(cValue || 0),
      });
      flash("Conversion imported. Recompute to refresh cost per lead.");
      setCPage("");
      setCCount("");
      setCValue("");
    } catch (e) {
      flash(e instanceof Error ? e.message : "Failed to import conversion");
    } finally {
      setBusy(null);
    }
  };

  const saveCost = async () => {
    if (!websiteId || !costMinutes) {
      flash("Minutes are required to record effort cost.");
      return;
    }
    try {
      setBusy("cost");
      await addEffortCost(websiteId, {
        cost_date: costDate,
        category: "seo_work",
        minutes: Number(costMinutes),
        hourly_rate: Number(costRate || 0),
      });
      flash("Effort cost recorded. Recompute to refresh cost per lead.");
      setCostMinutes("");
    } catch (e) {
      flash(e instanceof Error ? e.message : "Failed to record effort cost");
    } finally {
      setBusy(null);
    }
  };

  const results = report?.results ?? [];

  return (
    <>
      {notice && (
        <div
          className="panel"
          style={{ padding: "10px 14px", borderColor: "var(--accent)", fontSize: "11.5px" }}
        >
          {notice}
        </div>
      )}

      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Import Conversion & Cost Data</span>
          <span style={{ fontSize: "10px", color: "var(--muted)" }}>
            Cost per lead needs both leads and the effort spent producing them
          </span>
        </div>
        <div className="panel-body">
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "10px",
              marginBottom: "14px",
            }}
          >
            <div>
              <label style={labelStyle}>Landing page</label>
              <input
                className="chat-input"
                style={{ width: "100%" }}
                placeholder="/pricing"
                value={cPage}
                onChange={(e) => setCPage(e.target.value)}
              />
            </div>
            <div>
              <label style={labelStyle}>Date</label>
              <input
                className="chat-input"
                style={{ width: "100%" }}
                type="date"
                value={cDate}
                onChange={(e) => setCDate(e.target.value)}
              />
            </div>
            <div>
              <label style={labelStyle}>Conversions</label>
              <input
                className="chat-input"
                style={{ width: "100%" }}
                placeholder="12"
                value={cCount}
                onChange={(e) => setCCount(e.target.value.replace(/[^\d]/g, ""))}
              />
            </div>
            <div>
              <label style={labelStyle}>Value ($)</label>
              <input
                className="chat-input"
                style={{ width: "100%" }}
                placeholder="2400"
                value={cValue}
                onChange={(e) => setCValue(e.target.value.replace(/[^\d.]/g, ""))}
              />
            </div>
            <div style={{ display: "flex", alignItems: "flex-end" }}>
              <button
                className="btn"
                onClick={saveConversion}
                disabled={busy === "conv"}
                style={{ width: "100%" }}
              >
                {busy === "conv" ? "Saving..." : "Import conversion"}
              </button>
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "10px",
            }}
          >
            <div>
              <label style={labelStyle}>Cost date</label>
              <input
                className="chat-input"
                style={{ width: "100%" }}
                type="date"
                value={costDate}
                onChange={(e) => setCostDate(e.target.value)}
              />
            </div>
            <div>
              <label style={labelStyle}>Effort minutes</label>
              <input
                className="chat-input"
                style={{ width: "100%" }}
                placeholder="600"
                value={costMinutes}
                onChange={(e) => setCostMinutes(e.target.value.replace(/[^\d.]/g, ""))}
              />
            </div>
            <div>
              <label style={labelStyle}>Hourly rate ($)</label>
              <input
                className="chat-input"
                style={{ width: "100%" }}
                value={costRate}
                onChange={(e) => setCostRate(e.target.value.replace(/[^\d.]/g, ""))}
              />
            </div>
            <div style={{ display: "flex", alignItems: "flex-end" }}>
              <button
                className="btn"
                onClick={saveCost}
                disabled={busy === "cost"}
                style={{ width: "100%" }}
              >
                {busy === "cost" ? "Saving..." : "Record effort cost"}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Cost Per Lead by Keyword</span>
        </div>
        <div className="panel-body">
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
              gap: "10px",
              marginBottom: "12px",
            }}
          >
            <div>
              <label style={labelStyle}>Period start</label>
              <input
                className="chat-input"
                style={{ width: "100%" }}
                type="date"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </div>
            <div>
              <label style={labelStyle}>Period end</label>
              <input
                className="chat-input"
                style={{ width: "100%" }}
                type="date"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </div>
            <div>
              <label style={labelStyle}>Hourly rate ($)</label>
              <input
                className="chat-input"
                style={{ width: "100%" }}
                value={hourlyRate}
                onChange={(e) => setHourlyRate(e.target.value.replace(/[^\d.]/g, ""))}
              />
            </div>
          </div>

          <table className="data-table" style={{ marginBottom: "10px" }}>
            <thead>
              <tr>
                <th>Keyword</th>
                <th>Landing page</th>
                <th style={{ width: "80px" }}>Clicks</th>
                <th style={{ width: "90px" }}>Page sessions</th>
                <th style={{ width: "100px" }}>Attributed</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td>
                    <input
                      className="chat-input"
                      style={{ width: "100%" }}
                      placeholder="seo tool"
                      value={r.keyword}
                      onChange={(e) => updateRow(i, { keyword: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="chat-input"
                      style={{ width: "100%" }}
                      placeholder="/pricing"
                      value={r.landingPage}
                      onChange={(e) => updateRow(i, { landingPage: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="chat-input"
                      style={{ width: "100%" }}
                      value={r.clicks}
                      onChange={(e) =>
                        updateRow(i, { clicks: e.target.value.replace(/[^\d]/g, "") })
                      }
                    />
                  </td>
                  <td>
                    <input
                      className="chat-input"
                      style={{ width: "100%" }}
                      value={r.pageSessions}
                      onChange={(e) =>
                        updateRow(i, {
                          pageSessions: e.target.value.replace(/[^\d]/g, ""),
                        })
                      }
                    />
                  </td>
                  <td>
                    <input
                      className="chat-input"
                      style={{ width: "100%" }}
                      value={r.attributedSessions}
                      onChange={(e) =>
                        updateRow(i, {
                          attributedSessions: e.target.value.replace(/[^\d]/g, ""),
                        })
                      }
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div style={{ display: "flex", gap: "8px" }}>
            <button
              className="btn"
              onClick={() =>
                setRows([
                  ...rows,
                  {
                    keyword: "",
                    landingPage: "",
                    clicks: "",
                    pageSessions: "",
                    attributedSessions: "",
                  },
                ])
              }
            >
              + Add keyword
            </button>
            <button
              className="btn btn-primary"
              onClick={runCpl}
              disabled={busy === "cpl"}
            >
              {busy === "cpl" ? "Computing..." : "Compute cost per lead"}
            </button>
          </div>
        </div>
      </div>

      {report && (
        <>
          {!report.has_data && (
            <div
              className="panel"
              style={{ padding: "12px 16px", borderColor: "var(--amber)" }}
            >
              <div style={{ fontSize: "11.5px" }}>{report.data_note}</div>
            </div>
          )}

          {results.length > 0 && (
            <div className="panel">
              <div className="panel-head">
                <span className="panel-label">
                  Results · {report.period.start} to {report.period.end}
                </span>
                <span style={{ fontSize: "10px", color: "var(--muted)" }}>
                  {fmtNum(report.total_leads)} leads · {fmtMoney(report.total_cost)}{" "}
                  effort
                </span>
              </div>
              <div className="panel-body" style={{ padding: 0 }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Keyword</th>
                      <th>Landing page</th>
                      <th style={{ width: "70px" }}>Clicks</th>
                      <th style={{ width: "70px" }}>Leads</th>
                      <th style={{ width: "80px" }}>Conv rate</th>
                      <th style={{ width: "100px" }}>Cost / lead</th>
                      <th style={{ width: "100px" }}>Confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((r, i) => (
                      <tr key={i}>
                        <td style={{ fontWeight: 600 }}>{r.keyword}</td>
                        <td style={{ fontFamily: "monospace", fontSize: "10px" }}>
                          {r.landing_page}
                        </td>
                        <td>{fmtNum(r.clicks)}</td>
                        <td style={{ fontWeight: 600 }}>{fmtNum(r.leads)}</td>
                        <td>
                          {r.conversion_rate === null
                            ? "—"
                            : fmtPct(r.conversion_rate, 2)}
                        </td>
                        <td
                          style={{
                            fontWeight: 700,
                            color:
                              r.cost_per_lead === null ? "var(--muted)" : "var(--ink)",
                          }}
                        >
                          {fmtMoney(r.cost_per_lead)}
                        </td>
                        <td>
                          <span
                            className={`badge ${
                              r.attribution_confidence >= 0.6
                                ? "badge-green"
                                : r.attribution_confidence >= 0.3
                                ? "badge-amber"
                                : "badge-red"
                            }`}
                          >
                            {fmtPct(r.attribution_confidence, 0)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="panel" style={{ padding: "12px 16px" }}>
            <div style={{ fontSize: "10px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "6px" }}>
              Methodology
            </div>
            <div style={{ fontSize: "11px", lineHeight: 1.6, color: "var(--ink)" }}>
              <div style={{ marginBottom: "4px" }}>
                <strong>Cost basis:</strong> {report.methodology.cost_basis}.{" "}
                {report.methodology.cost_note}
              </div>
              <div>
                <strong>Attribution:</strong> {report.methodology.attribution_note}
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: "9.5px",
  textTransform: "uppercase",
  color: "var(--muted)",
  marginBottom: "4px",
};