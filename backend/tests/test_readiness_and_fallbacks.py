import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
from fastapi.testclient import TestClient

from backend.wordpress_oauth import test_wordpress_connection as wp_test_conn
from backend.services.nim_client import nim_generate_with_feedback
from backend.services.serper_service import serper_search_safe
from backend.agents.tools.knowledge_crawler_tool import KnowledgeCrawlerTool
from backend.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. WORDPRESS CONNECTION DIAGNOSTICS
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_wordpress_connection_200():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": 1,
        "name": "Editor User",
        "roles": ["editor"],
        "capabilities": {"publish_posts": True}
    }
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        res = await wp_test_conn("https://testsite.com", "admin", "pwd")
        assert res["status"] == "connected"
        assert res["role"] == "editor"
        assert res["can_publish"] is True


@pytest.mark.asyncio
async def test_wordpress_connection_401():
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized"
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        res = await wp_test_conn("https://testsite.com", "wronguser", "wrongpwd")
        assert res["status"] == "error"
        assert "Wrong username or app password" in res["message"]


@pytest.mark.asyncio
async def test_wordpress_connection_403():
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "Forbidden by Wordfence"
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        res = await wp_test_conn("https://testsite.com", "user", "pwd")
        assert res["status"] == "error"
        assert "security plugin" in res["message"].lower()


@pytest.mark.asyncio
async def test_wordpress_connection_404():
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = "Not Found"
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        res = await wp_test_conn("https://testsite.com", "user", "pwd")
        assert res["status"] == "error"
        assert "permalinks" in res["message"].lower()


@pytest.mark.asyncio
async def test_wordpress_connection_timeout():
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Timeout")):
        res = await wp_test_conn("https://testsite.com", "user", "pwd")
        assert res["status"] == "error"
        assert "timed out" in res["message"].lower()


# ---------------------------------------------------------------------------
# 2. NVIDIA NIM FEEDBACK & TIMEOUT HANDLING
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_nim_generate_with_feedback_timeout():
    async def slow_gen(*args, **kwargs):
        import asyncio
        await asyncio.sleep(2.0)
        return "slow"

    with patch("backend.services.nim_client.generate", new=slow_gen):
        with pytest.raises(ValueError) as exc:
            await nim_generate_with_feedback("prompt", timeout_seconds=1, job_label="Test Call")
        assert "timed out after 1s" in str(exc.value)


@pytest.mark.asyncio
async def test_nim_generate_with_feedback_401():
    with patch("backend.services.nim_client.generate", side_effect=Exception("HTTP 401 Unauthorized")):
        with pytest.raises(ValueError) as exc:
            await nim_generate_with_feedback("prompt", timeout_seconds=5)
        assert "API key is invalid or expired" in str(exc.value)


@pytest.mark.asyncio
async def test_nim_generate_with_feedback_429():
    with patch("backend.services.nim_client.generate", side_effect=Exception("HTTP 429 Rate Limit")):
        with pytest.raises(ValueError) as exc:
            await nim_generate_with_feedback("prompt", timeout_seconds=5)
        assert "rate limit reached" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# 3. SERPER SAFE SEARCH & QUOTA INTERCEPTION
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_serper_search_safe_quota_exceeded():
    with patch("backend.services.serper_service.serper_service.search", side_effect=Exception("403 Quota exceeded")):
        results = await serper_search_safe("car accident law", num_results=5)
        assert results == []  # Never crashes caller


@pytest.mark.asyncio
async def test_serper_search_safe_success():
    mock_results = {
        "organic": [
            {"title": "Result 1", "link": "https://example.com/1"},
            {"title": "Result 2", "link": "https://example.com/2"},
        ]
    }
    with patch("backend.services.serper_service.serper_service.search", new=AsyncMock(return_value=mock_results)):
        results = await serper_search_safe("car accident law", num_results=2)
        assert len(results) == 2
        assert results[0]["title"] == "Result 1"


# ---------------------------------------------------------------------------
# 4. KNOWLEDGE CRAWLER FALLBACK
# ---------------------------------------------------------------------------
def test_knowledge_crawler_homepage_fallback():
    tool = KnowledgeCrawlerTool()
    tool.set_website_id("test_fallback_site")
    
    mock_html = """<html><body>
    <a href="/about-us">About Us</a>
    <a href="/services">Legal Services</a>
    <a href="/contact">Contact</a>
    <p>Houston personal injury attorneys fighting for car accident victims.</p>
    </body></html>"""

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = mock_html
    mock_resp.headers = {"content-type": "text/html"}

    with patch("httpx.get", return_value=mock_resp):
        urls = tool._crawl_homepage_links("https://houstonlaw.com", max_pages=10)
        assert "https://houstonlaw.com" in urls
        assert "https://houstonlaw.com/about-us" in urls
        assert "https://houstonlaw.com/services" in urls


# ---------------------------------------------------------------------------
# 5. DEMO READINESS CHECK ENDPOINT
# ---------------------------------------------------------------------------
def test_demo_readiness_check_endpoint():
    res = client.get("/api/demo/readiness-check?website_id=default")
    assert res.status_code == 200
    data = res.json()
    assert "demo_ready" in data
    assert "checks" in data
    assert len(data["checks"]) == 5
    check_names = [c["name"] for c in data["checks"]]
    assert "Knowledge Base" in check_names
    assert "NVIDIA NIM" in check_names
    assert "Serper API" in check_names
    assert "WordPress" in check_names
    assert "Content Ready" in check_names
