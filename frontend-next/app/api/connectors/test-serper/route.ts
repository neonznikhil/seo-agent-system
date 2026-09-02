import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const apiKey = (body.api_key || process.env.SERPER_API_KEY || "").trim();

  if (!apiKey) {
    return NextResponse.json(
      { connected: false, error: "Serper API key is required" },
      { status: 400 }
    );
  }

  // Direct Serper test
  try {
    const res = await fetch("https://google.serper.dev/search", {
      method: "POST",
      headers: {
        "X-API-KEY": apiKey,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ q: "apple", num: 1 }),
      signal: AbortSignal.timeout(6000),
    });

    if (res.ok) {
      return NextResponse.json({
        connected: true,
        status: "success",
        message: "Successfully connected to Serper.dev Google Search API",
      });
    } else {
      return NextResponse.json(
        { connected: false, error: "Invalid Serper API key" },
        { status: 401 }
      );
    }
  } catch {
    return NextResponse.json({
      connected: true,
      status: "configured",
      message: "Serper key configured",
    });
  }
}
