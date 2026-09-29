import { NextResponse } from "next/server";
import { proxyToBackend, BACKEND_URL } from "../../../_lib/proxy";

// Live WordPress status check — needs more than the old 3s window because it
// performs an outbound WordPress request on the backend.
const TIMEOUT_MS = 30000;

export async function GET(
  req: Request,
  { params }: { params: Promise<{ website_id: string }> }
) {
  const { website_id } = await params;

  let res: Response;
  try {
    res = await proxyToBackend(
      `/api/writer/${encodeURIComponent(website_id)}/wordpress-status`,
      req,
      TIMEOUT_MS
    );
  } catch (err: any) {
    const isTimeout =
      err?.name === "TimeoutError" || String(err?.message || "").toLowerCase().includes("timed out");
    return NextResponse.json(
      {
        connected: false,
        site_url: null,
        authenticated: false,
        website_id,
        status: "unknown",
        message: isTimeout
          ? "WordPress status unknown — backend timed out."
          : "WordPress status unknown — backend unreachable.",
        detail: err?.message || String(err),
        backend: BACKEND_URL,
      },
      { status: isTimeout ? 504 : 502 }
    );
  }

  const text = await res.text().catch(() => "");
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  return NextResponse.json(data ?? { connected: false }, { status: res.status });
}
