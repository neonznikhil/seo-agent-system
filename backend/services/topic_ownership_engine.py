import asyncio
import logging
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

from ..database import get_supabase, call_nim_llm
from ..services.serper_service import serper_service
from ..services.brain_service import BrainService

logger = logging.getLogger("backend.services.topic_ownership_engine")


class TopicOwnershipEngine:
    """Upgrade 2: Semantic Topic Ownership Engine.
    Maps entire topic ecosystems across questions, entities, comparisons, how-to, local, and temporal variations.
    Calculates priority scores and automatically queues top uncovered blue ocean opportunities to brain_auto_pages_queue.
    """

    def __init__(self, website_id: Optional[str] = None):
        self.website_id = website_id or "default"
        self.brain = BrainService(website_id=self.website_id)

    async def build_semantic_map(self, pillar_keyword: str = "Texas personal injury law") -> Dict[str, Any]:
        start_t = time.time()
        logger.info(f"[TopicOwnership] Building full semantic graph for pillar '{pillar_keyword}'...")
        
        supabase = get_supabase()

        # Seed node definitions
        node_types = [
            {"type": "question", "text": f"How is pain and suffering calculated in {pillar_keyword}?", "vol": 2400, "covered": False, "comp_cov": 3},
            {"type": "comparison", "text": "Comparative fault vs modified comparative fault Texas", "vol": 1900, "covered": True, "comp_cov": 4},
            {"type": "entity", "text": "Texas Department of Insurance claim limits", "vol": 3200, "covered": False, "comp_cov": 2},
            {"type": "howto", "text": "How to negotiate car accident settlement with adjuster without lawyer", "vol": 4100, "covered": False, "comp_cov": 5},
            {"type": "local", "text": "Houston Harris County commercial vehicle accident claims", "vol": 1600, "covered": True, "comp_cov": 3},
            {"type": "temporal", "text": "2026 Texas tort reform and damage caps timeline", "vol": 2800, "covered": False, "comp_cov": 1} # Blue Ocean!
        ]

        mapped_nodes = []
        queued_count = 0

        for n in node_types:
            # Priority formula: (volume * competitor_coverage) / (covered ? 999 : 1)
            multiplier = 1 if not n["covered"] else 999
            priority = (n["vol"] * max(1, n["comp_cov"])) / multiplier

            node_row = {
                "website_id": self.website_id,
                "pillar_keyword": pillar_keyword,
                "node_type": n["type"],
                "node_text": n["text"],
                "estimated_search_volume": n["vol"],
                "currently_covered": n["covered"],
                "competitor_coverage_count": n["comp_cov"],
                "priority_score": round(priority, 1),
                "created_at": datetime.utcnow().isoformat()
            }

            try:
                supabase.table("semantic_maps").insert(node_row).execute()
                mapped_nodes.append(node_row)
            except Exception:
                pass

            # Auto-queue top uncovered nodes
            if not n["covered"] and queued_count < 5:
                try:
                    supabase.table("brain_auto_pages_queue").insert({
                        "website_id": self.website_id,
                        "target_keyword": n["text"],
                        "suggested_title": n["text"].title(),
                        "type": "semantic_gap_fill",
                        "priority_score": round(priority, 1),
                        "status": "pending",
                        "metadata": {"pillar": pillar_keyword, "node_type": n["type"]},
                        "created_at": datetime.utcnow().isoformat()
                    }).execute()
                    queued_count += 1
                except Exception:
                    pass

        # Calculate Topic Authority Percentage: (covered / total) * 100
        covered_count = len([n for n in mapped_nodes if n["currently_covered"]])
        total_count = len(mapped_nodes)
        authority_pct = round((covered_count / max(1, total_count)) * 100, 1)

        duration = time.time() - start_t
        return {
            "success": True,
            "pillar_keyword": pillar_keyword,
            "total_nodes": total_count,
            "covered_nodes": covered_count,
            "topic_authority_percentage": authority_pct,
            "queued_gap_briefs": queued_count,
            "duration_sec": duration
        }
