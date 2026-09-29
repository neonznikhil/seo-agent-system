import { NextResponse } from "next/server";
import { proxyToBackend, BACKEND_URL } from "../../../_lib/proxy";

// This route cannot verify a WordPress connection on its own — it proxies the
// backend verifier. The old 5s client timeout aborted before the backend's own
// 12s WordPress timeout, turning slow-but-valid sites into "unreachable".
const TIMEOUT_MS = 30000;

export async function POST(
  req: Request,
  { params }: { params: Promise<{ website_id: string }> }
) {
  const { website_id } = await params;

  let res: Response;
  try {
    res = await proxyToBackend(
      `/api/wordpress/${encodeURIComponent(website_id)}/test`,
      req,
      TIMEOUT_MS
    );
  } catch (err: any) {
    const isTimeout =
      err?.name === "TimeoutError" || String(err?.message || "").toLowerCase().includes("timed out");
    return NextResponse.json(
      {
        success: false,
        connected: false,
        status: "unknown",
        website_id,
        message: isTimeout
          ? "WordPress connection not verified — backend timed out."
          : "WordPress connection not verified — backend unreachable.",
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

  // Preserve the backend's exact result (including 401/403 diagnostics) so the
  // user sees the real reason a connection failed.
  return NextResponse.json(data ?? { connected: false }, { status: res.status });
}
