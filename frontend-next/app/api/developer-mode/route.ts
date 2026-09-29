import { proxyJson } from "../_lib/proxy";

// Developer-mode flags live on the backend. This handler returned a static
// {enabled:false} object, which shadowed the real endpoint.
export async function GET(req: Request) {
  return proxyJson("/api/developer-mode", req, 30000);
}

export async function POST(req: Request) {
  return proxyJson("/api/developer-mode", req, 30000);
}
