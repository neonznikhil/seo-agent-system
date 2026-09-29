import { NextResponse } from "next/server";
import { proxyToBackend, BACKEND_URL } from "../../_lib/proxy";

// Proxy the backend's live NVIDIA NIM model-list test, preserving its exact
// status. The previous version returned `connected: true` on network failure,
// which is how a user could see "NVIDIA connected" with an invalid key.
const TIMEOUT_MS = 20000;

export async function POST(req: Request) {
  const raw = await req.text().catch(() => "");
  let body: any = {};
  try {
    body = raw ? JSON.parse(raw) : {};
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  let res: Response;
  try {
    res = await proxyToBackend("/api/connectors/test-nvidia", req, TIMEOUT_MS, raw);
  } catch (err: any) {
    const isTimeout =
      err?.name === "TimeoutError" || String(err?.message || "").toLowerCase().includes("timed out");
    return NextResponse.json(
      {
        connected: false,
        status: "unknown",
        error: isTimeout
          ? "NVIDIA NIM validation timed out. Check the key/network and try again."
          : "Backend unreachable — could not validate the NVIDIA key.",
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

  // The backend is authoritative: pass its status through unchanged.
  if (!res.ok) {
    return NextResponse.json(data ?? { connected: false }, { status: res.status });
  }
  return NextResponse.json(data);
}
