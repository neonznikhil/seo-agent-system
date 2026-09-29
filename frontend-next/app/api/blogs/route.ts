import { proxyJson } from "../_lib/proxy";

// This handler used to serve an in-memory `articlesStore`, so it shadowed the
// backend's real /api/blogs and hid the fact that Supabase was unreachable.
// Proxy through so the UI reflects the real (or honestly-failing) result.
export async function GET(req: Request) {
  const url = new URL(req.url);
  return proxyJson(`/api/blogs${url.search}`, req, 30000);
}
