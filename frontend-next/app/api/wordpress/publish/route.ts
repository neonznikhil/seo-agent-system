import { proxyJson } from "../../_lib/proxy";

// Publishing is owned by the backend (verified receipt required — a live post
// is never claimed without one). The old handler returned a fake `published`
// success whenever the backend was unreachable. Pass the real result through.
export async function POST(req: Request) {
  return proxyJson("/api/wordpress/publish", req, 120000);
}
