import { NextResponse } from "next/server";
import { proxyToBackend } from "../_lib/proxy";
import { generateNewArticle } from "../writer/articles-store";
import { updateSchedule, sharedSchedule } from "../autonomous/schedule-store";
import { createRealWordPressDraft, updateSavedWpCredentials } from "../writer/wp-client";

export async function POST(req: Request) {
  try {
    const backendRes = await proxyToBackend("/api/generate", req);
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

  if (body.wordpress_app_password || body.app_password) {
    updateSavedWpCredentials({
      site_url: body.wordpress_site_url || body.site_url,
      username: body.wordpress_username || body.username,
      app_password: body.wordpress_app_password || body.app_password,
    });
  }

  const article = generateNewArticle(body.topic || body.title, body.primary_keyword);

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

  updateSchedule({
    blogs_generated_today: sharedSchedule.blogs_generated_today + 1,
  });

  return NextResponse.json({
    success: true,
    content_id: article.id,
    title: article.title,
    article,
    wp_post_id: article.wp_post_id,
    edit_url: article.edit_url,
    wordpress_url: article.wordpress_url,
    real_wp_draft_created: wpDraftResult.success,
    message: wpDraftResult.success
      ? `✓ Article generated and drafted directly to WordPress (Post ID #${article.wp_post_id})!`
      : (wpDraftResult.error || "Article generated — enter WordPress App Password in /connectors to draft to WP Admin"),
  });
}
