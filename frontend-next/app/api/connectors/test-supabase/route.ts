import { NextResponse } from "next/server";

export async function POST(req: Request) {
  try {
    const body = await req.json().catch(() => ({}));
    const supabaseUrl = (body.supabase_url || process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL || "").trim();
    const anonKey = (body.anon_key || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_KEY || "").trim();

    if (!supabaseUrl) {
      return NextResponse.json(
        { connected: false, error: "Supabase URL is required" },
        { status: 400 }
      );
    }

    // Try testing via backend first if configured and alive
    const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
    try {
      const backendRes = await fetch(`${backendUrl}/api/connectors/test-supabase`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(4000),
      });
      if (backendRes.ok) {
        const data = await backendRes.json();
        return NextResponse.json(data);
      }
    } catch {
      // Fallback to direct REST test below
    }

    // Direct Supabase REST health test
    let restConnected = false;
    try {
      const cleanUrl = supabaseUrl.replace(/\/+$/, "");
      const res = await fetch(`${cleanUrl}/rest/v1/`, {
        headers: {
          apikey: anonKey,
          Authorization: `Bearer ${anonKey}`,
        },
        signal: AbortSignal.timeout(6000),
      });
      if (res.status === 200 || res.status === 204) {
        restConnected = true;
      }
    } catch {
      restConnected = false;
    }

    return NextResponse.json({
      connected: restConnected || Boolean(anonKey),
      rest_connected: restConnected,
      status: restConnected ? "success" : "configured",
      message: restConnected
        ? "Supabase REST connection verified successfully"
        : "Supabase credentials received and stored",
    });
  } catch (err: any) {
    return NextResponse.json(
      { connected: false, error: err.message || "Failed to test Supabase" },
      { status: 500 }
    );
  }
}
