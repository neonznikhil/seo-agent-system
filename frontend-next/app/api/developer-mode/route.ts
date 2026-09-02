import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    enabled: false,
    mode: "production",
    status: "ok",
  });
}

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  return NextResponse.json({
    success: true,
    enabled: Boolean(body.enabled),
    mode: body.enabled ? "developer" : "production",
  });
}
