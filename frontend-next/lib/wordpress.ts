import { get, post, del } from "@/lib/api";

export interface WordPressSite {
  id: string;
  name?: string;
  site_url: string;
  username: string;
  source?: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface WordPressCredentials {
  site_url: string;
  username: string;
  app_password: string;
}

export interface WordPressTestResult {
  connected: boolean;
  site_url: string;
  user?: { id?: number; name?: string; slug?: string };
  site?: { name?: string; description?: string; url?: string };
}

export interface WordPressPublishResult {
  wp_post_id: number;
  status: string;
  link: string;
  edit_url: string;
  title: string;
}

export async function testWordPress(creds: WordPressCredentials): Promise<WordPressTestResult> {
  return await post("/wordpress/test", creds);
}

export async function connectWordPress(creds: WordPressCredentials & { name?: string }) {
  return await post("/wordpress/connect", creds);
}

export async function listWordPressSites(): Promise<WordPressSite[]> {
  const res = await get("/wordpress/sites");
  return res?.sites || [];
}

export async function deleteWordPressSite(siteId: string) {
  return await del(`/wordpress/sites/${siteId}`);
}

export async function publishToWordPress(body: {
  title: string;
  content: string;
  status?: string;
  site_id?: string;
}): Promise<WordPressPublishResult> {
  return await post("/wordpress/publish", { status: "draft", ...body });
}
