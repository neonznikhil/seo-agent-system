import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock, AsyncMock
from main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    with patch("backend.main.get_supabase") as mock_sup:
        mock_sup.return_value.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[{"id": "test"}])
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "checks" in data


@pytest.mark.asyncio
async def test_deep_health_endpoint():
    transport = ASGITransport(app=app)
    with patch("backend.main.get_supabase") as mock_sup:
        mock_sup.return_value.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[{"id": "test"}])
        with patch("backend.database.call_nim_llm", new=AsyncMock(return_value="pong")):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/health/deep")
                assert response.status_code == 200
                data = response.json()
                assert data.get("success") is True
                assert "health_score" in data
                assert data.get("health_score") >= 0
                assert "services" in data
                assert "supabase" in data["services"]
                assert "nvidia_nim" in data["services"]

