import { proxyJson } from "../_lib/proxy";

// Query-string and identity headers are preserved by proxyJson; the backend's
// real status (and honest empty result) is passed through instead of a
// fabricated sample keyword list.
const TIMEOUT_MS = 30000;

export async function GET(req: Request) {
  const url = new URL(req.url);
  const wid = url.searchParams.get("website_id") || "";
  const path = `/api/keywords${wid ? `?website_id=${encodeURIComponent(wid)}` : ""}`;
  return proxyJson(path, req, TIMEOUT_MS);
}
