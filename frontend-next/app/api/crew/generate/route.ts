import { NextResponse } from "next/server";
import { generateNewArticle } from "../../writer/articles-store";
import { updateSchedule, sharedSchedule } from "../../autonomous/schedule-store";
import { createRealWordPressDraft, updateSavedWpCredentials } from "../../writer/wp-client";

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));

  if (body.wordpress_app_password || body.app_password) {
    updateSavedWpCredentials({
      site_url: body.wordpress_site_url || body.site_url,
      username: body.wordpress_username || body.username,
      app_password: body.wordpress_app_password || body.app_password,
    });
  }

  const article = generateNewArticle(body.topic || body.title, body.primary_keyword);

  // Attempt real WordPress draft creation
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
    blog_id: article.id,
    content_id: article.id,
    title: article.title,
    article,
    wp_post_id: article.wp_post_id,
    edit_url: article.edit_url,
    wordpress_url: article.wordpress_url,
    real_wp_draft_created: wpDraftResult.success,
    message: wpDraftResult.success
      ? `✓ CrewAI 3-Agent generated & created real WordPress draft #${article.wp_post_id} at accident.innovatcs.com!`
      : (wpDraftResult.error || `Article generated — enter WordPress App Password in /connectors to draft directly to WP Admin`),
  });
}
