import { proxyJson } from "../../../_lib/proxy";

const TIMEOUT_MS = 60000;

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyJson(`/api/dashboard/${encodeURIComponent(id)}/metrics`, req, TIMEOUT_MS);
}
