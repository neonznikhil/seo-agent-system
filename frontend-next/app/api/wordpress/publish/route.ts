import { NextResponse } from "next/server";
import { createRealWordPressDraft } from "../../writer/wp-client";

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));

  const wpResult = await createRealWordPressDraft(
    {
      title: body.title || "Autonomous SEO Article",
      content: body.content || "<p>Article content</p>",
      excerpt: body.excerpt,
    },
    {
      site_url: body.wordpress_site_url || body.site_url,
      username: body.wordpress_username || body.username,
      app_password: body.wordpress_app_password || body.app_password,
    }
  );

  // HONEST: report only the WP client result. No invented post IDs/URLs.
  const postId = wpResult.wp_post_id || null;
  const postUrl = wpResult.link || wpResult.edit_url || null;

  return NextResponse.json({
    success: wpResult.success,
    published: wpResult.success,
    real_wp: wpResult.success,
    post_id: postId,
    wp_post_id: postId,
    url: postUrl,
    link: postUrl,
    edit_url: wpResult.edit_url || null,
    message: wpResult.success
      ? `WordPress post created (Post ID #${postId}).`
      : (wpResult.error || `Article NOT published — enter WordPress password in dashboard settings`),
  });
}
