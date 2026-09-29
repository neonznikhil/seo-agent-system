import { proxyJson } from "../../_lib/proxy";

// Blog settings are persisted on the backend (per website/account). The old
// in-memory handler shadowed it and returned defaults regardless of the real
// saved values.
export async function GET(req: Request) {
  const url = new URL(req.url);
  return proxyJson(`/api/autonomous/blog-settings${url.search}`, req, 30000);
}

export async function POST(req: Request) {
  return proxyJson("/api/autonomous/blog-settings", req, 30000);
}

export async function PUT(req: Request) {
  return proxyJson("/api/autonomous/blog-settings", req, 30000);
}
