import { NextResponse } from "next/server";
import { getSchedule, updateSchedule } from "../schedule-store";

export async function GET() {
  const current = getSchedule();
  return NextResponse.json(current);
}

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const updates: any = {};
  if (body.daily_blog_target !== undefined) updates.daily_blog_target = Number(body.daily_blog_target);
  if (body.auto_topic_selection !== undefined) updates.auto_topic_selection = Boolean(body.auto_topic_selection);
  if (body.interval_minutes !== undefined) updates.generation_interval_minutes = Number(body.interval_minutes);
  if (body.generation_interval_minutes !== undefined) updates.generation_interval_minutes = Number(body.generation_interval_minutes);

  const updated = updateSchedule(updates);
  return NextResponse.json({
    success: true,
    message: "Blog settings saved successfully",
    ...updated,
  });
}

export async function PUT(req: Request) {
  return POST(req);
}
