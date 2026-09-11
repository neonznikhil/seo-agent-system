"""
backend/tests/test_tinyfish_search.py
Unit and integration tests for TinyFish Search API integration.
"""

import os
import pytest
from backend.services.tinyfish_service import TinyFishService, get_tinyfish_service

@pytest.mark.asyncio
async def test_tinyfish_search_degraded_when_unconfigured():
    service = TinyFishService(api_key="")
    assert not service.is_configured
    result = await service.search("personal injury statute of limitations")
    assert result["status"] == "degraded"
    assert result["source"] == "tinyfish_search"
    assert result["organic"] == []
    assert "not configured" in result["reason"].lower()
    assert result["provenance"] == "observed"

@pytest.mark.asyncio
async def test_tinyfish_search_structure_with_key_or_stub():
    key = os.getenv("TINYFISH_API_KEY")
    if not key or len(key) < 10:
        pytest.skip("TINYFISH_API_KEY not set in environment — testing degradation path only")

    service = TinyFishService(api_key=key)
    result = await service.search("RankForge SEO automation", limit=5)
    assert result["status"] == "success"
    assert result["source"] == "tinyfish_search"
    assert len(result["organic"]) > 0
    assert "title" in result["organic"][0]
    assert "link" in result["organic"][0]
    assert result["provenance"] == "observed"
