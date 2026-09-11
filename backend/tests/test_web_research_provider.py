"""
backend/tests/test_web_research_provider.py
Unit tests for WebResearchProvider abstraction wrapping TinyFish -> Serper -> Tavily.
"""

import os
import pytest
from backend.services.web_research_provider import WebResearchProvider, get_web_research_provider

@pytest.mark.asyncio
async def test_web_research_provider_singleton():
    p1 = get_web_research_provider()
    p2 = get_web_research_provider()
    assert p1 is p2

@pytest.mark.asyncio
async def test_web_research_provider_search_contracts():
    provider = WebResearchProvider()
    res = await provider.search("test query for RankForge", limit=5)
    assert hasattr(res, "source")
    assert hasattr(res, "status")
    assert hasattr(res, "data")
    assert hasattr(res, "provenance")
    assert res.provenance == "observed"
    assert res.status in ("success", "degraded", "failed")
    if res.status == "degraded":
        assert res.data.get("organic") == []

@pytest.mark.asyncio
async def test_web_research_provider_quota_guard():
    provider = WebResearchProvider()
    provider.daily_cost_cents = 600
    provider.daily_cap_cents = 500
    assert not provider._check_quota()
    res = await provider.search("any query")
    assert res.status == "degraded"
    assert "cap" in res.data.get("reason", "").lower()

@pytest.mark.asyncio
async def test_web_research_provider_fetch_empty_list():
    provider = WebResearchProvider()
    res = await provider.fetch([])
    assert res.status == "success"
    assert res.data["results"] == []
