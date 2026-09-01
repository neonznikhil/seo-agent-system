import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_multisite_header_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Site 1 request
        res1 = await client.get("/api/backlinks/metrics?website_id=site_1")
        assert res1.status_code == 200
        
        # Site 2 request
        res2 = await client.get("/api/backlinks/metrics?website_id=site_2")
        assert res2.status_code == 200
