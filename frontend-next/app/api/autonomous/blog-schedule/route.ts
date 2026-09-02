import { NextResponse } from "next/server";
import { getSchedule, updateSchedule } from "../schedule-store";

export async function GET() {
  const current = getSchedule();
  return NextResponse.json({
    success: true,
    enabled: true,
    frequency: current.frequency,
    generation_interval_minutes: current.generation_interval_minutes,
    schedule_label: current.schedule_label,
    daily_blog_target: current.daily_blog_target,
    next_run: new Date(current.next_run_timestamp).toISOString(),
    next_blog_seconds: current.next_blog_seconds,
  });
}

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const minutes = Number(body.interval_minutes || body.generation_interval_minutes || 3);
  const daily = Number(body.daily_target || body.daily_blog_target || 10);
  const label = body.label || (minutes <= 60 ? `Every ${minutes} min` : `Every ${Math.round(minutes / 60)} hours`);

  const updated = updateSchedule({
    generation_interval_minutes: minutes,
    daily_blog_target: daily,
    schedule_label: label,
  });

  return NextResponse.json({
    success: true,
    message: `Blog schedule set to ${label}`,
    generation_interval_minutes: minutes,
    schedule_label: label,
    daily_blog_target: daily,
    next_run: new Date(updated.next_run_timestamp).toISOString(),
    next_blog_seconds: minutes * 60,
  });
}
