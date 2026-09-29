import { NextResponse } from "next/server";
import { proxyToBackend, BACKEND_URL } from "../../_lib/proxy";

// Persist the Serper key on the backend (durable), then relay the live test
// result. The old handler invented a "verified and saved" response when the
// backend was down, so the key silently never persisted.
const TIMEOUT_MS = 20000;

export async function POST(req: Request) {
  const raw = await req.text().catch(() => "");
  let body: any = {};
  try {
    body = raw ? JSON.parse(raw) : {};
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  if (!(body.api_key || "").trim()) {
    return NextResponse.json(
      { success: false, connected: false, error: "API key cannot be empty" },
      { status: 400 }
    );
  }

  let res: Response;
  try {
    res = await proxyToBackend("/api/connectors/save-serper", req, TIMEOUT_MS, raw);
  } catch (err: any) {
    const isTimeout =
      err?.name === "TimeoutError" || String(err?.message || "").toLowerCase().includes("timed out");
    return NextResponse.json(
      {
        success: false,
        connected: false,
        persisted: false,
        error: isTimeout
          ? "Backend timed out while saving the Serper key."
          : "Backend unreachable — Serper key not saved.",
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
      { success: false, connected: false, persisted: false, ...(data || {}) },
      { status: res.status }
    );
  }
  return NextResponse.json(data);
}
