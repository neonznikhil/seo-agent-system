import { proxyJson } from "../../../_lib/proxy";

// Generation is owned by the backend (CrewAI/NVIDIA). The old handler proxied
// but, on any failure, fell back to an in-memory stub that invented an article
// and reported success. Only the real result (or honest failure) is returned.
export async function POST(
  req: Request,
  { params }: { params: Promise<{ website_id: string }> }
) {
  const { website_id } = await params;
  return proxyJson(`/api/writer/${encodeURIComponent(website_id)}/generate`, req, 300000);
}
