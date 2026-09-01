import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from services.serper_service import serper_service, SerperService
from main import app


@pytest.mark.asyncio
async def test_serper_connector_queries():
    mock_search = {
        "source": "serper.dev",
        "organic": [{"title": "Texas Injury Claim Rules", "link": "https://texasbar.com", "snippet": "Legal guidelines"}],
        "peopleAlsoAsk": [{"question": "How long do I have to file?"}],
        "relatedSearches": [{"query": "Texas statute of limitations"}],
    }
    
    with patch.object(serper_service, "_call_serper_search_api", new=AsyncMock(return_value=mock_search)):
        with patch.object(serper_service, "is_configured", return_value=True):
            with patch.object(serper_service, "is_enabled", return_value=True):
                with patch.object(serper_service, "_log_cost_to_daily_costs"):
                    res = await serper_service.search("Texas personal injury lawyer", num=5)
                    assert "organic" in res
                    assert len(res["organic"]) > 0
                    assert "peopleAlsoAsk" in res

                    # Test PAA and related searches methods
                    paa = await serper_service.get_people_also_ask("Texas personal injury lawyer")
                    assert len(paa) > 0
                    assert paa[0]["question"] == "How long do I have to file?"

                    related = await serper_service.get_related_searches("Texas personal injury lawyer")
                    assert len(related) > 0


@pytest.mark.asyncio
async def test_serper_news_and_images():
    mock_news = {
        "news": [{"title": "New Texas Law 2026", "link": "https://news.com/1", "snippet": "Recent update"}]
    }
    mock_images = {
        "images": [{"title": "Courtroom", "imageUrl": "https://images.com/1.jpg"}]
    }

    with patch.object(serper_service, "_call_serper_news_api", new=AsyncMock(return_value=mock_news)):
        with patch.object(serper_service, "is_configured", return_value=True):
            with patch.object(serper_service, "is_enabled", return_value=True):
                news_res = await serper_service.search_news("Texas legal news", num_results=5)
                assert news_res.get("news") or news_res.get("organic") is not None

    with patch.object(serper_service, "is_configured", return_value=True):
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=MagicMock(status_code=200, json=lambda: mock_images))):
            images_res = await serper_service.search_images("Texas court", num_results=5)
            assert "images" in images_res


@pytest.mark.asyncio
async def test_serper_test_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/connectors/serper/test?query=SEO+Agent")
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") is True
        assert "source" in data

