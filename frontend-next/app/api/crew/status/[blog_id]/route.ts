import { proxyJson } from "../../../_lib/proxy";

// Real generation status lives on the backend (/api/crew/status/{blog_id}).
// The old handler invented pipeline logs, scores, and a "complete" status even
// when nothing had run.
export async function GET(
  req: Request,
  { params }: { params: Promise<{ blog_id: string }> }
) {
  const { blog_id } = await params;
  return proxyJson(`/api/crew/status/${encodeURIComponent(blog_id)}`, req, 60000);
}
