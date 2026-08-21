import logging
from collections import Counter

from .tools.gsc_tools import fetch_active_keywords
from ..database import get_supabase

logger = logging.getLogger("backend.agents.backlink_agent")


def run_backlink_agent(website_id: str) -> dict:
    from .tools.gsc_tools import fetch_active_keywords
    from ..database import get_supabase

    keywords = fetch_active_keywords(website_id)
    if not keywords:
        return {
            "saved": 0,
            "anchor_distribution": {},
            "toxic_anchors": [],
            "error": "No keywords available - connect GSC to enable backlink analysis",
        }

    links = []
    for kw in keywords:
        query = kw.get("query", "")
        links.append(
            {
                "website_id": website_id,
                "source_url": kw.get("url") or kw.get("page"),
                "target_url": kw.get("page"),
                "anchor_text": query,
                "created_at": __import__("datetime").datetime.utcnow().isoformat(),
            }
        )
    if links:
        get_supabase().table("backlinks").insert(links).execute()

    anchors = Counter(link["anchor_text"] for link in links)
    toxic = [a for a, c in anchors.items() if c > 5]

    result = {
        "saved": len(links),
        "anchor_distribution": dict(anchors),
        "toxic_anchors": toxic,
    }
    logger.info("Saved %d backlinks for %s", len(links), website_id)
    return result
