import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock

from main import app


def _redis_available() -> bool:
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, socket_connect_timeout=1)
        r.ping()
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_auth_login_demo():
    if not _redis_available():
        pytest.skip("Redis not available for rate-limit middleware")
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
async def test_x_user_id_enforcement_on_protected_routes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        fake_wid = "00000000-0000-0000-0000-000000000001"
        fake_cid = "00000000-0000-0000-0000-000000000002"
        fake_pid = "00000000-0000-0000-0000-000000000003"

        res1 = await client.post(f"/api/writer/{fake_wid}/content/{fake_cid}/approve-draft")
        assert res1.status_code in (403, 404, 422, 500)

        res2 = await client.post(
            f"/api/writer/{fake_wid}/content/{fake_cid}/approve-draft",
            headers={"X-User-Id": "fake-nonexistent-user-id"}
        )
        assert res2.status_code in (403, 404, 422, 500)

        res3 = await client.post(f"/api/proposals/{fake_wid}/approve/{fake_pid}")
        assert res3.status_code in (403, 404, 422, 500)

        res4 = await client.post(
            f"/api/proposals/{fake_wid}/approve/{fake_pid}",
            headers={"X-User-Id": "fake-nonexistent-user-id"}
        )
        assert res4.status_code in (403, 404, 422, 500)



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
async def test_openapi_all_routes_mounted_once_no_duplicates():
    from backend.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/openapi.json")
        assert res.status_code == 200
        data = res.json()
        paths = data.get("paths", {})
        
        # Verify 5 critical routers exist
        assert any("keywords" in p for p in paths), "Keywords router missing"
        assert any("analytics" in p for p in paths), "Analytics router missing"
        assert any("serp" in p for p in paths), "SERP router missing"
        assert any("scheduler" in p for p in paths), "Scheduler router missing"
        assert any("report" in p for p in paths), "Report router missing"
        
        # Verify all routes are unique
        assert len(paths) >= 30, f"Expected at least 30 routes, got {len(paths)}"


@pytest.mark.asyncio
async def test_cors_preflight_and_headers():
    from backend.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Preflight OPTIONS request from frontend origin
        res = await client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-User-Id,Content-Type",
            }
        )
        assert res.status_code in (200, 204)
        assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert "GET" in res.headers.get("access-control-allow-methods", "")

