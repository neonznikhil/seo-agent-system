import { NextResponse } from "next/server";
import { proxyToBackend, BACKEND_URL } from "../../../../../_lib/proxy";

const TIMEOUT_MS = 60000;

export async function POST(req: Request, { params }: { params: Promise<{ website_id: string; content_id: string }> }) {
  const { website_id, content_id } = await params;

  try {
    const res = await proxyToBackend(
      `/api/writer/${encodeURIComponent(website_id)}/content/${encodeURIComponent(content_id)}/publish`,
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
    return NextResponse.json(data ?? { success: false }, { status: res.status });
  } catch (err: any) {
    // HONEST: backend unreachable means the publish did NOT happen.
    return NextResponse.json(
      {
        success: false,
        status: "failed",
        wp_post_id: null,
        post_url: null,
        error: "Backend unavailable — article was NOT published. Retry when the backend is reachable.",
        detail: err?.message || String(err),
        backend: BACKEND_URL,
      },
      { status: 502 }
    );
  }
}
