import { proxyJson } from "../../_lib/proxy";

const TIMEOUT_MS = 30000;

export async function GET(req: Request) {
  const url = new URL(req.url);
  const limit = url.searchParams.get("limit") || "20";
  return proxyJson(`/api/scheduler/logs?limit=${encodeURIComponent(limit)}`, req, TIMEOUT_MS);
}
