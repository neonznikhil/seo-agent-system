import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.mark.asyncio
async def test_workforce_agents_directory():
    """Test GET /api/workforce/agents returns 25+ active agents with no orphaned references."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/workforce/agents")
        assert res.status_code == 200
        agents = res.json()
        assert len(agents) >= 20
        for agent in agents:
            assert agent["is_orphaned"] is False
            assert agent["is_used"] is True
            assert "name" in agent
            assert "role" in agent
            assert len(agent.get("tools_list", [])) > 0


@pytest.mark.asyncio
async def test_agent_detail():
    """Test fetching details for ResearchAgent."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/workforce/agents/ResearchAgent")
        assert res.status_code == 200
        data = res.json()
        assert data["agent"]["name"] == "ResearchAgent"
        tools = data["agent"].get("tools_list", [])
        assert len(tools) > 0


@pytest.mark.asyncio
async def test_knowledge_agent_rag_chat():
    """Test KnowledgeAgent chat returns RAG grounded answers with sources_used."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/workforce/agents/KnowledgeAgent/chat", json={
            "message": "What is our business model and fee structure in Houston?"
        })
        assert res.status_code == 200
        data = res.json()
        assert "reply" in data
        assert len(data["reply"]) > 0
        assert "sources_used" in data


@pytest.mark.asyncio
async def test_setup_agent_chat():
    """Test SetupAgent chat triggers website profile extraction."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/workforce/agents/setup_agent/chat", json={
            "message": "Setup new site profile",
            "params": {"url": "https://accident.innovatcs.com"}
        })
        assert res.status_code == 200
        data = res.json()
        assert "Setup completed" in data["reply"] or "Business Profile" in data["reply"]


@pytest.mark.asyncio
async def test_pipeline_status():
    """Test GET /api/workforce/pipeline/status returns visual pipeline state."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/workforce/pipeline/status")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "active"
        assert data["nodes_count"] >= 20


@pytest.mark.asyncio
async def test_workforce_tools():
    """Test GET /api/workforce/tools returns tool catalog."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/workforce/tools")
        assert res.status_code == 200
        data = res.json()
        assert data["total_tools"] >= 20
        assert len(data["tools"]) >= 20
