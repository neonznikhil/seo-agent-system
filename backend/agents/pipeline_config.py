import logging
from datetime import datetime
import json
"""
Pipeline configuration for 10-phase, 100+ step content generation.
EVERY article runs FULL pipeline - no shortcuts.
"""

from typing import Dict, List, Any, Optional



PIPELINE_PHASES = [
    {
        "id": 1,
        "name": "audience_demand",
        "display_name": "Audience & Demand",
        "steps": 10,
        "desc": "Topic selection, audience research, Business Potential Scoring 0-3"
    },
    {
        "id": 2,
        "name": "serp_competitor", 
        "display_name": "SERP & Competitors",
        "steps": 20,
        "desc": "Every ranking page scraped via Crawlee, structure/headings/gaps extracted"
    },
    {
        "id": 3,
        "name": "keyword_intent",
        "display_name": "Keyword & Intent Mapping",
        "steps": 10,
        "desc": "Live GSC keywords, intent classification, funnel mapping"
    },
    {
        "id": 4,
        "name": "positioning",
        "display_name": "Positioning & Angle",
        "steps": 10,
        "desc": "Positioning analysis, funnel alignment lock angle and spine"
    },
    {
        "id": 5,
        "name": "outline_structure",
        "display_name": "Outline & Structure",
        "steps": 10,
        "desc": "H1-H3 outline with question H2s for GEO, table, FAQ, internal link plan"
    },
    {
        "id": 6,
        "name": "multi_step_writing",
        "display_name": "Multi-Step Writing",
        "steps": 20,
        "desc": "Section-by-section drafting with research, citations, brand voice"
    },
    {
        "id": 7,
        "name": "internal_linking_schema",
        "display_name": "Internal Linking & Schema",
        "steps": 10,
        "desc": "Smart internal link graph + Article/FAQPage/Breadcrumb schema"
    },
    {
        "id": 8,
        "name": "eeat_citations",
        "display_name": "E-E-A-T & Citations",
        "steps": 10,
        "desc": "Author, reviewer, last-updated, verified first-party citations"
    },
    {
        "id": 9,
        "name": "multi_expert_review",
        "display_name": "Multi-Expert Review",
        "steps": 11,
        "desc": "Chief Editor iterates, then 11 expert frameworks review every phase"
    },
    {
        "id": 10,
        "name": "humanizer_gate",
        "display_name": "Humanizer & Gate",
        "steps": 10,
        "desc": "AI tells stripped, GEO dual-optimized, ready to publish draft"
    }
]

EXPERT_NAMES = [
    "seo_expert",
    "eeat_expert", 
    "helpful_content_expert",
    "ai_search_expert",
    "brand_voice_expert",
    "business_impact_expert",
    "editorial_expert",
    "fact_check_expert",
    "internal_link_expert",
    "citation_expert",
    "humanizer_expert"
]

MODES = {
    "grounded": "Grounded in Your Knowledge",
    "deep_web": "Deep Web Research",
    "combined": "Combined (Verified takes precedence)"
}

TOTAL_STEPS = sum(p["steps"] for p in PIPELINE_PHASES)

PHASE_HANDLERS = {
    1: "backend.agents.tools.phases.phase_1_audience_demand",
    2: "backend.agents.tools.phases.phase_2_serp_competitor",
    3: "backend.agents.tools.phases.phase_3_keyword_intent",
    4: "backend.agents.tools.phases.phase_4_positioning",
    5: "backend.agents.tools.phases.phase_5_outline_structure",
    6: "backend.agents.tools.phases.phase_6_multi_step_writing",
    7: "backend.agents.tools.phases.phase_7_internal_linking_schema",
    8: "backend.agents.tools.phases.phase_8_eeat_citations",
    9: "backend.agents.tools.phases.phase_9_multi_expert_review",
    10: "backend.agents.tools.phases.phase_10_humanizer_gate",
}

BANNED_PHRASES = [
    "Delve", "Unlock", "Elevate", "In conclusion", "It's important to note",
    "Comprehensive guide", "Plethora", "Leverage", "Utilize", "Harness",
    "Maximize", "Optimize your", "Streamline", "Revolutionary", "Game-changing",
    "Seamless integration", "Powerful", "Transform your", "In today's world",
    "In today's fast-paced world", "Let's dive in", "This guide will walk you through",
    "As we move forward", "Going forward", "When it comes to", "Here are some key points"
]

EM_DASH = "—"


def get_pipeline_progress(content_id: str, website_id: str) -> Dict:
    """Get current pipeline progress for a content item."""
    from ..database import get_supabase
    
    supabase = get_supabase()
    logs = supabase.table("content_pipeline_logs").select("*").eq("content_id", content_id).eq("website_id", website_id).order("step_number").execute().data or []
    
    phases_completed = {}
    steps_completed = 0
    
    for log in logs:
        phase = log.get("phase")
        if phase not in phases_completed:
            phases_completed[phase] = {"completed": 0, "total": 0}
        phases_completed[phase]["completed"] += 1
        steps_completed += 1
    
    for phase in PIPELINE_PHASES:
        phase_name = phase["name"]
        if phase_name not in phases_completed:
            phases_completed[phase_name] = {"completed": 0, "total": phase["steps"]}
    
    return {
        "content_id": content_id,
        "phases_completed": phases_completed,
        "total_steps_completed": steps_completed,
        "total_steps": TOTAL_STEPS,
        "progress_percent": round((steps_completed / TOTAL_STEPS) * 100, 1) if TOTAL_STEPS > 0 else 0
    }