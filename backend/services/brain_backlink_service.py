import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from backend.database import get_supabase
from backend.services.brain_service import BrainService
from backend.services.reporting_service import report_problem

logger = logging.getLogger("backend.services.brain_backlink")


async def learn_from_backlink_outcome(
    website_id: str, prospect_id: str, outcome: str
) -> Dict[str, Any]:
    supabase = get_supabase()
    prospect = (
        supabase.table("backlink_prospects")
        .select("*")
        .eq("id", prospect_id)
        .eq("website_id", website_id)
        .single()
        .execute()
        .data
    )
    if not prospect:
        return {"error": "Prospect not found"}

    strategy = prospect.get("strategy", "")
    dr = prospect.get("domain_rating", 0)
    target_url = prospect.get("target_page_url", "")
    keyword = prospect.get("target_keyword", "")
    brain = BrainService(website_id)

    if outcome == "acquired":
        position_improved = False
        if target_url:
            ranks = (
                supabase.table("rank_tracking")
                .select("current_position,created_at")
                .eq("page_url", target_url)
                .order("created_at")
                .execute()
                .data
                or []
            )
            if len(ranks) >= 2:
                start = ranks[0].get("current_position") or 0
                end = ranks[-1].get("current_position") or 0
                if start > 0 and end > 0 and (start - end) >= 3:
                    position_improved = True

        if position_improved:
            try:
                await brain.remember(
                    website_id=website_id,
                    memory_type="outcome",
                    title=f"Broken link DR {dr} resource page boosted pos",
                    content=(
                        f"Strategy {strategy} DR {dr} keyword {keyword} target {target_url} - acquired and position improved 3+"
                    ),
                    source_type="backlink",
                    source_id=prospect_id,
                    confidence=0.9,
                )
            except Exception:
                pass
        else:
            try:
                await brain.remember(
                    website_id=website_id,
                    memory_type="experience",
                    title=f"Acquired backlink {strategy} DR {dr}",
                    content=(
                        f"Strategy {strategy} DR {dr} keyword {keyword} target {target_url} - acquired but no position data yet"
                    ),
                    source_type="backlink",
                    source_id=prospect_id,
                    confidence=0.7,
                )
            except Exception:
                pass

    elif outcome == "rejected":
        try:
            await brain.remember(
                website_id=website_id,
                memory_type="failure",
                title=f"Guest post pitch for {keyword} rejected",
                content=(
                    f"Strategy {strategy} keyword {keyword} target {target_url} - prospect rejected"
                ),
                source_type="backlink",
                source_id=prospect_id,
                confidence=0.6,
            )
        except Exception:
            pass

    elif outcome == "lost":
        try:
            await brain.remember(
                website_id=website_id,
                memory_type="failure",
                title=f"Lost backlink {strategy} DR {dr}",
                content=(
                    f"Strategy {strategy} DR {dr} keyword {keyword} target {target_url} - link lost"
                ),
                source_type="backlink",
                source_id=prospect_id,
                confidence=0.7,
            )
        except Exception:
            pass

    return {"status": "learned", "outcome": outcome}
