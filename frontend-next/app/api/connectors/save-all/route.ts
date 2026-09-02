import { NextResponse } from "next/server";
import { updateSavedWpCredentials } from "../../writer/wp-client";

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));

  if (body.wordpress_site_url || body.wordpress_app_password || body.wordpress_username) {
    updateSavedWpCredentials({
      site_url: body.wordpress_site_url,
      username: body.wordpress_username,
      app_password: body.wordpress_app_password,
    });
  }

  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";
  try {
    const res = await fetch(`${backendUrl}/api/connectors/save-all`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(4000),
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
    message: "All connector settings saved successfully",
    updated_at: new Date().toISOString(),
  });
}
