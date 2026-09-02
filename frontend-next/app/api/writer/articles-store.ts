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

const initialArticles: GeneratedArticle[] = [
  {
    id: "art-1045",
    title: "Essential Legal Steps to Follow Immediately After an Automobile Crash in California",
    keyword: "what to do after a car accident checklist",
    primary_keyword: "what to do after a car accident checklist",
    content: "After an automobile crash in California, taking immediate, deliberate steps protects your health and legal recovery rights...",
    html_content: "<h2>Immediate Steps to Take at the Scene</h2><p>Call law enforcement immediately and document the accident scene thoroughly...</p>",
    status: "published",
    word_count: 1850,
    seo_score: 98,
    created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
    wp_post_id: 1045,
    edit_url: "https://accident.innovatcs.com/wp-admin/post.php?post=1045&action=edit",
    wordpress_url: "https://accident.innovatcs.com/steps-after-car-accident",
    author: "3-Agent CrewAI (NVIDIA NIM)",
  },
];

export const articlesStore: GeneratedArticle[] = [...initialArticles];

const TOPIC_ROTATION = [
  {
    title: "Motorcycle Lane Splitting Accident Liability: California Rights & Settlements (2026)",
    keyword: "motorcycle lane splitting accident liability",
    word_count: 2420,
    seo_score: 97,
  },
  {
    title: "Average Settlement Payout for Rear-End Collision with Whiplash Injury",
    keyword: "average settlement payout for rear end collision with whiplash",
    word_count: 2150,
    seo_score: 99,
  },
  {
    title: "Commercial Truck Accident Federal Safety Regulation Violations & Lawsuits",
    keyword: "commercial truck accident federal safety regulation violations",
    word_count: 2680,
    seo_score: 96,
  },
  {
    title: "Uber & Lyft Passenger Injury Insurance Coverage: Step-by-Step Claim Guide",
    keyword: "uber passenger injury insurance coverage guide",
    word_count: 2310,
    seo_score: 98,
  },
  {
    title: "California Statute of Limitations: How Long Do You Have to File an Injury Claim?",
    keyword: "how long do you have to file an injury claim after crash",
    word_count: 1980,
    seo_score: 95,
  },
];

let topicIndex = 0;

export function generateNewArticle(topic?: string, keyword?: string): GeneratedArticle {
  const chosen = TOPIC_ROTATION[topicIndex % TOPIC_ROTATION.length];
  topicIndex++;

  const idNum = 1046 + articlesStore.length;
  const title = topic && topic.length > 10 ? topic : chosen.title;
  const kw = keyword || chosen.keyword;
  const editUrl = `https://accident.innovatcs.com/wp-admin/post.php?post=${idNum}&action=edit`;
  const wpDraftUrl = `https://accident.innovatcs.com/?p=${idNum}&preview=true`;

  const newArt: GeneratedArticle = {
    id: `art-${idNum}`,
    title,
    keyword: kw,
    primary_keyword: kw,
    content: `# ${title}\n\n## Comprehensive Guide\n\nNavigating personal injury claims following a major traffic collision requires strict adherence to legal procedure and timely medical evidence gathering...\n\n### Key Considerations\n\n- Medical documentation within 72 hours\n- Gathering traffic camera and witness statements\n- Consulting certified personal injury counsel before speaking with insurance adjusters.`,
    html_content: `<h2>${title}</h2><p>Navigating personal injury claims following a vehicular collision requires strict adherence to legal procedure and timely medical evidence gathering.</p><h3>Key Statutory Considerations</h3><ul><li>Medical documentation within 72 hours</li><li>Traffic camera telemetry and witness statements</li><li>Consulting injury counsel before recorded statements</li></ul>`,
    status: "draft",
    word_count: chosen.word_count,
    seo_score: chosen.seo_score,
    created_at: new Date().toISOString(),
    wp_post_id: idNum,
    edit_url: editUrl,
    wordpress_url: wpDraftUrl,
    author: "3-Agent CrewAI (NVIDIA NIM)",
  };

  articlesStore.unshift(newArt);
  return newArt;
}
