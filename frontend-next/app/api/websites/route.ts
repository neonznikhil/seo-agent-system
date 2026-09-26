import { NextResponse } from "next/server";

// This file previously exported GET only. A Next.js route handler shadows the
// /api/:path* rewrite, so `POST /api/websites` never reached the backend and
// Next answered 405 -- which is what "Failed to create website: API 405" was.
const backendBase = () =>
  (process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

async function proxy(req: Request, path: string) {
  const headers: Record<string, string> = {};
  req.headers.forEach((val, key) => {
    if (!["host", "connection", "content-length"].includes(key.toLowerCase())) {
      headers[key] = val;
    }
  });

  let body: string | undefined;
  if (["POST", "PUT", "PATCH"].includes(req.method)) {
    body = await req.text().catch(() => undefined);
  }

  const res = await fetch(`${backendBase()}${path}`, {
    method: req.method,
    headers,
    body,
    signal: AbortSignal.timeout(120000),
  });

  const text = await res.text().catch(() => "");
  if (!text) return new NextResponse(null, { status: res.status });
  try {
    return NextResponse.json(JSON.parse(text), { status: res.status });
  } catch {
    return new NextResponse(text, { status: res.status });
  }
}

export async function GET() {
  // Try proxying to backend first
  const backendUrl = backendBase();
  try {
    const backendRes = await fetch(`${backendUrl}/api/websites`, {
      signal: AbortSignal.timeout(3000),
    });
    if (backendRes.ok) {
      const data = await backendRes.json();
      return NextResponse.json(data);
    }
  } catch {
    // Fall through to native fallback
  }

  // HONEST: backend unreachable means NO sites. Never invent a demo site —
  // every downstream call would attribute content to someone else's domain.
  return NextResponse.json([]);
}

export async function POST(req: Request) {
  return proxy(req, "/api/websites");
}

export async function PUT(req: Request) {
  return proxy(req, "/api/websites");
}

export async function PATCH(req: Request) {
  return proxy(req, "/api/websites");
}

export async function DELETE(req: Request) {
  return proxy(req, "/api/websites");
}
