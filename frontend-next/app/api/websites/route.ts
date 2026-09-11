import { NextResponse } from "next/server";

export async function GET(req: Request) {
  // Try proxying to backend first
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const backendRes = await fetch(`${backendUrl}/api/websites`, {
      signal: AbortSignal.timeout(3000),
    });
    if (backendRes.ok) {
      const data = await backendRes.json();
      return NextResponse.json(data);
    }
  } catch {
    // Fall through to native fallback
  }

  // HONEST: backend unreachable means NO sites. Never invent a demo site —
  // every downstream call would attribute content to someone else's domain.
  return NextResponse.json([]);
}
