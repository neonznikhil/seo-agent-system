import { proxyJson } from "../_lib/proxy";

// Real content listing lives on the backend (/api/content, Supabase-backed).
// This handler previously returned an in-memory store, shadowing the backend.
// GET and POST are both proxied so creation works too.
export async function GET(req: Request) {
  const url = new URL(req.url);
  return proxyJson(`/api/content${url.search}`, req, 30000);
}

export async function POST(req: Request) {
  return proxyJson("/api/content", req, 30000);
}

export async function PUT(req: Request) {
  return proxyJson("/api/content", req, 30000);
}

export async function DELETE(req: Request) {
  const url = new URL(req.url);
  return proxyJson(`/api/content${url.search}`, req, 30000);
}
