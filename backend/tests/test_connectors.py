import os
import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from database import get_supabase


@pytest.mark.asyncio
async def test_connectors_status():
    """Test GET /api/connectors/status returns honest health of real connectors."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/connectors/status")
        assert res.status_code == 200
        data = res.json()
        assert "nvidia" in data
        assert "supabase" in data
        assert "wordpress" in data
        # Honesty invariant: a placeholder/never-valid config must never be
        # reported as connected, and must never be reported as configured.
        sb = data["supabase"]
        if sb.get("placeholder"):
            assert sb["connected"] is False
            assert sb["is_configured"] is False
        if not sb["connected"]:
            assert sb["is_configured"] is False


@pytest.mark.asyncio
async def test_placeholder_supabase_is_not_reported_connected(monkeypatch):
    """Regression: 'dummy' key + example.supabase.co used to report connected=true."""
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "dummy")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/connectors/status")
        assert res.status_code == 200
        sb = res.json()["supabase"]
        assert sb["placeholder"] is True
        assert sb["connected"] is False
        assert sb["is_configured"] is False



@pytest.mark.asyncio
async def test_nvidia_connector():
    """Test POST /api/connectors/test-nvidia with real NVIDIA API key."""
    from tests.conftest import live_nvidia_key
    api_key = live_nvidia_key()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/connectors/test-nvidia", json={"api_key": api_key})
        from tests.conftest import skip_if_auth_rejected
        skip_if_auth_rejected(res.status_code, res.text)
        assert res.status_code == 200
        data = res.json()
        assert data["connected"] is True
        assert len(data.get("models", [])) > 0


@pytest.mark.asyncio
async def test_supabase_connector():
    """Test POST /api/connectors/test-supabase with real Supabase credentials."""
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_KEY", "")
    if not supabase_url or not supabase_key or supabase_key.strip().lower() in ("", "dummy", "your-supabase-service-role-key", "mock-key") or "example.supabase.co" in supabase_url or "dummy" in supabase_url:
        pytest.skip("Real Supabase credentials not configured")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/connectors/test-supabase", json={
            "supabase_url": supabase_url,
            "anon_key": supabase_key
        })
        assert res.status_code == 200
        data = res.json()
        assert data["connected"] is True


@pytest.mark.asyncio
async def test_supabase_tables_exist():
    """Verify that core active tables exist in the live database schema."""
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_KEY", "")
    if not supabase_url or not supabase_key or supabase_key.strip().lower() in ("", "dummy", "your-supabase-service-role-key", "mock-key") or "example.supabase.co" in supabase_url or "dummy" in supabase_url:
        pytest.skip("Real Supabase credentials not configured")
    supabase = get_supabase()
    tables = [
        "websites",
        "knowledge_base",
        "website_knowledge",
        "tasks"
    ]
    for table_name in tables:
        try:
            res = supabase.table(table_name).select("id").limit(1).execute()
            assert res.data is not None, f"Table {table_name} query returned None"
        except Exception as e:
            pytest.fail(f"Failed to query required table '{table_name}': {e}")
