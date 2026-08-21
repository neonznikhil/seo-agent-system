"use client";

import { useEffect, useState } from "react";
import { get } from "@/lib/api";

interface BlogItem {
  id: string;
  title: string;
  status: string;
  agent_name?: string;
}

interface DayData {
  date: string;
  blogs: BlogItem[];
}

interface CalendarResponse {
  days: DayData[];
}

function getStatusColor(status: string): string {
  switch (status) {
    case "draft_planned":
      return "#D1CCC4";
    case "pending_approval":
      return "#FF4D12";
    case "published":
      return "#111";
    case "needs_revision":
      return "#FF4D12";
    default:
      return "#6B6B6B";
  }
}

function getTagInfo(blogs: BlogItem[]): { label: string; accent: boolean } {
  if (blogs.length === 0) return { label: "", accent: false };
  const status = blogs[0].status;
  switch (status) {
    case "pending_approval":
      return { label: "Blog", accent: true };
    case "published":
      return { label: "Blog", accent: true };
    case "draft_planned":
      return { label: "Optimize", accent: false };
    default:
      return { label: "Review", accent: false };
  }
}

export function ContentCalendar({ websiteId }: { websiteId: string }) {
  const [calendarData, setCalendarData] = useState<CalendarResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchCalendar() {
      try {
        setLoading(true);
        const data = await get(`/calendar/${websiteId}?days=7`);
        setCalendarData(data);
        setError(null);
      } catch (err) {
        setError("Backend not running");
        setCalendarData(null);
      } finally {
        setLoading(false);
      }
    }

    fetchCalendar();
  }, [websiteId]);

  if (loading) {
    return (
      <div className="bg-stone border border-ink p-4">
        <div className="flex items-center justify-center py-8">
          <div className="w-4 h-4 border-2 border-ink border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-stone border border-ink p-4">
        <div className="text-[11px] text-ink mono-font text-center">
          {error}
        </div>
      </div>
    );
  }

  if (!calendarData || calendarData.days.length === 0) {
    return (
      <div className="bg-stone border border-ink p-4">
        <div className="text-[11px] text-ink mono-font text-center py-8">
          No calendar data available
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="grid grid-cols-7 border border-ink divide-x divide-line">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day, index) => (
          <div key={index} className="bg-stone p-2 text-center text-[9px] text-muted uppercase tracking-wider mono-font">
            {day}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7 border-x border-b border-line divide-x divide-line">
        {calendarData.days.map((day, dayIndex) => {
          const date = new Date(day.date).getDate();
          const tag = getTagInfo(day.blogs);
          const entry = day.blogs[0]?.title || "";

          return (
            <div key={dayIndex} className="p-2 border-t border-line last:border-t-0 min-h-[68px]">
              <div className="text-[9px] text-muted mb-1">{date}</div>
              {tag.label && (
                <div
                  className={`text-[9px] px-1 py-0.5 mb-1 inline-block ${
                    tag.accent ? "bg-accent text-paper" : "bg-stone border border-ink"
                  }`}
                >
                  {tag.label}
                </div>
              )}
              {entry && (
                <div className="text-[10px] text-ink leading-tight">{entry}</div>
              )}
              {day.blogs.length === 0 && (
                <div className="text-[10px] text-muted">—</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}