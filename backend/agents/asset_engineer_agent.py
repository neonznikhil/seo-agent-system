import asyncio
import logging
import uuid
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

from ..database import get_supabase, call_nim_llm
from ..services.brain_service import BrainService

logger = logging.getLogger("backend.agents.asset_engineer_agent")


class AssetEngineerAgent:
    """Agent 2: Runs every Monday at 10:00 IST after OpportunityScoutAgent.
    Reads discovered opportunities, determines the linkable asset required, and briefs it into brain_auto_pages_queue.
    """

    def __init__(self, website_id: Optional[str] = None):
        self.website_id = website_id or "default"
        self.brain = BrainService(website_id=self.website_id)

    async def run(self) -> Dict[str, Any]:
        start_t = time.time()
        logger.info("[AssetEngineer] Commencing Monday 10:00 IST linkable asset engineering pass...")
        
        supabase = get_supabase()
        try:
            res = supabase.table("backlink_opportunities").select("*").eq("website_id", self.website_id).eq("status", "discovered").limit(10).execute()
            opportunities = res.data or []
        except Exception:
            opportunities = []

        briefed_assets = []
        already_covered_count = 0

        for opp in opportunities:
            opp_id = opp.get("id")
            opp_type = opp.get("opportunity_type", "resource_page")
            dr = opp.get("domain_rating", 45)
            target_url = opp.get("url", "")

            # Determine asset configuration dynamically
            topic = opp.get("page_topic") or opp.get("niche_keyword") or opp.get("anchor_text") or "Industry Analysis"
            if opp_type == "statistics_citation":
                asset_title = f"{topic} Statistics & Benchmark [2026 Comprehensive Data]"
                target_kw = f"{topic} statistics 2026"
                why_earns = "Engineered to attract academic and authoritative citations with real empirical data points."
                min_words = 2800
            elif opp_type == "competitor_gap":
                asset_title = f"{topic} Definitive Framework & Evaluation Guide"
                target_kw = f"{topic} evaluation guide"
                why_earns = "Superior technical analysis designed to replace competitor links on high-DR resource portals."
                min_words = 2600
            elif opp_type == "link_page":
                asset_title = f"{topic} Resource Directory & Strategic Index"
                target_kw = f"{topic} resource index"
                why_earns = "High-utility resource index providing unique value for dedicated industry link hubs."
                min_words = 2400
            else: # resource_page / default
                asset_title = f"The Definitive 2026 Guide to {topic}"
                target_kw = f"{topic} guide 2026"
                why_earns = "Authoritative long-form pillar guide built to be the single best reference link on the web."
                min_words = 3000

            priority = "critical" if dr >= 50 else "high" if dr >= 30 else "medium"

            brief_row = {
                "website_id": self.website_id,
                "target_keyword": target_kw,
                "suggested_title": asset_title,
                "type": "linkable_asset",
                "priority_score": float(dr) * 1.5,
                "status": "pending",
                "metadata": {
                    "asset_type": opp_type,
                    "target_linking_domains": [target_url],
                    "why_it_earns_links": why_earns,
                    "minimum_word_count": min_words,
                    "priority_tier": priority,
                    "required_schema": ["ItemPage", "FAQPage", "Dataset", "SpeakableSpecification"]
                },
                "created_at": datetime.utcnow().isoformat()
            }

            try:
                supabase.table("brain_auto_pages_queue").insert(brief_row).execute()
                supabase.table("backlink_opportunities").update({"status": "asset_briefed", "updated_at": datetime.utcnow().isoformat()}).eq("id", opp_id).execute()
                briefed_assets.append(brief_row)
            except Exception as e:
                logger.debug(f"[AssetEngineer] Brief queue note: {e}")

        # Record completion to brain_memory
        await self.brain.remember(
            website_id=self.website_id,
            memory_type="experience",
            title=f"Asset Engineer Briefing: {len(briefed_assets)} Assets",
            content=f"Briefed {len(briefed_assets)} new linkable assets for WriterPipeline based on active high-DR opportunities. {already_covered_count} opportunities matched existing content.",
            source_type="asset_engineer_agent",
            confidence=0.94
        )

        duration = time.time() - start_t
        try:
            supabase.table("tasks").insert({
                "website_id": self.website_id,
                "action": "asset_engineer_briefing",
                "status": "completed",
                "duration_sec": duration,
                "metadata": {"briefed_count": len(briefed_assets)},
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception:
            pass

        return {
            "success": True,
            "briefed_count": len(briefed_assets),
            "already_covered_count": already_covered_count,
            "duration_sec": duration
        }
