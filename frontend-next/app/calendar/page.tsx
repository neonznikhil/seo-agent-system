"use client";

import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface CalendarDay {
  date: number;
  day: string;
  status: "pending" | "active" | "complete";
}

function getStatusColor(status: CalendarDay["status"]) {
  switch (status) {
    case "complete":
      return "#FF4D12";
    case "active":
      return "#000000";
    default:
      return "#d6d3d1";
  }
}

export default function CalendarPage() {
  const [week, setWeek] = useState<CalendarDay[]>([]);
  const [statusCounts, setStatusCounts] = useState<{ active: number; pending: number; complete: number }>({
    active: 0,
    pending: 0,
    complete: 0,
  });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const getStatusFromBlogs = (blogs: any[]): CalendarDay["status"] => {
    if (!blogs || blogs.length === 0) return "pending";
    const hasPublished = blogs.some((b: any) => b.status === "published");
    const hasPendingApproval = blogs.some((b: any) => b.status === "pending_approval");
    const hasNeedsRevision = blogs.some((b: any) => b.status === "needs_revision");

    if (hasPublished) return "complete";
    if (hasPendingApproval || hasNeedsRevision) return "active";
    return "pending";
  };

  useEffect(() => {
    async function fetchCalendarData() {
      try {
        setLoading(true);
        const websiteId = getCurrentWebsiteId();
        const data = await get(`/calendar/${websiteId}?days=7`);
        if (data && data.days) {
          const weekData: CalendarDay[] = data.days.map((day: any, index: number) => {
            const dateObj = new Date(day.date);
            return {
              date: dateObj.getDate(),
              day: dateObj.toLocaleString("en-US", { weekday: "short" }).toUpperCase().substring(0, 3),
              status: getStatusFromBlogs(day.blogs || []),
            };
          });
          setWeek(weekData);

          const counts = {
            active: weekData.filter((d) => d.status === "active").length,
            pending: weekData.filter((d) => d.status === "pending").length,
            complete: weekData.filter((d) => d.status === "complete").length,
          };
          setStatusCounts(counts);
        } else {
          const today = new Date();
          const weekData: CalendarDay[] = Array.from({ length: 7 }, (_, i) => {
            const d = new Date(today);
            d.setDate(today.getDate() + i);
            return {
              date: d.getDate(),
              day: d.toLocaleString("en-US", { weekday: "short" }).toUpperCase().substring(0, 3),
              status: "pending" as CalendarDay["status"],
            };
          });
          setWeek(weekData);
        }
        setError(null);
      } catch (err) {
        setError("Backend not running - run uvicorn main:app --reload in backend");
        const today = new Date();
        const weekData: CalendarDay[] = Array.from({ length: 7 }, (_, i) => {
          const d = new Date(today);
          d.setDate(today.getDate() + i);
          return {
            date: d.getDate(),
            day: d.toLocaleString("en-US", { weekday: "short" }).toUpperCase().substring(0, 3),
            status: "pending" as CalendarDay["status"],
          };
        });
        setWeek(weekData);
      } finally {
        setLoading(false);
      }
    }

    fetchCalendarData();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <h1 className="text-3xl font-bold dot-font">CALENDAR</h1>
        <div className="flex gap-4 text-xs mono-font">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 bg-accent rounded-full" />
            Active: {statusCounts.active}
          </span>
          <span className="text-muted">/</span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 bg-line rounded-full" />
            Pending: {statusCounts.pending}
          </span>
          <span className="text-muted">/</span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2" style={{ backgroundColor: "#FF4D12", opacity: 0.5 }} />
            Complete: {statusCounts.complete}
          </span>
        </div>
      </div>

      <div className="bg-stone border border-ink p-4">
        <div className="grid grid-cols-7 gap-px border border-line divide-x divide-line">
          {week.length > 0 ? week.map((day) => (
            <div key={day.day} className="bg-stone">
              <div className="text-[10px] text-muted mono-font text-center py-1">{day.day}</div>
            </div>
          )) : ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"].map((day) => (
            <div key={day} className="bg-stone">
              <div className="text-[10px] text-muted mono-font text-center py-1">{day}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-7 gap-px border-x border-line divide-x divide-line">
          {week.map((day, i) => (
            <div
              key={day.date}
              className={`bg-stone ${i === 0 ? "border-l" : ""} flex flex-col items-center py-4`}
            >
              <span className="text-[10px] text-muted mono-font mb-2">{day.date}</span>
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: getStatusColor(day.status) }} />
            </div>
          ))}
        </div>
      </div>

      <div className="bg-stone border border-ink p-4">
        <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">QUICK ACTIONS</div>
        <div className="grid grid-cols-3 gap-2">
          <button className="px-3 py-2 border border-ink text-[11px] mono-font pill">Schedule Blog</button>
          <button className="px-3 py-2 border border-ink text-[11px] mono-font pill">Generate Topic</button>
          <button className="px-3 py-2 border border-ink text-[11px] mono-font pill">View Queue</button>
        </div>
      </div>
    </div>
  );
}
