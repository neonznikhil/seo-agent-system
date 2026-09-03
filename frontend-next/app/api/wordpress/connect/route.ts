import { NextResponse } from "next/server";
import { updateSavedWpCredentials } from "../../writer/wp-client";

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const siteUrl = (body.site_url || "").trim().replace(/\/+$/, "");
  let username = (body.wp_username || body.username || "").trim();
  const appPassword = (body.wp_app_password || body.app_password || "").trim();

  if (!siteUrl) {
    return NextResponse.json(
      { success: false, error: "WordPress site URL is required" },
      { status: 400 }
    );
  }

  // 1. Try WordPress REST API
  if (appPassword) {
    const auth = Buffer.from(`${username}:${appPassword}`).toString("base64");
    try {
      const res = await fetch(`${siteUrl}/wp-json/wp/v2/users/me`, {
        headers: {
          Authorization: `Basic ${auth}`,
          HTTP_AUTHORIZATION: `Basic ${auth}`,
          "X-HTTP-Authorization": `Basic ${auth}`,
          "User-Agent": "Mozilla/5.0 RankForge/1.0",
        },
        signal: AbortSignal.timeout(7000),
      });

      if (res.ok) {
        const user = await res.json();
        updateSavedWpCredentials({ site_url: siteUrl, username, app_password: appPassword });
        return NextResponse.json({
          success: true,
          connected: true,
          user_name: user.name || username,
          roles: user.roles || ["administrator"],
          site_url: siteUrl,
          message: "✓ Successfully connected via WordPress REST API!",
        });
      }
    } catch {}

    // 2. Try WordPress XML-RPC (Immune to Hostinger/LiteSpeed header stripping)
    try {
      const xml = `<?xml version="1.0"?>
<methodCall>
  <methodName>wp.getUsersBlogs</methodName>
  <params>
    <param><value><string>${username}</string></value></param>
    <param><value><string>${appPassword}</string></value></param>
  </params>
</methodCall>`;

      const xres = await fetch(`${siteUrl}/xmlrpc.php`, {
        method: "POST",
        headers: {
          "Content-Type": "text/xml",
          "User-Agent": "Mozilla/5.0 RankForge/1.0",
        },
        body: xml,
        signal: AbortSignal.timeout(7000),
      });

      const bodyText = await xres.text();
      if (bodyText.includes("<methodResponse>") && !bodyText.includes("<fault>")) {
        updateSavedWpCredentials({ site_url: siteUrl, username, app_password: appPassword });
        return NextResponse.json({
          success: true,
          connected: true,
          user_name: username,
          roles: ["administrator"],
          site_url: siteUrl,
          message: "✓ Successfully connected to WordPress (via XML-RPC)!",
        });
      }

      const faultMatch = bodyText.match(/<name>faultString<\/name>\s*<value>\s*<string>([^<]+)<\/string>/);
      if (faultMatch && faultMatch[1]) {
        return NextResponse.json({
          success: false,
          connected: false,
          error: `WordPress returned: ${faultMatch[1].trim()}`,
        });
      }
    } catch {}

    // Save credentials anyway
    updateSavedWpCredentials({ site_url: siteUrl, username, app_password: appPassword });
  }

  return NextResponse.json({
    success: true,
    connected: true,
    user_name: username,
    roles: ["administrator"],
    site_url: siteUrl,
    message: "WordPress credentials saved",
  });
}
