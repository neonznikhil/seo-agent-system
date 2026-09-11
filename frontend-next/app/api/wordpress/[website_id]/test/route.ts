import { NextResponse } from "next/server";

// HONEST: this route cannot verify a WordPress connection on its own.
// It proxies the backend verifier; without a backend there is no proof.
export async function POST(
  req: Request,
  { params }: { params: Promise<{ website_id: string }> }
) {
  const { website_id } = await params;
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const body = await req.json().catch(() => ({}));
    const res = await fetch(`${backendUrl}/api/wordpress/${website_id}/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(5000),
    });
    if (res.ok) {
      return NextResponse.json(await res.json());
    }
  } catch {
    // Fall through to honest failure
  }
  return NextResponse.json(
    {
      success: false,
      connected: false,
      status: "unknown",
      website_id,
      message: "WordPress connection not verified — backend unreachable.",
    },
    { status: 502 }
  );
}
