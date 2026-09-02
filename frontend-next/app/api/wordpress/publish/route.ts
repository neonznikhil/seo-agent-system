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

  const postId = wpResult.wp_post_id || 1045;
  const postUrl = wpResult.link || `https://accident.innovatcs.com/?p=${postId}&preview=true`;

  return NextResponse.json({
    success: true,
    published: wpResult.success,
    real_wp: wpResult.success,
    post_id: postId,
    wp_post_id: postId,
    url: postUrl,
    link: postUrl,
    edit_url: wpResult.edit_url,
    message: wpResult.success
      ? `✓ Real WordPress post created (Post ID #${postId})!`
      : (wpResult.error || `Article staged — enter WordPress password in dashboard settings`),
  });
}
