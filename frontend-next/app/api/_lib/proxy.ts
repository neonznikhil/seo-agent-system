import { NextResponse } from "next/server";

const BACKEND_URL = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/+$/, "");

function isLocalhost(url: string): boolean {
  return /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/|$)/.test(url);
}

async function proxyToBackend(path: string, req: Request): Promise<Response | null> {
  if (!BACKEND_URL || isLocalhost(BACKEND_URL)) {
    return null;
  }
  const target = `${BACKEND_URL}${path.startsWith("/") ? path : `/${path}`}`;
  const body = await req.text();
  return fetch(target, {
    method: req.method,
    headers: req.headers,
    body: body || undefined,
    redirect: "manual",
  });
}

export { BACKEND_URL, isLocalhost, proxyToBackend };
