export interface GeneratedArticle {
  id: string;
  title: string;
  keyword: string;
  primary_keyword: string;
  content: string;
  html_content: string;
  status: "draft" | "published" | "pending";
  word_count: number;
  seo_score: number;
  created_at: string;
  wp_post_id: number;
  edit_url: string;
  wordpress_url: string;
  author: string;
}

// HONEST STORE: starts empty. Articles appear only after real generation
// runs return data. No seeded demo articles, no hardcoded domains.
export const articlesStore: GeneratedArticle[] = [];

export function generateNewArticle(topic?: string, keyword?: string): GeneratedArticle {
  // Client-side generation is not a real article: record an explicit
  // placeholder that must be replaced by the backend writer pipeline.
  const idNum = Date.now();
  const title = topic && topic.length > 10 ? topic : "Untitled draft — generate via the Writer pipeline";
  const kw = keyword || title;

  const newArt: GeneratedArticle = {
    id: `art-local-${idNum}`,
    title,
    keyword: kw,
    primary_keyword: kw,
    content: "",
    html_content: "",
    status: "draft",
    word_count: 0,
    seo_score: 0,
    created_at: new Date().toISOString(),
    wp_post_id: 0,
    edit_url: "",
    wordpress_url: "",
    author: "local — pending backend generation",
  };

  articlesStore.unshift(newArt);
  return newArt;
}
