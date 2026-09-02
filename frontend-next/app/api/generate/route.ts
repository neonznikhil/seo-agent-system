import { NextResponse } from "next/server";
import { generateNewArticle } from "../writer/articles-store";
import { updateSchedule, sharedSchedule } from "../autonomous/schedule-store";

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const article = generateNewArticle(body.topic || body.title, body.primary_keyword);

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
    message: "Article generated and drafted to WordPress successfully",
  });
}
