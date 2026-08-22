"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface CalendarDay {
  date: number;
  day: string;
  fullDate?: string;
  status: "pending" | "active" | "complete";
  blogs?: any[];
}

export default function CalendarPage() {
  const [week, setWeek] = useState<CalendarDay[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [websiteId, setWebsiteId] = useState<string>("");

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
      const data = await get(`/api/calendar/${wid}?days=14`);
      if (data && data.days && Array.isArray(data.days)) {
        const weekData: CalendarDay[] = data.days.map((day: any) => {
          const dateObj = new Date(day.date || day);
          const blogs = day.blogs || [];
          const hasPublished = blogs.some((b: any) => b.status === "published");
          const hasDraft = blogs.some((b: any) => b.status === "draft" || b.status === "pending_approval");
          
          return {
            date: dateObj.getDate(),
            day: dateObj.toLocaleString("en-US", { weekday: "short" }).toUpperCase(),
            fullDate: day.date,
            status: hasPublished ? "complete" : hasDraft ? "active" : "pending",
            blogs,
          };
        });
        setWeek(weekData);
      } else {
        setWeek([]);
      }
    } catch (err: any) {
      console.warn("Calendar fetch error:", err);
      setError(err.message || "Failed to load editorial calendar");
      setWeek([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCalendarData();
    const handleChanged = () => fetchCalendarData();
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [fetchCalendarData]);

  if (loading && week.length === 0) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px auto" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Loading autonomous editorial calendar schedule...
        </p>
      </div>
    );
  }

  if (!websiteId) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">Editorial Content Calendar</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No data yet — add a website first.</strong> Connect your website to view scheduled autonomous blog publication dates.
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
      <div className="page-heading">Editorial Content Calendar</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Autonomous Publishing Schedule · Content Cadence · Scheduled Pipeline Runs
        {error && (
          <span className="badge badge-amber" style={{ marginLeft: "12px" }}>
            {error}
          </span>
        )}
      </div>

      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">14-Day Publishing Pipeline Schedule</span>
          <button className="panel-action" onClick={fetchCalendarData}>
            Refresh
          </button>
        </div>
        <div className="panel-body">
          {week.length === 0 ? (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              No scheduled events found for this website. Generate articles in Content Studio to populate the calendar.
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))", gap: "10px" }}>
              {week.map((item, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: "14px 10px",
                    border: "1px solid var(--line)",
                    background: item.status === "complete" ? "rgba(34, 197, 94, 0.08)" : item.status === "active" ? "rgba(255, 77, 18, 0.08)" : "var(--surface)",
                    borderTop: `3px solid ${item.status === "complete" ? "var(--green)" : item.status === "active" ? "var(--accent)" : "var(--line)"}`,
                    textAlign: "center",
                  }}
                >
                  <div style={{ fontSize: "11px", color: "var(--muted)", fontWeight: 600 }}>{item.day}</div>
                  <div style={{ fontSize: "20px", fontWeight: "bold", margin: "6px 0" }}>{item.date}</div>
                  <div>
                    <span className={`badge ${item.status === "complete" ? "badge-green" : item.status === "active" ? "badge-accent" : ""}`}>
                      {item.status === "complete" ? "Published" : item.status === "active" ? "Draft Ready" : "Scheduled"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
