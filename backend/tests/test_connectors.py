import os
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.database import get_supabase


@pytest.mark.asyncio
async def test_connectors_status():
    """Test GET /api/connectors/status returns health of real connectors."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/connectors/status")
        assert res.status_code == 200
        data = res.json()
        assert "nvidia" in data
        assert "supabase" in data
        assert "wordpress" in data
        assert data["supabase"]["connected"] is True


@pytest.mark.asyncio
async def test_nvidia_connector():
    """Test POST /api/connectors/test-nvidia with real NVIDIA API key."""
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        pytest.skip("NVIDIA_API_KEY not configured")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/connectors/test-nvidia", json={"api_key": api_key})
        assert res.status_code == 200
        data = res.json()
        assert data["connected"] is True
        assert len(data.get("models", [])) > 0


@pytest.mark.asyncio
async def test_supabase_connector():
    """Test POST /api/connectors/test-supabase with real Supabase credentials."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        pytest.skip("Supabase credentials not configured")

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
