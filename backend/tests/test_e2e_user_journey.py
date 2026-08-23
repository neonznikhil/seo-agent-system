import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.services.rag_service import RAGService
from backend.services.knowledge_service import KnowledgeService
from backend.agents.autonomous_decision_engine import AutonomousDecisionEngine


@pytest.mark.asyncio
async def test_full_10_step_user_journey():
    """Simulate complete 10-step autonomous user journey with zero mock data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # ---------------------------------------------------------
        # STEP 1: Connectors Status Verification
        # ---------------------------------------------------------
        res_conn = await client.get("/api/connectors/status")
        assert res_conn.status_code == 200
        conn_data = res_conn.json()
        assert conn_data["supabase"]["connected"] is True

        # ---------------------------------------------------------
        # STEP 2: Knowledge Ingestion
        # ---------------------------------------------------------
        ks = KnowledgeService(website_id="03b7febf-0c44-4830-a42a-cfcd84ae6464")
        ingest_res = await ks.ingest(
            content="Under Texas Section 16.003, personal injury claims in Houston must be filed within 2 years. Contingency fees are strictly 33.3% with zero upfront cost.",
            source_type="manual",
            title="Houston Injury Statute & Contingency Rules",
            explicit_type="business_info"
        )
        assert ingest_res["success"] is True

        # ---------------------------------------------------------
        # STEP 3: Fact-Check Validation
        # ---------------------------------------------------------
        res_val = await client.post("/api/knowledge/validate-all")
        assert res_val.status_code == 200

        # ---------------------------------------------------------
        # STEP 4: Hybrid Knowledge Search
        # ---------------------------------------------------------
        res_search = await client.get("/api/knowledge/search/hybrid?q=Houston+injury+statute&top_k=3")
        assert res_search.status_code == 200
        search_data = res_search.json()
        assert len(search_data.get("results", [])) >= 1

        # ---------------------------------------------------------
        # STEP 5: Strategic Business Goals Update
        # ---------------------------------------------------------
        res_goals = await client.post("/api/autonomous/goals", json={
            "target_articles_per_week": 5,
            "target_traffic_growth": 15.0,
            "focus_keywords": ["Houston car accident lawyer", "Texas commercial truck claims"]
        })
        assert res_goals.status_code == 200

        # ---------------------------------------------------------
        # STEP 6: Autonomous Decision Engine & Scheduler Triggers
        # ---------------------------------------------------------
        engine = AutonomousDecisionEngine(website_id="03b7febf-0c44-4830-a42a-cfcd84ae6464")
        decision = await engine.should_run("daily_search")
        assert "should_run" in decision

        # ---------------------------------------------------------
        # STEP 7: Workforce Agent Chat
        # ---------------------------------------------------------
        res_agent_chat = await client.post("/api/workforce/agents/KnowledgeAgent/chat", json={
            "message": "What is our contingency fee percentage in Houston?"
        })
        assert res_agent_chat.status_code == 200
        agent_data = res_agent_chat.json()
        assert "reply" in agent_data
        assert len(agent_data["reply"]) > 0

        # ---------------------------------------------------------
        # STEP 8: Production RAG Query with Citations
        # ---------------------------------------------------------
        rag = RAGService(website_id="03b7febf-0c44-4830-a42a-cfcd84ae6464")
        rag_res = await rag.rag_query(query="What is the statute of limitations in Houston Texas?", top_k=3)
        assert len(rag_res.get("answer", "")) > 0
        assert "hallucination_check" in rag_res

        # ---------------------------------------------------------
        # STEP 9: Dynamic llms.txt Verification
        # ---------------------------------------------------------
        res_llms = await client.get("/llms.txt")
        assert res_llms.status_code == 200
        assert "Acme" not in res_llms.text

        # ---------------------------------------------------------
        # STEP 10: Autonomy Overview Verification
        # ---------------------------------------------------------
        res_auto = await client.get("/api/autonomy")
        assert res_auto.status_code == 200
        auto_data = res_auto.json()
        assert "scheduler" in auto_data
        assert auto_data["scheduler"]["running"] is True or "timezone" in auto_data["scheduler"]
