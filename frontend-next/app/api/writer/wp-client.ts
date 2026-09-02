// Server-side WordPress REST API helper

export interface WpCredentials {
  site_url: string;
  username: string;
  app_password: string;
}

// In-memory credentials cache for server
export const savedWpCredentials: WpCredentials = {
  site_url: process.env.WORDPRESS_SITE_URL || "https://accident.innovatcs.com",
  username: process.env.WORDPRESS_USERNAME || "admin",
  app_password: process.env.WORDPRESS_APP_PASSWORD || "",
};

export function updateSavedWpCredentials(creds: Partial<WpCredentials>) {
  if (creds.site_url) savedWpCredentials.site_url = creds.site_url.trim().replace(/\/+$/, "");
  if (creds.username) savedWpCredentials.username = creds.username.trim();
  if (creds.app_password) savedWpCredentials.app_password = creds.app_password.trim();
  return savedWpCredentials;
}

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
  const siteUrl = (overrideCreds?.site_url || savedWpCredentials.site_url || "https://accident.innovatcs.com").trim().replace(/\/+$/, "");
  const username = (overrideCreds?.username || savedWpCredentials.username || "admin").trim();
  const appPassword = (overrideCreds?.app_password || savedWpCredentials.app_password || "").trim();

  if (!siteUrl || !username || !appPassword || appPassword.includes("••••")) {
    return {
      success: false,
      error: "WordPress application password not configured. Please enter your WordPress App Password in /connectors.",
    };
  }

  // Support passwords with or without spaces
  const passwordsToTry = [appPassword, appPassword.replace(/\s+/g, "")];
  const endpoints = [
    `${siteUrl}/wp-json/wp/v2/posts`,
    `${siteUrl}/?rest_route=/wp/v2/posts`,
  ];

  for (const pwd of passwordsToTry) {
    const auth = Buffer.from(`${username}:${pwd}`).toString("base64");
    for (const ep of endpoints) {
      try {
        const res = await fetch(ep, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Basic ${auth}`,
            "User-Agent": "Mozilla/5.0 RankForge/1.0",
          },
          body: JSON.stringify({
            title: article.title,
            content: article.content,
            status: "draft",
            excerpt: article.excerpt || "",
          }),
          signal: AbortSignal.timeout(15000),
        });

        if (res.ok) {
          const postData = await res.json();
          const draftId = postData.id;
          const editUrl = `${siteUrl}/wp-admin/post.php?post=${draftId}&action=edit`;
          const link = postData.link || `${siteUrl}/?p=${draftId}&preview=true`;
          return {
            success: true,
            wp_post_id: draftId,
            edit_url: editUrl,
            link,
          };
        } else {
          const errText = await res.text().catch(() => "");
          console.warn(`WordPress create draft error ${res.status} at ${ep}: ${errText.slice(0, 200)}`);
        }
      } catch (err: any) {
        console.warn(`WordPress connection exception to ${ep}: ${err.message}`);
      }
    }
  }

  return {
    success: false,
    error: "WordPress REST API rejected the credentials. Verify the user is Administrator or Editor and the App Password is active in WP Admin > Users > Profile.",
  };
}
