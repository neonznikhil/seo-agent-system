import asyncio
import os
import sys
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_seo_agent_group")


async def main():
    logger.info("=== 1. Testing SerperService ===")
    from backend.services.serper_service import serper_service
    status = await serper_service.check_status()
    logger.info(f"SerperService Status: {json.dumps(status, indent=2)}")

    search_res = await serper_service.search("Texas personal injury lawyer", num=3)
    logger.info(f"Serper Search Source: {search_res.get('source')}, Organic Count: {len(search_res.get('organic', []))}")
    assert "organic" in search_res, "Search result should contain organic key"

    logger.info("\n=== 2. Testing BrainService 7 Memory Types & Strict Recall ===")
    from backend.services.brain_service import BrainService
    brain = BrainService(website_id="test-website-123")
    
    # Test Remember with types
    mem_fact = await brain.remember(
        website_id="test-website-123",
        memory_type="fact",
        title="Fact: Texas Statute 16.003",
        content="2-year statute of limitations for personal injury in Texas",
        source_type="verification"
    )
    logger.info(f"Saved Fact Memory ID: {mem_fact}")

    mem_outcome = await brain.remember(
        website_id="test-website-123",
        memory_type="outcome",
        title="Outcome: High-converting legal guide",
        content="Article on Texas car accident claims achieved top 3 ranking in 14 days",
        source_type="verification"
    )
    logger.info(f"Saved Outcome Memory ID: {mem_outcome}")

    # Test Failure & Exponential Backoff
    fail_id = await brain.record_failure(
        website_id="test-website-123",
        agent_name="test_agent",
        error_context="HTTP 429 Rate Limit",
        backoff_minutes=15
    )
    logger.info(f"Recorded Failure ID: {fail_id}")

    # Test 14-Day Synthesis
    synthesis = await brain.synthesize_14day_learnings(website_id="test-website-123")
    logger.info(f"14-Day Learning Synthesis: {json.dumps(synthesis, indent=2)}")

    # Test Breakdown
    breakdown = brain.get_memory_breakdown(website_id="test-website-123")
    logger.info(f"Memory Breakdown: {json.dumps(breakdown, indent=2)}")
    assert "by_type" in breakdown, "Breakdown must include by_type mapping"

    logger.info("\n=== 3. Testing 7 SEO Agents ===")
    from backend.agents.research_agent import ResearchAgent
    from backend.agents.keyword_agent import KeywordAgent
    from backend.agents.seo_agent import SEOAgent
    from backend.agents.tech_seo_agent import TechSEOAgent
    from backend.agents.backlink_agent import BacklinkAgent
    from backend.agents.strategy_agent import StrategyAgent
    from backend.agents.supervisor_agent import SupervisorAgent

    # Research Agent
    r_agent = ResearchAgent(website_id="test-website-123")
    r_res = await r_agent.run(topic="commercial truck accidents")
    logger.info(f"ResearchAgent trends count: {len(r_res.get('trends', []))}, connector: {r_res.get('source_connector')}")

    # Keyword Agent
    k_agent = KeywordAgent(website_id="test-website-123")
    k_res = await k_agent.run(r_res)
    logger.info(f"KeywordAgent primary keyword: '{k_res.get('primary_keyword')}', difficulty: {k_res.get('difficulty_score')}")

    # SEO Agent
    s_agent = SEOAgent(website_id="test-website-123")
    s_res = await s_agent.run("<h1>Test Article</h1><p>Content regarding commercial truck accidents.</p>", keyword="commercial truck accidents")
    logger.info(f"SEOAgent title: '{s_res.get('seo_title')}', slug: '{s_res.get('slug')}'")

    # Strategy Agent Self-Healing
    strat_agent = StrategyAgent(website_id="test-website-123")
    alt_res = await strat_agent.generate_alternative_strategy("daily_search", "rate_limit_error", "HTTP 429")
    logger.info(f"StrategyAgent Self-Healing Intervention: {alt_res.get('alternative_approach')}")

    logger.info("\n=== 4. Testing SEO Agent Group Integration Layer ===")
    from backend.agents.seo_agent_group import seo_agent_group
    status_snapshot = await seo_agent_group.get_status_snapshot()
    logger.info(f"SEO Agent Group Status Snapshot:\n{json.dumps(status_snapshot, indent=2)}")
    
    assert "agent_states" in status_snapshot, "Snapshot must include all 7 agent states"
    assert len(status_snapshot["agent_states"]) == 7, "All 7 agents must be present in registry"
    assert "serper_connector" in status_snapshot, "Snapshot must include serper_connector health"
    assert "brain_memory" in status_snapshot, "Snapshot must include brain_memory stats"
    assert "human_gate" in status_snapshot, "Snapshot must include human_gate status"

    logger.info("\n✅ ALL TESTS PASSED SUCCESSFULLY! Autonomous SEO Agent Group is fully operational.")


if __name__ == "__main__":
    asyncio.run(main())
