import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.agents.backlink_agent import BacklinkAgent
from backend.agents.aeo_agent import AEOAgent


@pytest.mark.asyncio
async def test_backlink_4_modules():
    """Test 4-module Backlink Engine: prospecting, qualification, personalized pitch, approval."""
    agent = BacklinkAgent()
    res = await agent.run_prospecting_loop(keyword="Houston accident lawyer resources")
    assert res["success"] is True
    assert "prospects_scanned" in res
    assert "opportunities_found" in res
    assert "saved_for_approval" in res


@pytest.mark.asyncio
async def test_backlink_opportunities_api():
    """Test GET /api/backlinks/opportunities endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/backlinks/opportunities")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_aeo_4_modules_and_schema():
    """Test AEO citation tracking, Share of Voice calculation, and Schema JSON-LD injection."""
    aeo = AEOAgent()
    
    # 1. Citation Tracking
    sov_data = await aeo.track_buyer_intent_queries([
        "Who is the best car accident lawyer in Houston?",
        "What are top rated Texas personal injury attorneys?"
    ])
    assert "sov_percentage" in sov_data
    assert float(sov_data["sov_percentage"]) >= 0.0

    # 2. Schema Generation
    schema_res = await aeo.generate_and_inject_schema(
        blog_id=None,
        schema_type="FAQPage"
    )
    assert schema_res["success"] is True
    assert schema_res["schema_json"]["@type"] == "FAQPage"


@pytest.mark.asyncio
async def test_dynamic_llms_txt_and_full():
    """Test dynamic /llms.txt and /llms-full.txt endpoints return real business information."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. /llms.txt
        res_txt = await client.get("/llms.txt")
        assert res_txt.status_code == 200
        content_txt = res_txt.text
        assert "Innovatcs" in content_txt or "Injury" in content_txt or "Legal" in content_txt
        assert "Acme" not in content_txt

        # 2. /llms-full.txt
        res_full = await client.get("/llms-full.txt")
        assert res_full.status_code == 200
        content_full = res_full.text
        assert len(content_full) > 100

        # 3. Generate static file
        res_gen = await client.post("/api/llms/generate")
        assert res_gen.status_code == 200
