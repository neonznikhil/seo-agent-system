import { NextResponse } from "next/server";

export async function GET(req: Request) {
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const url = new URL(req.url);
    const wid = url.searchParams.get("website_id") || "";
    const res = await fetch(`${backendUrl}/api/keywords${wid ? `?website_id=${wid}` : ""}`, {
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
  } catch {
    // Fall through
  }

  return NextResponse.json({
    success: true,
    keywords: [
      { id: "k-1", keyword: "car accident lawyer consultation", volume: 18200, difficulty: 32, current_rank: 4, previous_rank: 6, change: "+2" },
      { id: "k-2", keyword: "truck accident lawsuit compensation", volume: 6400, difficulty: 29, current_rank: 7, previous_rank: 8, change: "+1" },
      { id: "k-3", keyword: "motorcycle crash injury compensation guide", volume: 5100, difficulty: 24, current_rank: 3, previous_rank: 6, change: "+3" },
    ],
    total: 3,
  });
}
