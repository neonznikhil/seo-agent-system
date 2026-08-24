"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface CalendarItem {
  id: string;
  source_table: string;
  title: string;
  status: string;
  date: string;
  keyword?: string | null;
  type?: string;
  draggable?: boolean;
  next_run?: string | null;
}

interface CalendarDay {
  date: string;
  day: string;
  is_today: boolean;
  items: CalendarItem[];
  count: number;
}

const STATUS_META: Record<string, { label: string; cls: string }> = {
  published: { label: "Published", cls: "badge-green" },
  pending_approval: { label: "Awaiting Approval", cls: "badge-accent" },
  draft: { label: "Draft", cls: "badge-amber" },
  agent_run: { label: "Agent Run", cls: "badge-ink" },
  scheduled: { label: "Scheduled", cls: "badge-accent" },
};

export default function CalendarPage() {
  const [days, setDays] = useState<CalendarDay[]>([]);
  const [items, setItems] = useState<CalendarItem[]>([]);
  const [summary, setSummary] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [websiteId, setWebsiteId] = useState<string>("");
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  const fetchCalendarData = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);
    if (!wid) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = await get(`/api/calendar/${wid}`);
      if (data?.success && data?.data) {
        setDays(data.data.calendar || []);
        setItems(data.data.items || []);
        setSummary(data.data.summary || {});
      } else {
        setError(data?.error || "Calendar unavailable");
        setDays([]);
        setItems([]);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load editorial calendar");
    } finally {
      setLoading(false);
    }
  }, []);

  // Drag-to-reschedule
  const handleDrop = async (item: CalendarItem, targetDate: string) => {
    if (item.date === targetDate) return;
    try {
      await post(`/api/calendar/${websiteId}/reschedule`, {
        item_id: item.id,
        target_table: item.source_table === "content_log" ? "content_log" : "content_calendar",
        new_date: targetDate,
      });
      showToast(`Rescheduled "${item.title}" to ${targetDate}`);
      fetchCalendarData();
    } catch (e: any) {
      showToast(`Reschedule failed: ${e.message}`);
    }
  };

  useEffect(() => {
    fetchCalendarData();
    const handleChanged = () => fetchCalendarData();
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [fetchCalendarData]);

  if (!websiteId && !loading) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">Publishing Schedule</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No website selected.</strong> Connect a website to see its autonomous publishing schedule.
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

  const contentItems = items.filter((i) => i.type !== "agent_run");

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      {toastMsg && (
        <div style={{
          position: "fixed", bottom: "24px", left: "50%", transform: "translateX(-50%)",
          background: "var(--ink)", color: "var(--bg)", padding: "10px 22px", fontSize: "10.5px",
          textTransform: "uppercase", letterSpacing: ".07em", zIndex: 9999,
          fontFamily: "'IBM Plex Mono', monospace", border: "1px solid var(--accent)",
        }}>
          {toastMsg}
        </div>
      )}

      <div className="page-heading">Publishing Schedule</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Auto-populated from generated content &amp; scheduled agent runs · Drag entries to reschedule
        {error && (
          <span className="badge badge-red" style={{ marginLeft: "12px" }}>{error}</span>
        )}
      </div>

      {/* SUMMARY STRIP */}
      <div className="kpi-strip" style={{ marginBottom: "20px" }}>
        <div className="kpi-cell">
          <div className="kpi-label">Total Scheduled Items</div>
          <div className="kpi-val">{contentItems.length}</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Awaiting Approval</div>
          <div className="kpi-val" style={{ color: "var(--accent)" }}>{summary.pending_approval ?? 0}</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Published</div>
          <div className="kpi-val" style={{ color: "var(--green)" }}>{summary.published ?? 0}</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Scheduled Agent Runs</div>
          <div className="kpi-val">{summary.agent_runs ?? 0}</div>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: "20px" }}>
        <div className="panel-head">
          <span className="panel-label">30-Day Pipeline Schedule</span>
          <button className="panel-action" onClick={fetchCalendarData}>Refresh</button>
        </div>
        <div className="panel-body">
          {loading ? (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)" }}>Loading schedule...</div>
          ) : days.length === 0 ? (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              No calendar data available yet.
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: "8px" }}>
              {days.map((day) => (
                <div
                  key={day.date}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    const raw = e.dataTransfer.getData("text/plain");
                    if (raw) {
                      try {
                        const dragged = JSON.parse(raw) as CalendarItem;
                        handleDrop(dragged, day.date);
                      } catch {}
                    }
                  }}
                  style={{
                    padding: "10px 8px",
                    border: day.is_today ? "1.5px solid var(--accent)" : "1px solid var(--line)",
                    background: day.is_today ? "rgba(255, 77, 18, 0.05)" : "var(--surface)",
                    minHeight: "96px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "9px", color: "var(--muted)", textTransform: "uppercase" }}>
                    <span>{day.day.slice(0, 3)}</span>
                    <span>{day.date}</span>
                  </div>
                  {day.items.length === 0 ? (
                    <div style={{ fontSize: "9.5px", color: "var(--muted)", marginTop: "14px", textAlign: "center" }}>—</div>
                  ) : (
                    <div style={{ marginTop: "6px", display: "flex", flexDirection: "column", gap: "3px" }}>
                      {day.items.map((item) => {
                        const meta = STATUS_META[item.status] || { label: item.status, cls: "" };
                        return (
                          <div
                            key={`${item.source_table}_${item.id}`}
                            draggable={item.draggable}
                            onDragStart={(e) =>
                              e.dataTransfer.setData("text/plain", JSON.stringify(item))
                            }
                            title={item.title}
                            style={{
                              fontSize: "9px",
                              padding: "3px 5px",
                              border: "1px solid var(--line)",
                              background: "var(--bg)",
                              cursor: item.draggable ? "grab" : "default",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            <span className={`badge ${meta.cls}`} style={{ marginRight: "4px", fontSize: "7.5px", padding: "0 3px" }}>
                              {meta.label}
                            </span>
                            {item.title.length > 26 ? `${item.title.slice(0, 26)}…` : item.title}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* UPCOMING LIST VIEW */}
      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">All Scheduled Content</span>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Title</th>
                <th>Keyword</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {contentItems.length > 0 ? (
                contentItems
                  .slice()
                  .sort((a, b) => (a.date > b.date ? 1 : -1))
                  .map((item) => {
                    const meta = STATUS_META[item.status] || { label: item.status, cls: "" };
                    return (
                      <tr key={`${item.source_table}_${item.id}`}>
                        <td>{item.date}</td>
                        <td style={{ fontWeight: 600 }}>{item.title}</td>
                        <td style={{ color: "var(--muted)", fontSize: "10px" }}>{item.keyword || "—"}</td>
                        <td><span className={`badge ${meta.cls}`}>{meta.label}</span></td>
                      </tr>
                    );
                  })
              ) : (
                <tr>
                  <td colSpan={4} style={{ textAlign: "center", padding: "24px", color: "var(--muted)" }}>
                    Nothing scheduled yet. Every article the system generates gets an automatic publish slot
                    48 hours out — connect a website or force-generate one on the Writer page.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
