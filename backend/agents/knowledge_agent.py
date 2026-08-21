import logging

from .tools.crawlee_tool import CrawleeTool
from .tools.knowledge_extractor_tool import KnowledgeExtractorTool
from .tools.tone_analyzer_tool import ToneAnalyzerTool
from ..database import get_supabase, get_embedding
from .tools.shared_utils import is_homepage

logger = logging.getLogger("backend.agents.knowledge_agent")


def run_knowledge_agent(website_id: str, homepage_url: str, max_pages: int = 20) -> dict:
    crawlee = CrawleeTool()
    crawlee.set_website_id(website_id)
    crawlee.set_agent_name("knowledge_agent")
    
    knowledge_extractor = KnowledgeExtractorTool()
    knowledge_extractor.set_website_id(website_id)
    knowledge_extractor.set_agent_name("knowledge_agent")
    
    tone_analyzer = ToneAnalyzerTool()
    tone_analyzer.set_website_id(website_id)
    tone_analyzer.set_agent_name("knowledge_agent")

    pages = [homepage_url]
    for i in range(1, min(max_pages, 10)):
        pages.append(f"{homepage_url.rstrip('/')}/page/{i+1}")

    saved_count = 0
    for url in pages:
        content = crawlee._run(url)
        if not content or content.startswith("# Error"):
            continue
        try:
            emb = get_embedding(content[:1000], website_id=website_id)
            get_supabase().table("website_knowledge").insert({
                "website_id": website_id,
                "url": url,
                "content": content,
                "embedding": emb,
                "created_at": __import__("datetime").datetime.utcnow().isoformat(),
            }).execute()
            saved_count += 1
        except Exception as e:
            logger.error("Failed to save knowledge for %s: %s", url, e)

    homepage_content = crawlee._run(homepage_url)
    tone_result = tone_analyzer._run(homepage_content)
    extract_result = knowledge_extractor._run(homepage_content)

    logger.info("Knowledge agent completed for %s: saved %s pages", website_id, saved_count)
    return {"pages_saved": saved_count, "tone": tone_result, "knowledge": extract_result}