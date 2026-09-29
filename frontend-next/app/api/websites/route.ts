import { proxyJson } from "../_lib/proxy";

// This file previously exported GET only. A Next.js route handler shadows the
// /api/:path* rewrite, so `POST /api/websites` never reached the backend and
// Next answered 405 — that was the "Failed to create website: API 405" bug.
// All methods are proxied with identity headers preserved, and the backend's
// real status code is passed through (never masked as success).

export async function GET(req: Request) {
  // Listing is a normal read; use the shared 30s proxy timeout rather than the
  // old 3s window that silently returned an empty list on slow backends.
  return proxyJson("/api/websites", req, 30000);
}

export async function POST(req: Request) {
  return proxyJson("/api/websites", req, 120000);
}

export async function PUT(req: Request) {
  return proxyJson("/api/websites", req, 120000);
}

export async function PATCH(req: Request) {
  return proxyJson("/api/websites", req, 120000);
}

export async function DELETE(req: Request) {
  return proxyJson("/api/websites", req, 30000);
}
