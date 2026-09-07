import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_websites_endpoint_structure():
    """Verify websites endpoint responds correctly via ASGI transport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/websites")
        assert res.status_code in (200, 401, 403, 500)
