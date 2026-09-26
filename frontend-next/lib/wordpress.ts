import { post, put, buildUrl } from "@/lib/api";

/** Name the failing step plus backend target so 404s point at env, not code. */
function stepError(step: string, path: string, err: any): Error {
  const base = buildUrl(path);
  const detail = err?.message || String(err);
  return new Error(`${step} failed [${base}]: ${detail}`);
}

export interface WpCreds {
  siteUrl: string;
  username: string;
  appPassword: string;
}

/** Single canonical WordPress connect flow used by /websites and /connectors. */
export async function saveWordPressForSite(websiteId: string, creds: WpCreds) {
  const siteUrl = creds.siteUrl.trim();
  const username = creds.username.trim();
  const appPassword = creds.appPassword.trim();
  if (!websiteId) throw new Error("Select website first");
  if (!siteUrl || !username || !appPassword) throw new Error("Site URL, username, app password required");

  try {
    await put(`/api/websites/${websiteId}`, {
      wordpress_user: username,
      cms_user: username,
      wordpress_password: appPassword,
      app_password: appPassword,
      wordpress_url: siteUrl,
      cms_url: siteUrl,
      url: siteUrl,
    } as any);
  } catch (e: any) {
    throw stepError("Save creds", `/api/websites/${websiteId}`, e);
  }

  try {
    return await post(`/api/wordpress/${websiteId}/test`, {
      url: siteUrl,
      wordpress_url: siteUrl,
      username,
      wordpress_user: username,
      password: appPassword,
      wordpress_password: appPassword,
    });
  } catch (e: any) {
    throw stepError("Verify connection", `/api/wordpress/${websiteId}/test`, e);
  }
}

export async function testWordPressForSite(websiteId: string, creds: WpCreds) {
  return saveWordPressForSite(websiteId, creds);
}
