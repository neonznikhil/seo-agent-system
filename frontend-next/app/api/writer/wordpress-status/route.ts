import { NextResponse } from "next/server";
import { proxyToBackend, BACKEND_URL } from "../../_lib/proxy";

const TIMEOUT_MS = 30000;

export async function GET(req: Request) {
  const url = new URL(req.url);
  const website_id = url.searchParams.get("website_id") || "default";

  // Query the backend for the live WordPress status; previously this route
  // always answered `connected: false` regardless of the real state.
  try {
    const res = await proxyToBackend(
      `/api/writer/${encodeURIComponent(website_id)}/wordpress-status`,
      req,
      TIMEOUT_MS
    );
    const text = await res.text().catch(() => "");
    let data: any = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { detail: text };
    }
    return NextResponse.json(data ?? { connected: false }, { status: res.status });
  } catch (err: any) {
    return NextResponse.json(
      {
        connected: false,
        site_url: null,
        authenticated: false,
        website_id,
        status: "unknown",
        user: null,
        categories: [],
        recent_posts: [],
        message: "WordPress status unknown — backend unreachable.",
        detail: err?.message || String(err),
        backend: BACKEND_URL,
      },
      { status: 502 }
    );
  }
}
