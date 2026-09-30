import { NextResponse } from "next/server";
import { proxyToBackend, BACKEND_URL } from "../../_lib/proxy";

// Live Serper verification must run on the backend so the same code path that
// persists the key also validates it. Never fabricate a successful result.
const TIMEOUT_MS = 60000;

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
    res = await proxyToBackend("/api/connectors/test-serper", req, TIMEOUT_MS, raw);
  } catch (err: any) {
    const isTimeout =
      err?.name === "TimeoutError" || String(err?.message || "").toLowerCase().includes("timed out");
    return NextResponse.json(
      {
        connected: false,
        status: "unknown",
        error: isTimeout
          ? "Serper validation timed out. Check the key/network and try again."
          : "Backend unreachable — could not validate the Serper key.",
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
    return NextResponse.json(data ?? { connected: false }, { status: res.status });
  }
  return NextResponse.json(data);
}
