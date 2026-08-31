"""RankForge Internal Linking Engine.
Indexes published WordPress blogs by headings and key phrases,
and automatically injects real contextual internal links into new articles.
"""

import re
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

from ..database import get_supabase
from ..services.local_store import (
    save_local_internal_link,
    list_local_internal_links,
)

logger = logging.getLogger("backend.services.internal_links")


async def index_blog_for_linking(
    blog_id: str,
    website_id: str,
    title: str,
    url: str,
    target_keyword: str,
    html_content: str,
) -> Dict[str, Any]:
    """
    Extracts key topics from the blog and stores them
    so other articles can link to this one.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract all H2 headings as linkable topics
    headings = [h.get_text().strip() for h in soup.find_all('h2') if h.get_text().strip()]
    
    # Extract key phrases from first paragraph
    first_para = None
    for p in soup.find_all('p'):
        if not p.find_parent('div', class_='tldr-block') and len(p.get_text().strip()) > 30:
            first_para = p
            break
    first_para_text = first_para.get_text().strip() if first_para else ""
    
    record = {
        "website_id": website_id,
        "blog_id": blog_id,
        "url": url,
        "title": title,
        "target_keyword": target_keyword,
        "linkable_topics": headings,
        "summary": first_para_text[:300],
        "published_at": datetime.utcnow().isoformat(),
    }
    
    try:
        supabase = get_supabase()
        supabase.table("internal_link_index").insert(record).execute()
    except Exception as e:
        logger.debug(f"[InternalLinks] Supabase index insert note (using local store): {e}")

    saved = save_local_internal_link(record)
    logger.info(f"[InternalLinks] Indexed '{title}' ({url}) with {len(headings)} topics for internal linking.")
    return saved


async def inject_internal_links(
    html_content: str,
    website_id: str,
    max_links: int = 4,
) -> str:
    """
    Finds opportunities in the article to link to other
    published articles on the same site.
    Inserts max 3-5 internal links per article.
    """
    if not html_content or not website_id:
        return html_content

    # Get published articles index from DB / local store
    articles: List[Dict[str, Any]] = []
    try:
        supabase = get_supabase()
        res = (
            supabase.table("internal_link_index")
            .select("url, title, target_keyword, linkable_topics")
            .eq("website_id", website_id)
            .order("published_at", desc=True)
            .limit(20)
            .execute()
        )
        articles = res.data or []
    except Exception:
        pass

    local_articles = list_local_internal_links(website_id=website_id, limit=20)
    known_urls = {a.get("url") for a in articles if a.get("url")}
    for la in local_articles:
        if la.get("url") and la.get("url") not in known_urls:
            articles.append(la)
            known_urls.add(la.get("url"))

    if not articles:
        return html_content  # No published articles to link to yet

    try:
        soup = BeautifulSoup(html_content, 'html.parser')
    except Exception:
        return html_content

    links_added = 0
    used_urls = set()
    
    # Don't inject inside TLDR block or headings
    for para in soup.find_all('p'):
        if links_added >= max_links:
            break
        if para.find_parent('div', class_='tldr-block'):
            continue
            
        para_text = para.get_text().lower()
        
        for article in articles:
            if links_added >= max_links:
                break
            art_url = article.get("url")
            if not art_url or art_url in used_urls:
                continue
                
            keyword = (article.get("target_keyword") or "").lower().strip()
            if not keyword:
                continue

            # Stop words to ignore during word match
            stop_words = {"the", "and", "for", "with", "from", "that", "this", "your", "have", "are", "was", "were", "what", "how", "why"}
            keyword_words = [w for w in re.findall(r'[a-zA-Z]{4,}', keyword) if w not in stop_words]
            if not keyword_words:
                continue
                
            # Check if keyword or multiple related words appear in paragraph
            matches = sum(1 for w in keyword_words if w in para_text)
            
            # Check if paragraph doesn't already contain this link
            if matches >= 2 and art_url not in str(para):
                para_str = str(para)
                
                # Look for matching multi-word phrase first, or fallback to key word
                replaced = False
                # Try 2-word combinations
                for i in range(len(keyword_words) - 1):
                    phrase = f"{keyword_words[i]} {keyword_words[i+1]}"
                    if phrase in para_text:
                        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
                        linked_str = pattern.sub(f'<a href="{art_url}">{phrase}</a>', para_str, count=1)
                        if linked_str != para_str:
                            para.replace_with(BeautifulSoup(linked_str, 'html.parser'))
                            links_added += 1
                            used_urls.add(art_url)
                            replaced = True
                            break
                
                if not replaced:
                    for word in keyword_words:
                        if len(word) > 4 and word in para_text:
                            pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
                            linked_str = pattern.sub(f'<a href="{art_url}">{word}</a>', para_str, count=1)
                            if linked_str != para_str:
                                para.replace_with(BeautifulSoup(linked_str, 'html.parser'))
                                links_added += 1
                                used_urls.add(art_url)
                                break
    
    return str(soup)
