import { NextResponse } from "next/server";
import { proxyToBackend, BACKEND_URL } from "../../_lib/proxy";

// The key must reach the backend's durable store; a fabricated success here
// would leave the user with an "Saved" toast but no usable NVIDIA key.
const TIMEOUT_MS = 90000;

export async function POST(req: Request) {
  const raw = await req.text().catch(() => "");
  let body: any = {};
  try {
    body = raw ? JSON.parse(raw) : {};
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const apiKey = (body.api_key || "").trim();
  if (!apiKey) {
    return NextResponse.json(
      { success: false, persisted: false, error: "API key cannot be empty" },
      { status: 400 }
    );
  }

  let res: Response;
  try {
    res = await proxyToBackend("/api/connectors/save-nvidia", req, TIMEOUT_MS, raw);
  } catch (err: any) {
    const isTimeout =
      err?.name === "TimeoutError" || String(err?.message || "").toLowerCase().includes("timed out");
    return NextResponse.json(
      {
        success: false,
        persisted: false,
        error: isTimeout ? "Backend timed out while saving the NVIDIA key." : "Backend unreachable — key not saved.",
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
      { success: false, persisted: false, ...(data || {}), backend: BACKEND_URL },
      { status: res.status }
    );
  }

  // Only report success if the backend actually confirmed the write. A 200 with
  // an empty/unrecognized body must not be presented to the user as "saved".
  if (!data || (data.success === undefined && data.persisted === undefined)) {
    return NextResponse.json(
      {
        success: false,
        persisted: false,
        error: "Backend returned no confirmation — the credential was not reported as saved.",
        backend: BACKEND_URL,
      },
      { status: 502 }
    );
  }

  return NextResponse.json(data);
}
