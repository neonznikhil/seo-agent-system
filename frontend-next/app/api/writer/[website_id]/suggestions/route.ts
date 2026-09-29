import { proxyJson } from "../../../_lib/proxy";

const TIMEOUT_MS = 30000;

export async function GET(req: Request, { params }: { params: Promise<{ website_id: string }> }) {
  const { website_id } = await params;
  return proxyJson(`/api/writer/${encodeURIComponent(website_id)}/suggestions`, req, TIMEOUT_MS);
}
