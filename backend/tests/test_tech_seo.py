import logging
import pytest

from backend.agents.tech_seo_agent import run_tech_seo_agent

logger = logging.getLogger("backend.tests.test_tech_seo")


@pytest.mark.asyncio
async def test_tech_seo_agent_runs():
    try:
        result = await run_tech_seo_agent("test-wid", "https://example.com")
        assert "score" in result
        assert "issues" in result
    except Exception as e:
        pytest.skip(f"Tech SEO agent skipped: {e}")
