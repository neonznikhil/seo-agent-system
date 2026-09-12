import { NextResponse } from "next/server";
import { proxyToBackend } from "../../../_lib/proxy";
import { generateNewArticle } from "../../articles-store";
import { updateSchedule, sharedSchedule } from "../../../autonomous/schedule-store";
import { createRealWordPressDraft, updateSavedWpCredentials } from "../../wp-client";

export async function POST(
  req: Request,
  { params }: { params: Promise<{ website_id: string }> }
) {
  const { website_id } = await params;
  const backendPath = `/api/writer/${encodeURIComponent(website_id)}/generate`;

  try {
    const backendRes = await proxyToBackend(backendPath, req);
    if (backendRes) {
      const text = await backendRes.text();
      return new NextResponse(text, {
        status: backendRes.status,
        headers: {
          "Content-Type": backendRes.headers.get("content-type") || "application/json",
        },
      });
    }
  } catch {
    // Fall through to local stub if proxy fails or backend is local/undefined
  }

  const body = await req.json().catch(() => ({}));
  if (!body?.topic && !body?.title) {
    return NextResponse.json({ success: false, error: "topic or title is required" }, { status: 400 });
  }

  // Update WordPress credentials if supplied in the request body
  if (body.wordpress_app_password || body.app_password) {
    updateSavedWpCredentials({
      site_url: body.wordpress_site_url || body.site_url,
      username: body.wordpress_username || body.username,
      app_password: body.wordpress_app_password || body.app_password,
    });
  }

  // 1. Generate rich article content
  const article = generateNewArticle(body.title || body.topic, body.primary_keyword || body.keyword);

  // 2. Attempt real WordPress draft creation
  const wpDraftResult = await createRealWordPressDraft(
    {
      title: article.title,
      content: article.html_content || article.content,
      excerpt: article.primary_keyword,
    },
    {
      site_url: body.wordpress_site_url || body.site_url,
      username: body.wordpress_username || body.username,
      app_password: body.wordpress_app_password || body.app_password,
    }
  );

  if (wpDraftResult.success && wpDraftResult.wp_post_id) {
    article.wp_post_id = wpDraftResult.wp_post_id;
    article.edit_url = wpDraftResult.edit_url || article.edit_url;
    article.wordpress_url = wpDraftResult.link || article.wordpress_url;
  }

  // 3. Increment schedule counter
  updateSchedule({
    blogs_generated_today: sharedSchedule.blogs_generated_today + 1,
  });

  return NextResponse.json({
    success: true,
    job_id: article.id,
    content_id: article.id,
    status: "draft",
    title: article.title,
    article,
    wp_post_id: article.wp_post_id,
    edit_url: article.edit_url,
    wordpress_url: article.wordpress_url,
    real_wp_draft_created: wpDraftResult.success,
    message: wpDraftResult.success
      ? `WordPress draft created (Post ID #${wpDraftResult.wp_post_id})${wpDraftResult.edit_url ? ` — ${wpDraftResult.edit_url}` : ""}`
      : (wpDraftResult.error || `Article generated — enter WordPress App Password in /connectors to sync to WP Admin`),
  });
}
