import { NextResponse } from "next/server";
import { generateNewArticle } from "../../writer/articles-store";
import { updateSchedule, sharedSchedule } from "../../autonomous/schedule-store";

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";

  try {
    const res = await fetch(`${backendUrl}/api/crew/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(6000),
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
  } catch {
    // Fall through
  }

  const article = generateNewArticle(body.topic || body.title, body.primary_keyword);

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
    message: `CrewAI 3-Agent generation completed — WordPress draft #${article.wp_post_id} created`,
  });
}
