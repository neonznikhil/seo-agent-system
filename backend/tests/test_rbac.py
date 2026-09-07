import pytest
from httpx import AsyncClient, ASGITransport
from main import app


from unittest.mock import patch


@pytest.mark.asyncio
async def test_rbac_headers():
    transport = ASGITransport(app=app)
    with patch("middleware.auth._validate_user_exists", return_value=True):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Request with Owner user role
            headers = {"X-User-Id": "usr_owner_1", "X-User-Role": "owner", "X-Website-Id": "site_test_1"}
            res = await client.get("/api/websites", headers=headers)
            assert res.status_code == 200
