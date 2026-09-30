import { NextResponse } from "next/server";
import { proxyToBackend, BACKEND_URL } from "../../_lib/proxy";

// Credential writes go to the backend's durable store (.env + Supabase row).
// If the backend cannot be reached we must NOT claim success — a lost write
// means the user's keys are gone after the next restart, which is exactly the
// bug this endpoint had.
const TIMEOUT_MS = 120000;

export async function POST(req: Request) {
  // Read the body so it can be forwarded verbatim (a Request body is a one-shot
  // stream and must be consumed before proxying).
  const raw = await req.text().catch(() => "");

  let res: Response;
  try {
    res = await proxyToBackend("/api/connectors/save-all", req, TIMEOUT_MS, raw);
  } catch (err: any) {
    const isTimeout =
      err?.name === "TimeoutError" || String(err?.message || "").toLowerCase().includes("timed out");
    return NextResponse.json(
      {
        success: false,
        persisted: false,
        error: isTimeout ? "Backend timed out while saving credentials." : "Backend unreachable — nothing was saved.",
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
