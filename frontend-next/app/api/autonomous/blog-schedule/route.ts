import { proxyJson } from "../../_lib/proxy";

// The schedule is persisted on the backend (per website/account). The old
// in-memory handler shadowed it and silently dropped every save.
export async function GET(req: Request) {
  const url = new URL(req.url);
  return proxyJson(`/api/autonomous/blog-schedule${url.search}`, req, 30000);
}

export async function POST(req: Request) {
  return proxyJson("/api/autonomous/blog-schedule", req, 30000);
}
