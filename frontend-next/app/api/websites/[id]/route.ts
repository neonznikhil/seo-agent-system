import { proxyJson } from "../../_lib/proxy";

// GET/PUT/DELETE all proxy to the backend with identity headers preserved and
// the backend's real status passed through. The old GET used a 3s timeout and a
// hardcoded public backend URL fallback; both are removed.

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyJson(`/api/websites/${encodeURIComponent(id)}`, req, 30000);
}

// This dynamic segment also captures backend aliases such as
// /api/websites/create and /api/websites/list. A route handler shadows the
// catch-all proxy, so without POST/PUT/PATCH here those aliases returned 405
// instead of reaching the backend.
export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyJson(`/api/websites/${encodeURIComponent(id)}`, req, 120000);
}

export async function PUT(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyJson(`/api/websites/${encodeURIComponent(id)}`, req, 120000);
}

export async function PATCH(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyJson(`/api/websites/${encodeURIComponent(id)}`, req, 120000);
}

export async function DELETE(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyJson(`/api/websites/${encodeURIComponent(id)}`, req, 30000);
}
