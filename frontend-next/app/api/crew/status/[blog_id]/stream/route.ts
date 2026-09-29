import { proxyStream } from "../../../../_lib/proxy";

// SSE progress stream — must be piped through untouched, not fabricated.
// The old handler emitted a fake 4-step sequence and closed, so the UI showed
// invented progress instead of the real CrewAI pipeline.
export async function GET(
  req: Request,
  { params }: { params: Promise<{ blog_id: string }> }
) {
  const { blog_id } = await params;
  return proxyStream(`/api/crew/status/${encodeURIComponent(blog_id)}/stream`, req, 600000);
}
