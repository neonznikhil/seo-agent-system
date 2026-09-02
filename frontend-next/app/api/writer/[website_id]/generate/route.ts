import { NextResponse } from "next/server";
import { generateNewArticle } from "../../articles-store";
import { updateSchedule, sharedSchedule } from "../../../autonomous/schedule-store";
import { createRealWordPressDraft, updateSavedWpCredentials } from "../../wp-client";

export async function POST(
  req: Request,
  { params }: { params: Promise<{ website_id: string }> }
) {
  const { website_id } = await params;
  const body = await req.json().catch(() => ({}));

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
      ? `✓ Real WordPress draft created (Post ID #${wpDraftResult.wp_post_id}) in accident.innovatcs.com WP Admin!`
      : (wpDraftResult.error || `Article generated — enter WordPress App Password in /connectors to sync to WP Admin`),
  });
}
