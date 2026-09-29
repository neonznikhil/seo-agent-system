import { proxyJson } from "../../../_lib/proxy";

// Real per-website writer content lives on the backend
// (/api/writer/{website_id}/content). The old handler served an in-memory store.
export async function GET(
  req: Request,
  { params }: { params: Promise<{ website_id: string }> }
) {
  const { website_id } = await params;
  const url = new URL(req.url);
  return proxyJson(`/api/writer/${encodeURIComponent(website_id)}/content${url.search}`, req, 30000);
}

export async function POST(
  req: Request,
  { params }: { params: Promise<{ website_id: string }> }
) {
  const { website_id } = await params;
  return proxyJson(`/api/writer/${encodeURIComponent(website_id)}/content`, req, 60000);
}
