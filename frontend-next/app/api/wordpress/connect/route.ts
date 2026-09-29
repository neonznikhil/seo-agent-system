import { NextResponse } from "next/server";
import { proxyToBackend, BACKEND_URL } from "../../_lib/proxy";

// Delegates the WordPress connection test to the backend, which performs real
// REST + role verification and persists the credentials Fernet-encrypted.
//
// The previous handler talked to WordPress directly from this route, wrote the
// plaintext app password to a server-side file, and returned
// `connected: true` even when both REST and XML-RPC verification failed. That is
// the exact "says connected, but nothing works" bug.
const TIMEOUT_MS = 30000;

export async function POST(req: Request) {
  let res: Response;
  try {
    res = await proxyToBackend("/api/wordpress/connect", req, TIMEOUT_MS);
  } catch (err: any) {
    const isTimeout =
      err?.name === "TimeoutError" || String(err?.message || "").toLowerCase().includes("timed out");
    return NextResponse.json(
      {
        success: false,
        connected: false,
        error: isTimeout
          ? "WordPress verification timed out. Check the site URL/network and try again."
          : "Backend unreachable — WordPress was not verified.",
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

  if (!res.ok) {
    return NextResponse.json(
      { success: false, connected: false, ...(data || {}) },
      { status: res.status }
    );
  }
  return NextResponse.json(data);
}
