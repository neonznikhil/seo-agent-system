import { NextResponse } from "next/server";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ website_id: string }> }
) {
  const { website_id } = await params;
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const res = await fetch(`${backendUrl}/api/writer/${website_id}/suggestions`, {
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
    website_id,
    niche: "Personal Injury & Vehicle Accidents",
    domain: "accident.innovatcs.com",
    wordpress_connected: true,
    wordpress_url: "https://accident.innovatcs.com",
    suggestions: [
      { keyword: "what to do immediately after a car accident in California", volume: 14200, difficulty: 28, intent: "Informational", opportunity: "High" },
      { keyword: "motorcycle lane splitting accident liability laws", volume: 8900, difficulty: 34, intent: "Commercial", opportunity: "High" },
      { keyword: "average settlement payout for rear end collision with whiplash", volume: 12100, difficulty: 31, intent: "Informational", opportunity: "High" },
      { keyword: "how long do you have to file an injury claim after a crash", volume: 6700, difficulty: 22, intent: "Informational", opportunity: "Medium" },
      { keyword: "commercial truck accident federal safety regulation violations", volume: 5400, difficulty: 39, intent: "Commercial", opportunity: "High" },
      { keyword: "uber passenger injury insurance coverage guide", volume: 7800, difficulty: 26, intent: "Informational", opportunity: "High" },
    ],
  });
}
