import { NextResponse } from "next/server";

export async function GET(req: Request) {
  // Try proxying to backend first
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const url = new URL(req.url);
    const wid = url.searchParams.get("website_id") || "";
    const backendRes = await fetch(`${backendUrl}/api/connectors/status${wid ? `?website_id=${wid}` : ""}`, {
      headers: {
        "Content-Type": "application/json",
      },
      signal: AbortSignal.timeout(3000),
    });
    if (backendRes.ok) {
      const data = await backendRes.json();
      return NextResponse.json(data);
    }
  } catch {
    // Fall through to native status
  }

  // Native status fallback
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL || "";
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_KEY || "";
  const nvidiaKey = process.env.NVIDIA_API_KEY || "";
  const serperKey = process.env.SERPER_API_KEY || "";

  // HONEST native status: report only what env vars prove. Never claim
  // connected services we have not verified.
  const has = (v: string) => Boolean(v && v.length > 0);
  const supabaseConfigured = has(supabaseUrl) && has(supabaseKey);
  const nvidiaConfigured = has(nvidiaKey);
  const serperConfigured = has(serperKey);

  return NextResponse.json({
    success: true,
    connected_count: 0,
    total_count: 8,
    health_score: null,
    health_label: "Not verified — backend unreachable",
    supabase: {
      connected: false,
      is_configured: supabaseConfigured,
      tables_count: null,
    },
    nvidia: {
      connected: false,
      is_configured: nvidiaConfigured,
      available: null,
      models_count: null,
    },
    serper: {
      connected: false,
      is_configured: serperConfigured,
      fallback_active: false,
    },
    tavily: {
      connected: false,
      is_configured: false,
    },
    gsc: {
      connected: false,
      is_configured: false,
      status_label: "Not connected",
    },
    ga4: {
      connected: false,
      is_configured: false,
      status_label: "Not connected",
    },
    wordpress: {
      connected: false,
      is_configured: false,
      role: null,
      site_url: null,
    },
    slack: {
      connected: false,
      is_configured: false,
    },
  });
}
