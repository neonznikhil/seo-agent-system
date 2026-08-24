import pytest
from unittest.mock import patch, AsyncMock
from backend.services.serper_service import serper_service


@pytest.mark.asyncio
async def test_serper_connector_queries():
    mock_search = {
        "organic": [{"title": "Texas Injury Claim Rules", "link": "https://texasbar.com", "snippet": "Legal guidelines"}],
        "peopleAlsoAsk": [{"question": "How long do I have to file?"}],
    }
    
    with patch("backend.services.serper_service.serper_service.search", new=AsyncMock(return_value=mock_search)):
        res = await serper_service.search("Texas personal injury lawyer", num=5)
        assert "organic" in res
        assert len(res["organic"]) > 0
        assert "peopleAlsoAsk" in res
