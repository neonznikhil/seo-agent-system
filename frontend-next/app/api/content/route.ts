import { NextResponse } from "next/server";
import { articlesStore } from "../writer/articles-store";

export async function GET() {
  return NextResponse.json(
    articlesStore.map((a) => ({
      id: a.id,
      title: a.title,
      target_keyword: a.keyword,
      status: a.status,
      word_count: a.word_count,
      seo_score: a.seo_score,
      created_at: a.created_at,
      url: a.wordpress_url,
      wp_post_id: a.wp_post_id,
      edit_url: a.edit_url,
    }))
  );
}
