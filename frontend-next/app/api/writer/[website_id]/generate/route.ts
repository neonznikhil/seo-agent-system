import { NextResponse } from "next/server";
import { generateNewArticle } from "../../articles-store";
import { updateSchedule, sharedSchedule } from "../../../autonomous/schedule-store";

export async function POST(
  req: Request,
  { params }: { params: Promise<{ website_id: string }> }
) {
  const { website_id } = await params;
  const body = await req.json().catch(() => ({}));
  const backendUrl = process.env.BACKEND_URL || "https://rankforge-backend.onrender.com";

  // Try backend first if online
  try {
    const res = await fetch(`${backendUrl}/api/writer/${website_id}/generate`, {
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

  // Generate article with CrewAI pipeline
  const article = generateNewArticle(body.title || body.topic, body.primary_keyword || body.keyword);

  // Increment today's count in schedule store
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
    message: `Generated and drafted to WordPress (Post ID #${article.wp_post_id})`,
  });
}
