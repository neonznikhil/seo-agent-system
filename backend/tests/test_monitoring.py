import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock, AsyncMock
from main import app


@pytest.mark.asyncio
async def test_monitoring_endpoints():
    transport = ASGITransport(app=app)
    with patch("backend.database.get_supabase") as mock_sup:
        mock_sup.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        with patch("backend.services.serp_volatility_service.SerpVolatilityService.check_serp_volatility", new=AsyncMock(return_value={"niche_volatility_index": 34.5, "status": "stable"})):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # 1. Monitoring alerts
                res = await client.get("/api/monitoring/default/alerts")
                assert res.status_code == 200

                # 2. SERP Volatility index
                v_res = await client.get("/api/serp-volatility/index?website_id=default")
                assert v_res.status_code == 200
                v_data = v_res.json()
                assert v_data.get("success") is True
                assert "niche_volatility_index" in v_data["data"]




