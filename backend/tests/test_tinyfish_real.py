"""
backend/tests/test_tinyfish_real.py
REAL tests for TinyFish integration - no mocks, test graceful degradation and real API when key set
"""

import os
import pytest
import asyncio

@pytest.mark.asyncio
async def test_tinyfish_search_degraded_without_key():
    """Without TINYFISH_API_KEY, should return degraded, never fake data"""
    # Temporarily unset key
    original = os.getenv("TINYFISH_API_KEY")
    if "TINYFISH_API_KEY" in os.environ:
        del os.environ["TINYFISH_API_KEY"]

    # Need to reimport to pick up no-key state
    import importlib
    import backend.services.tinyfish_service as tf_module
    importlib.reload(tf_module)

    service = tf_module.TinyFishService(api_key="")
    result = await service.search("test query")

    assert result["status"] == "degraded"
    assert result["organic"] == []
    assert "TINYFISH_API_KEY not configured" in result["reason"]
    assert result["source"] == "tinyfish_search"
    # Must NOT return fake data
    assert result["organic"] == []

    # Restore
    if original:
        os.environ["TINYFISH_API_KEY"] = original

@pytest.mark.asyncio
async def test_tinyfish_fetch_degraded_without_key():
    """Without key, fetch should return degraded"""
    import backend.services.tinyfish_service as tf_module
    service = tf_module.TinyFishService(api_key="")
    result = await service.fetch(["https://example.com"])

    assert result["status"] == "degraded"
    assert result["results"] == []
    assert "not configured" in result["reason"].lower()

@pytest.mark.asyncio
async def test_tinyfish_search_real_with_key():
    """With real TINYFISH_API_KEY, should return real organic results"""
    api_key = os.getenv("TINYFISH_API_KEY")
    if not api_key or len(api_key) < 10:
        pytest.skip("TINYFISH_API_KEY not set - skipping real API test")

    from backend.services.tinyfish_service import TinyFishService
    service = TinyFishService(api_key=api_key)

    result = await service.search("RankForge SEO automation", limit=5)

    # Should be success with real data
    assert result["status"] == "success", f"Expected success, got {result}"
    assert result["source"] == "tinyfish_search"
    assert len(result["organic"]) > 0, "Should return real organic results"
    assert "title" in result["organic"][0]
    assert "link" in result["organic"][0]
    assert result["organic"][0]["title"] != ""
    # Must be real, not fake
    assert result["provenance"] == "observed"

@pytest.mark.asyncio
async def test_tinyfish_fetch_real_with_key():
    """With real key, fetch should return clean markdown >100 chars"""
    api_key = os.getenv("TINYFISH_API_KEY")
    if not api_key or len(api_key) < 10:
        pytest.skip("TINYFISH_API_KEY not set - skipping real API test")

    from backend.services.tinyfish_service import TinyFishService
    service = TinyFishService(api_key=api_key)

    result = await service.fetch(["https://www.tinyfish.ai/"], format="markdown")

    assert result["status"] == "success"
    assert len(result["results"]) > 0
    markdown = result["results"][0].get("markdown", "")
    assert len(markdown) > 100, f"Should return clean markdown >100 chars, got {len(markdown)}"
    assert result["results"][0]["source"] == "tinyfish_fetch"

@pytest.mark.asyncio
async def test_web_research_provider_search():
    """WebResearchProvider should use TinyFish first, then Serper, then degraded"""
    from backend.services.web_research_provider import get_web_research_provider
    provider = get_web_research_provider()

    result = await provider.search("test query for RankForge")

    # Should return ResearchResult with status
    assert result.status in ["success", "degraded", "failed"]
    assert result.provenance == "observed"
    # Should never return fake data
    if result.status == "degraded":
        assert result.data["organic"] == []

@pytest.mark.asyncio
async def test_web_research_provider_quota_guard():
    """Quota guard should return degraded when cap reached"""
    from backend.services.web_research_provider import WebResearchProvider
    provider = WebResearchProvider()
    provider.daily_cost_cents = 1000
    provider.daily_cap_cents = 500

    result = await provider.search("test query")

    assert result.status == "degraded"
    assert "cap" in result.data["reason"].lower()
