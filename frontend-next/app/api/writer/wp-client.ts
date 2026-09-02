import fs from "fs";
import path from "path";

export interface WpCredentials {
  site_url: string;
  username: string;
  app_password: string;
}

const CREDENTIALS_FILE = path.join(process.cwd(), ".wp_credentials.json");

function loadStoredCredentials(): WpCredentials {
  const fallback: WpCredentials = {
    site_url: process.env.WORDPRESS_SITE_URL || "https://accident.innovatcs.com",
    username: process.env.WORDPRESS_USERNAME || "admin",
    app_password: process.env.WORDPRESS_APP_PASSWORD || "",
  };

  try {
    if (fs.existsSync(CREDENTIALS_FILE)) {
      const data = JSON.parse(fs.readFileSync(CREDENTIALS_FILE, "utf-8"));
      return {
        site_url: data.site_url || fallback.site_url,
        username: data.username || fallback.username,
        app_password: data.app_password || fallback.app_password,
      };
    }
  } catch {}
  return fallback;
}

export const savedWpCredentials: WpCredentials = loadStoredCredentials();

export function updateSavedWpCredentials(creds: Partial<WpCredentials>) {
  if (creds.site_url) savedWpCredentials.site_url = creds.site_url.trim().replace(/\/+$/, "");
  if (creds.username) savedWpCredentials.username = creds.username.trim();
  if (creds.app_password) savedWpCredentials.app_password = creds.app_password.trim();

  try {
    fs.writeFileSync(CREDENTIALS_FILE, JSON.stringify(savedWpCredentials, null, 2), "utf-8");
  } catch {}

  return savedWpCredentials;
}

/**
 * Escape XML special characters
 */
function escapeXml(unsafe: string): string {
  return (unsafe || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/**
 * Create a draft in WordPress using XML-RPC fallback
 */
async function postViaXmlRpc(
  siteUrl: string,
  username: string,
  password: string,
  article: { title: string; content: string; excerpt?: string }
): Promise<{ success: boolean; wp_post_id?: number; edit_url?: string; link?: string; error?: string }> {
  const xmlrpcUrl = `${siteUrl.replace(/\/+$/, "")}/xmlrpc.php`;
  const xmlPayload = `<?xml version="1.0"?>
<methodCall>
  <methodName>wp.newPost</methodName>
  <params>
    <param><value><int>1</int></value></param>
    <param><value><string>${escapeXml(username)}</string></value></param>
    <param><value><string>${escapeXml(password)}</string></value></param>
    <param>
      <value>
        <struct>
          <member><name>post_title</name><value><string>${escapeXml(article.title)}</string></value></member>
          <member><name>post_content</name><value><string>${escapeXml(article.content)}</string></value></member>
          <member><name>post_status</name><value><string>draft</string></value></member>
          <member><name>post_excerpt</name><value><string>${escapeXml(article.excerpt || "")}</string></value></member>
        </struct>
      </value>
    </param>
  </params>
</methodCall>`;

  try {
    const res = await fetch(xmlrpcUrl, {
      method: "POST",
      headers: {
        "Content-Type": "text/xml",
        "User-Agent": "Mozilla/5.0 RankForge/1.0",
      },
      body: xmlPayload,
      signal: AbortSignal.timeout(15000),
    });

    const bodyText = await res.text();

    // Check for success: <value><string>1234</string></value> or <value><int>1234</int></value>
    const match = bodyText.match(/<value>\s*<(?:string|int)>(\d+)<\/(?:string|int)>\s*<\/value>/);
    if (match && match[1]) {
      const draftId = parseInt(match[1], 10);
      return {
        success: true,
        wp_post_id: draftId,
        edit_url: `${siteUrl}/wp-admin/post.php?post=${draftId}&action=edit`,
        link: `${siteUrl}/?p=${draftId}&preview=true`,
      };
    }

    // Check for faultString
    const faultMatch = bodyText.match(/<name>faultString<\/name>\s*<value>\s*<string>([^<]+)<\/string>/);
    if (faultMatch && faultMatch[1]) {
      return {
        success: false,
        error: faultMatch[1].trim(),
      };
    }
  } catch (err: any) {
    return {
      success: false,
      error: `XML-RPC connection error: ${err.message}`,
    };
  }

  return {
    success: false,
    error: "WordPress XML-RPC did not return a valid post ID.",
  };
}

/**
 * Robust draft creation: tries REST API with multiple header variations, then falls back to XML-RPC
 */
export async function createRealWordPressDraft(
  article: {
    title: string;
    content: string;
    excerpt?: string;
  },
  overrideCreds?: Partial<WpCredentials>
): Promise<{
  success: boolean;
  wp_post_id?: number;
  edit_url?: string;
  link?: string;
  error?: string;
}> {
  const currentCreds = loadStoredCredentials();
  const siteUrl = (overrideCreds?.site_url || currentCreds.site_url || "https://accident.innovatcs.com").trim().replace(/\/+$/, "");
  const username = (overrideCreds?.username || currentCreds.username || "admin").trim();
  const appPassword = (overrideCreds?.app_password || currentCreds.app_password || "").trim();

  if (!siteUrl || !username || !appPassword || appPassword.includes("••••")) {
    return {
      success: false,
      error: "WordPress credentials not configured. Please enter your WordPress password or Application Password in the dashboard.",
    };
  }

  // Update in-memory / persistent file if new credentials were provided
  if (overrideCreds?.app_password) {
    updateSavedWpCredentials(overrideCreds);
  }

  const passwordsToTry = [appPassword, appPassword.replace(/\s+/g, "")];
  const endpoints = [
    `${siteUrl}/wp-json/wp/v2/posts`,
    `${siteUrl}/?rest_route=/wp/v2/posts`,
  ];

  // 1. First Attempt: REST API with comprehensive headers for LiteSpeed / Hostinger
  for (const pwd of passwordsToTry) {
    const auth = Buffer.from(`${username}:${pwd}`).toString("base64");
    for (const ep of endpoints) {
      try {
        const res = await fetch(ep, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Basic ${auth}`,
            HTTP_AUTHORIZATION: `Basic ${auth}`,
            "X-HTTP-Authorization": `Basic ${auth}`,
            "Redirect-HTTP-Authorization": `Basic ${auth}`,
            "User-Agent": "Mozilla/5.0 RankForge/1.0",
          },
          body: JSON.stringify({
            title: article.title,
            content: article.content,
            status: "draft",
            excerpt: article.excerpt || "",
          }),
          signal: AbortSignal.timeout(12000),
        });

        if (res.ok) {
          const postData = await res.json();
          const draftId = postData.id;
          return {
            success: true,
            wp_post_id: draftId,
            edit_url: `${siteUrl}/wp-admin/post.php?post=${draftId}&action=edit`,
            link: postData.link || `${siteUrl}/?p=${draftId}&preview=true`,
          };
        }
      } catch (err) {
        // Fall through to next endpoint / XML-RPC
      }
    }
  }

  // 2. Second Attempt: XML-RPC fallback (Immune to LiteSpeed HTTP Authorization header stripping)
  for (const pwd of passwordsToTry) {
    const xmlRpcResult = await postViaXmlRpc(siteUrl, username, pwd, article);
    if (xmlRpcResult.success) {
      return xmlRpcResult;
    }
    if (xmlRpcResult.error && !xmlRpcResult.error.includes("connection error")) {
      // Return the specific WordPress error (e.g., "Incorrect username or password")
      return {
        success: false,
        error: `WordPress error: ${xmlRpcResult.error}`,
      };
    }
  }

  return {
    success: false,
    error: "WordPress authentication failed. Please verify your WordPress username and password/Application Password in the settings.",
  };
}
