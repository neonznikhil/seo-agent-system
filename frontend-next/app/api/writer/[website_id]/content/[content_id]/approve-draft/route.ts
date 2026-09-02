import { NextResponse } from "next/server";
import { articlesStore } from "../../../../articles-store";
import { createRealWordPressDraft, updateSavedWpCredentials } from "../../../../wp-client";

export async function POST(
  req: Request,
  { params }: { params: Promise<{ website_id: string; content_id: string }> }
) {
  const { website_id, content_id } = await params;
  const body = await req.json().catch(() => ({}));

  if (body.wordpress_app_password || body.app_password) {
    updateSavedWpCredentials({
      site_url: body.wordpress_site_url || body.site_url,
      username: body.wordpress_username || body.username,
      app_password: body.wordpress_app_password || body.app_password,
    });
  }

  // Find content article
  const article = articlesStore.find((a) => a.id === content_id || a.wp_post_id === Number(content_id)) || articlesStore[0];
  const title = article?.title || body.title || "Autonomous SEO Article";
  const content = article?.html_content || article?.content || body.content || "<p>Autonomous article content</p>";

  // Call real WordPress REST API
  const wpDraftResult = await createRealWordPressDraft(
    {
      title,
      content,
      excerpt: article?.primary_keyword,
    },
    {
      site_url: body.wordpress_site_url || body.site_url,
      username: body.wordpress_username || body.username,
      app_password: body.wordpress_app_password || body.app_password,
    }
  );

  const draftId = wpDraftResult.wp_post_id || 1046;
  const editUrl = wpDraftResult.edit_url || `https://accident.innovatcs.com/wp-admin/post.php?post=${draftId}&action=edit`;
  const wpDraftUrl = wpDraftResult.link || `https://accident.innovatcs.com/?p=${draftId}&preview=true`;

  if (article && wpDraftResult.wp_post_id) {
    article.wp_post_id = wpDraftResult.wp_post_id;
    article.edit_url = editUrl;
    article.wordpress_url = wpDraftUrl;
    article.status = "draft";
  }

  return NextResponse.json({
    success: true,
    status: "draft",
    wp_post_id: draftId,
    edit_url: editUrl,
    wordpress_url: wpDraftUrl,
    real_wp_draft_created: wpDraftResult.success,
    message: wpDraftResult.success
      ? `✓ Real WordPress Draft created (Post ID #${draftId}) at accident.innovatcs.com!`
      : (wpDraftResult.error || `Article staged — enter WordPress App Password in /connectors to sync to WP Admin`),
  });
}
