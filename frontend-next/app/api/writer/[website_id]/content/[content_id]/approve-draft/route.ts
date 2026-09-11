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

  // Find content article — no fallback to an unrelated article.
  const article = articlesStore.find((a) => a.id === content_id || a.wp_post_id === Number(content_id));
  if (!article && !body.title && !body.content) {
    return NextResponse.json(
      { success: false, error: "Article not found and no content supplied." },
      { status: 404 }
    );
  }
  const title = article?.title || body.title || "Untitled draft";
  const content = article?.html_content || article?.content || body.content || "";

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

  const draftSite = body.wordpress_site_url || body.site_url || null;
  const draftId = wpDraftResult.wp_post_id || null;
  const editUrl = wpDraftResult.edit_url || null;
  const wpDraftUrl = wpDraftResult.link || null;

  if (article && wpDraftResult.wp_post_id) {
    article.wp_post_id = wpDraftResult.wp_post_id;
    article.edit_url = editUrl || "";
    article.wordpress_url = wpDraftUrl || "";
    article.status = "draft";
  }

  return NextResponse.json({
    success: wpDraftResult.success,
    status: wpDraftResult.success ? "draft" : "failed",
    wp_post_id: draftId,
    edit_url: editUrl,
    wordpress_url: wpDraftUrl,
    real_wp_draft_created: wpDraftResult.success,
    message: wpDraftResult.success
      ? `WordPress draft created (Post ID #${draftId})${draftSite ? ` at ${draftSite}` : ""}.`
      : (wpDraftResult.error || `Draft not created — enter WordPress App Password in /connectors to sync to WP Admin`),
  });
}
