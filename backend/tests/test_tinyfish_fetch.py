"""
backend/tests/test_tinyfish_fetch.py
Unit and integration tests for TinyFish Fetch API integration.
"""

import os
import pytest
from backend.services.tinyfish_service import TinyFishService

@pytest.mark.asyncio
async def test_tinyfish_fetch_degraded_when_unconfigured():
    service = TinyFishService(api_key="")
    assert not service.is_configured
    result = await service.fetch(["https://example.com"])
    assert result["status"] == "degraded"
    assert result["source"] == "tinyfish_fetch"
    assert result["results"] == []
    assert "not configured" in result["reason"].lower()

@pytest.mark.asyncio
async def test_tinyfish_fetch_real_with_key():
    key = os.getenv("TINYFISH_API_KEY")
    if not key or len(key) < 10:
        pytest.skip("TINYFISH_API_KEY not set in environment — testing degradation path only")

    service = TinyFishService(api_key=key)
    result = await service.fetch(["https://www.tinyfish.ai/"], format="markdown")
    assert result["status"] == "success"
    assert len(result["results"]) > 0
    md = result["results"][0].get("markdown", "")
    assert len(md) > 50
    assert result["results"][0]["source"] == "tinyfish_fetch"
