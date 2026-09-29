import { proxyJson } from "../../../../../_lib/proxy";

// Draft creation is owned by the backend: it resolves the content row, applies
// the saved per-website WordPress credentials (Fernet-encrypted durable store),
// creates the draft, and persists wp_post_id. The old handler used an in-memory
// article store and a per-process credential cache that vanished on restart.
// Credentials may still be passed in the body to override for one call.
export async function POST(
  req: Request,
  { params }: { params: Promise<{ website_id: string; content_id: string }> }
) {
  const { website_id, content_id } = await params;
  return proxyJson(
    `/api/writer/${encodeURIComponent(website_id)}/content/${encodeURIComponent(content_id)}/approve-draft`,
    req,
    120000
  );
}
