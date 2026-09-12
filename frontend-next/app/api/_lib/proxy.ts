import { NextResponse } from "next/server";

const BACKEND_URL = (
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000"
).replace(/\/+$/, "");

async function proxyToBackend(path: string, req: Request): Promise<Response | null> {
  if (!BACKEND_URL) {
    return null;
  }
  const target = `${BACKEND_URL}${path.startsWith("/") ? path : `/${path}`}`;

  const headers: Record<string, string> = {};
  req.headers.forEach((val, key) => {
    if (!["host", "connection", "content-length"].includes(key.toLowerCase())) {
      headers[key] = val;
    }
  });

  const body = ["POST", "PUT", "PATCH"].includes(req.method)
    ? await req.text().catch(() => undefined)
    : undefined;

  return fetch(target, {
    method: req.method,
    headers,
    body,
    redirect: "manual",
    signal: AbortSignal.timeout(120000),
  });
}

export { BACKEND_URL, proxyToBackend };

