import { NextResponse } from "next/server";
import { proxyToBackend, proxyStream, BACKEND_URL } from "../_lib/proxy";

// Catch-all proxy for backend routes that have no dedicated Next handler
// (e.g. /api/connectors/test-gsc, /api/wordpress/{id}/posts). Identity headers
// are forwarded and long-running generation/crawl calls get an extended window.
async function handleProxy(req: Request, slug: string[]) {
  const path = "/" + slug.join("/");
  const url = new URL(req.url);
  const search = url.search;

  // SSE / streaming endpoints must be piped, not buffered: reading the whole
  // body first would hold the browser connection open with no events. Decide
  // from the request AND, as a fallback, from the backend's response
  // content-type (some streams do not advertise via Accept or a /stream path).
  const requestWantsStream =
    req.headers.get("accept")?.includes("text/event-stream") ||
    path.endsWith("/stream") ||
    path.includes("/stream/");
  const isLongRunning = [
    "/generate",
    "/crawl",
    "/crew",
    "/cluster",
    "/blog",
    "/research",
    "/sync",
    "/live",
    "/measure",
  ].some((segment) => path.includes(segment));
  const timeoutMs = requestWantsStream ? 600000 : isLongRunning ? 300000 : 90000;

  if (requestWantsStream) {
    return proxyStream(`${path}${search}`, req, timeoutMs);
  }

  try {
    const res = await proxyToBackend(`${path}${search}`, req, timeoutMs);
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("text/event-stream")) {
      return new Response(res.body, {
        status: res.status,
        headers: {
          "Content-Type": contentType,
          "Cache-Control": "no-cache, no-transform",
          Connection: "keep-alive",
          "X-Accel-Buffering": "no",
        },
      });
    }
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
        detail: isTimeout ? "Backend request timed out" : err?.message || String(err),
        backend: BACKEND_URL,
      },
      { status: isTimeout ? 504 : 502 }
    );
  }
}

export async function GET(
  req: Request,
  { params }: { params: Promise<{ slug: string[] }> }
) {
  const { slug } = await params;
  return handleProxy(req, slug);
}

export async function POST(
  req: Request,
  { params }: { params: Promise<{ slug: string[] }> }
) {
  const { slug } = await params;
  return handleProxy(req, slug);
}

export async function PUT(
  req: Request,
  { params }: { params: Promise<{ slug: string[] }> }
) {
  const { slug } = await params;
  return handleProxy(req, slug);
}

export async function DELETE(
  req: Request,
  { params }: { params: Promise<{ slug: string[] }> }
) {
  const { slug } = await params;
  return handleProxy(req, slug);
}

export async function PATCH(
  req: Request,
  { params }: { params: Promise<{ slug: string[] }> }
) {
  const { slug } = await params;
  return handleProxy(req, slug);
}
