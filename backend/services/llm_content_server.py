import logging
from datetime import datetime
from bs4 import BeautifulSoup

logger = logging.getLogger("backend.services.llm_content_server")


async def generate_markdown_version(
    html_content: str,
    title: str,
    target_keyword: str,
    wp_url: str,
    published_at: str,
    website_facts: dict
) -> str:
    soup = BeautifulSoup(html_content, 'html.parser')

    h1 = soup.find('h1')
    title_text = h1.get_text() if h1 else title

    sections = []
    current_section = None

    for tag in soup.find_all(['h2', 'h3', 'p', 'ul', 'ol', 'table']):
        if tag.name == 'h2':
            if current_section:
                sections.append(current_section)
            current_section = {
                "heading": tag.get_text(),
                "content": []
            }
        elif tag.name == 'h3' and current_section:
            current_section["content"].append(f"### {tag.get_text()}")
        elif tag.name == 'p' and current_section:
            text = tag.get_text().strip()
            if text and len(text) > 20:
                current_section["content"].append(text)
        elif tag.name in ['ul', 'ol'] and current_section:
            items = [f"- {li.get_text().strip()}" for li in tag.find_all('li')]
            current_section["content"].extend(items)

    if current_section:
        sections.append(current_section)

    faqs = []
    for h3 in soup.find_all('h3'):
        next_p = h3.find_next_sibling('p')
        if next_p and '?' in h3.get_text():
            faqs.append({
                "question": h3.get_text().strip(),
                "answer": next_p.get_text().strip()
            })

    md_lines = [
        f"# {title_text}",
        "",
        f"**Source:** {wp_url}",
        f"**Published:** {published_at}",
        f"**Last Modified:** {datetime.utcnow().strftime('%Y-%m-%d')}",
        f"**Topic:** {target_keyword}",
        "",
        "---",
        ""
    ]

    for section in sections:
        md_lines.append(f"## {section['heading']}")
        md_lines.append("")
        for content in section["content"]:
            md_lines.append(content)
            md_lines.append("")

    if faqs:
        md_lines.append("## Frequently Asked Questions")
        md_lines.append("")
        for faq in faqs:
            md_lines.append(f"**Q: {faq['question']}**")
            md_lines.append("")
            md_lines.append(f"A: {faq['answer']}")
            md_lines.append("")

    markdown_content = "\n".join(md_lines)

    slug = wp_url.rstrip('/').split('/')[-1] if wp_url else ""

    if slug:
        try:
            from database import get_supabase
            get_supabase().table("article_markdown_cache").upsert({
                "wp_url": wp_url,
                "slug": slug,
                "markdown_content": markdown_content,
                "updated_at": datetime.utcnow().isoformat()
            }, on_conflict="wp_url").execute()
        except Exception as e:
            logger.debug(f"[LLMContentServer] Cache upsert note: {e}")

    return markdown_content


async def get_cached_markdown(slug: str) -> dict:
    try:
        from database import get_supabase
        result = get_supabase().table("article_markdown_cache")\
            .select("markdown_content, updated_at")\
            .eq("slug", slug)\
            .single()\
            .execute()
        if result.data:
            return result.data
    except Exception:
        pass
    return {}
