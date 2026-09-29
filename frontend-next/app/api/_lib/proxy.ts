import { NextResponse } from "next/server";

/**
 * Canonical backend base URL.
 *
 * Every server route must resolve the Python backend through this helper so the
 * frontend and Next route handlers can never disagree about where the backend
 * lives. A hardcoded production URL is intentionally NOT used as a fallback:
 * silently sending local/self-hosted traffic to a shared public backend leaks
 * credentials across environments. Default to the documented local backend.
 */
const rawBase =
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000";

export const BACKEND_URL: string = rawBase
  .replace(/\/+$/, "")
  .replace(/\/api$/, "");

const HOP_BY_HOP_HEADERS = new Set([
  "host",
  "connection",
  "content-length",
  "transfer-encoding",
  "keep-alive",
  "expect",
]);

/**
 * Forward the client's headers to the backend, preserving identity headers
 * (X-User-Id / X-Website-Id / Authorization). Dropping them caused connector
 * calls to be attributed to the wrong account (or rejected outright).
 */
export function forwardHeaders(req: Request): Record<string, string> {
  const headers: Record<string, string> = {};
  req.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      headers[key] = value;
    }
  });
  return headers;
}

export function buildBackendUrl(path: string): string {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  const withApi = suffix.startsWith("/api") ? suffix : `/api${suffix}`;
  return `${BACKEND_URL}${withApi}`;
}

/**
 * Proxy a request to the backend and return the raw Response.
 *
 * `bodyOverride` must be passed by any route that already consumed the request
 * body (e.g. to inspect it): a Request body is a one-shot stream, so proxying
 * the original request afterwards would forward an empty body.
 */
export async function proxyToBackend(
  path: string,
  req: Request,
  timeoutMs = 120000,
  bodyOverride?: string | undefined
): Promise<Response> {
  const headers = forwardHeaders(req);
  const body = ["POST", "PUT", "PATCH"].includes(req.method)
    ? bodyOverride !== undefined
      ? bodyOverride
      : await req.text().catch(() => undefined)
    : undefined;

  return fetch(buildBackendUrl(path), {
    method: req.method,
    headers,
    body,
    redirect: "manual",
    signal: AbortSignal.timeout(timeoutMs),
  });
}

/**
 * Proxy and return a NextResponse that preserves the backend's status code and
 * body. On network failure it returns 502 — never a fabricated success.
 */
export async function proxyJson(
  path: string,
  req: Request,
  timeoutMs = 30000,
  bodyOverride?: string | undefined
): Promise<NextResponse> {
  try {
    const res = await proxyToBackend(path, req, timeoutMs, bodyOverride);
    const text = await res.text().catch(() => "");
    if (!text) return new NextResponse(null, { status: res.status });
    try {
      return NextResponse.json(JSON.parse(text), { status: res.status });
    } catch {
      return new NextResponse(text, { status: res.status });
    }
  } catch (err: any) {
    const isTimeout =
      err?.name === "TimeoutError" || String(err?.message || "").toLowerCase().includes("timed out");
    return NextResponse.json(
      {
        error: "Backend unreachable",
        detail: isTimeout
          ? `Backend did not respond within ${timeoutMs}ms`
          : err?.message || String(err),
        backend: BACKEND_URL,
      },
      { status: isTimeout ? 504 : 502 }
    );
  }
}

/**
 * Stream a backend response through untouched.
 *
 * Server-Sent Events and other long-lived streams must NOT be buffered: awaiting
 * `res.text()` (as proxyJson does) blocks until the backend closes the stream,
 * which for an SSE endpoint never happens until the job ends — the browser sees
 * a hung connection and no events. This pipes the body straight through.
 */
export async function proxyStream(
  path: string,
  req: Request,
  timeoutMs = 300000
): Promise<Response> {
  try {
    const res = await proxyToBackend(path, req, timeoutMs);
    return new Response(res.body, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("content-type") || "application/octet-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (err: any) {
    return new Response(
      `data: ${JSON.stringify({
        error: "Backend unreachable",
        detail: err?.message || String(err),
        backend: BACKEND_URL,
      })}\n\n`,
      { status: 502, headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" } }
    );
  }
}
