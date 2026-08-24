import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock

from backend.main import app


@pytest.mark.asyncio
async def test_auth_login_demo():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={"email": "admin@rankforge.ai", "password": "demo"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "token" in data
        assert data["user"]["email"] == "admin@rankforge.ai"
        assert data["user"]["role"] == "owner"


@pytest.mark.asyncio
async def test_auth_signup_validation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Invalid email
        res = await client.post("/api/auth/signup", json={"email": "invalid", "password": "123"})
        assert res.status_code == 400

        # Short password
        res2 = await client.post("/api/auth/signup", json={"email": "valid@test.com", "password": "123"})
        assert res2.status_code == 400


@pytest.mark.asyncio
async def test_delete_blog_endpoint():
    transport = ASGITransport(app=app)
    with patch("backend.main.get_supabase") as mock_sup:
        mock_sup.return_value.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "test-blog-id"}])
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.delete("/api/blogs/test-blog-id")
            assert res.status_code == 200
            data = res.json()
            assert data.get("success") is True
            assert data.get("deleted_id") == "test-blog-id"
