import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from pydantic import BaseModel

from ..services.ranking_signal_harvester import RankingSignalHarvester
from ..services.topic_ownership_engine import TopicOwnershipEngine
from ..services.entity_authority_service import EntityAuthorityService
from ..services.serp_volatility_service import SerpVolatilityService
from ..services.content_portfolio_service import ContentPortfolioService
from ..services.internal_link_service import build_internal_link_graph, run_autonomous_internal_link_optimization
from ..services.knowledge_evolution_service import KnowledgeEvolutionService
from ..services.conversion_intelligence_service import ConversionIntelligenceService
from ..services.crisis_response_service import CrisisResponseService
from ..services.self_training_service import SelfTrainingService
from ..services.slack_intelligence_service import slack_intelligence_service

logger = logging.getLogger("backend.routers.phase3_router")

router = APIRouter(tags=["Phase 3 Self-Evolving Organism"])


# 1. Niche Harvest
@router.get("/api/niche-harvest/report")
async def get_niche_harvest_report(website_id: str = "default"):
    harvester = RankingSignalHarvester(website_id=website_id)
    res = await harvester.run_niche_harvest()
    return {"success": True, "data": res}


@router.post("/api/niche-harvest/run")
async def run_niche_harvest_now(website_id: str = "default"):
    harvester = RankingSignalHarvester(website_id=website_id)
    res = await harvester.run_niche_harvest()
    return {"success": True, "data": res}


# 2. Topic Ownership
@router.get("/api/topic-ownership/map")
async def get_topic_ownership_map(website_id: str = "default", pillar: str = "Texas personal injury law"):
    engine = TopicOwnershipEngine(website_id=website_id)
    res = await engine.build_semantic_map(pillar)
    return {"success": True, "data": res}


@router.post("/api/topic-ownership/run")
async def run_topic_ownership_now(website_id: str = "default", pillar: str = "Texas personal injury law"):
    engine = TopicOwnershipEngine(website_id=website_id)
    res = await engine.build_semantic_map(pillar)
    return {"success": True, "data": res}


# 3. Entity Authority
@router.get("/api/entity-authority/audit")
async def get_entity_audit(website_id: str = "default", entity_name: str = "RankForge Legal"):
    svc = EntityAuthorityService(website_id=website_id)
    res = await svc.run_entity_audit(entity_name)
    return {"success": True, "data": res}


# 4. SERP Volatility
@router.get("/api/serp-volatility/index")
async def get_serp_volatility(website_id: str = "default"):
    svc = SerpVolatilityService(website_id=website_id)
    res = await svc.check_serp_volatility()
    return {"success": True, "data": res}


# 5. Content Portfolio
@router.get("/api/content-portfolio/analysis")
async def get_content_portfolio(website_id: str = "default"):
    svc = ContentPortfolioService(website_id=website_id)
    res = await svc.analyze_portfolio()
    return {"success": True, "data": res}


# 6. Internal Links
@router.get("/api/internal-links/graph")
async def get_internal_link_graph_data(website_id: str = "default"):
    graph = await build_internal_link_graph(website_id)
    return {"success": True, "data": graph}


@router.post("/api/internal-links/optimize")
async def run_internal_link_optimization_now(website_id: str = "default"):
    res = await run_autonomous_internal_link_optimization(website_id)
    return {"success": True, "data": res}


# 7. Knowledge Evolution
@router.get("/api/knowledge-evolution/health")
async def get_knowledge_health(website_id: str = "default"):
    svc = KnowledgeEvolutionService(website_id=website_id)
    res = await svc.run_daily_evolution_jobs()
    return {"success": True, "data": res}


# 8. Conversion Intelligence
@router.get("/api/conversion-intelligence/report")
async def get_conversion_intelligence_report(website_id: str = "default"):
    svc = ConversionIntelligenceService(website_id=website_id)
    res = await svc.run_conversion_analysis()
    return {"success": True, "data": res}


# 9. Crisis Response
@router.get("/api/crisis-response/status")
async def get_crisis_status(website_id: str = "default"):
    svc = CrisisResponseService(website_id=website_id)
    res = await svc.evaluate_crises()
    return {"success": True, "data": res}


# 10. Self-Training Loop
@router.get("/api/self-training/dashboard")
async def get_self_training_dashboard(website_id: str = "default"):
    svc = SelfTrainingService(website_id=website_id)
    res = await svc.run_self_training_cycle()
    return {"success": True, "data": res}


# 11. Slack App Integration Test
@router.post("/api/slack/test-report")
async def trigger_slack_test_report(website_id: str = "default"):
    success = await slack_intelligence_service.send_morning_brief(website_id)
    return {"success": success, "message": "Mini Morning Brief report dispatched to Slack channel."}
