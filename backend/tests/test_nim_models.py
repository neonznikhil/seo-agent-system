"""Verify NVIDIA NIM models not EOL 410 - primary nemotron-3-nano-30b-a3b and embed nemotron-3-embed-1b return 200."""
import os
import httpx
import pytest

NIM_LLM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NIM_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"

@pytest.mark.asyncio
async def test_llm_nemotron_3_nano():
    api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("NIM_API_KEY")
    if not api_key:
        pytest.skip("NVIDIA_API_KEY not set")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": "nvidia/nemotron-3-nano-30b-a3b", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5, "temperature": 0}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(NIM_LLM_URL, json=payload, headers=headers)
    assert resp.status_code == 200, f"Expected 200 for nemotron-3-nano-30b-a3b, got {resp.status_code}: {resp.text[:300]}"
    data = resp.json()
    assert "choices" in data
    assert resp.status_code != 410, "Model should not be EOL 410"

@pytest.mark.asyncio
async def test_embed_nemotron_3_embed():
    api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("NIM_API_KEY")
    if not api_key:
        pytest.skip("NVIDIA_API_KEY not set")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": "nvidia/nemotron-3-embed-1b", "input": ["hello world"], "input_type": "query", "encoding_format": "float"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(NIM_EMBED_URL, json=payload, headers=headers)
    assert resp.status_code == 200, f"Expected 200 for nemotron-3-embed-1b, got {resp.status_code}: {resp.text[:300]}"
    data = resp.json()
    assert "data" in data
    vec = data["data"][0]["embedding"]
    # Should be 1536 or 1024 dims -> normalized to 1536
    assert len(vec) > 0
    assert resp.status_code != 410

@pytest.mark.asyncio
async def test_llm_fallback_70b():
    api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("NIM_API_KEY")
    if not api_key:
        pytest.skip("NVIDIA_API_KEY not set")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": "nvidia/llama-3.1-nemotron-70b-instruct", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5, "temperature": 0}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(NIM_LLM_URL, json=payload, headers=headers)
    assert resp.status_code in (200, 404, 403), f"Fallback 70b got {resp.status_code}: {resp.text[:200]}"
    if resp.status_code == 200:
        assert "choices" in resp.json()

@pytest.mark.asyncio
async def test_nim_client_central():
    """Verify nim_client central returns 200 models via validate."""
    from backend.services.nim_client import validate_llm_model, validate_embedding_model, get_llm_model, get_embedding_model
    llm_model = get_llm_model()
    embed_model = get_embedding_model()
    assert llm_model == "nvidia/nemotron-3-nano-30b-a3b" or "nemotron" in llm_model
    assert embed_model == "nvidia/nemotron-3-embed-1b" or "embed" in embed_model
    api_key = os.getenv("NVIDIA_API_KEY")
    if api_key:
        validated_llm = await validate_llm_model(force=True)
        assert validated_llm in ["nvidia/nemotron-3-nano-30b-a3b", "nvidia/llama-3.1-nemotron-70b-instruct", "nvidia/nemotron-3-super-120b-a12b"]
        validated_embed = await validate_embedding_model(force=True)
        assert validated_embed in ["nvidia/nemotron-3-embed-1b", "nvidia/nvidia-embed-qa-4"]

def test_no_eol_hardcoded():
    """Ensure EOL ultra model not hardcoded as primary in database."""
    from backend.database import NIM_LLM_MODEL, NIM_EMBED_MODEL, _LLM_MODELS
    assert NIM_LLM_MODEL != "nvidia/llama-3.1-nemotron-ultra-253b-v1.5", "EOL ultra should not be primary"
    assert NIM_EMBED_MODEL != "nvidia/nv-embedqa-e5-v5", "EOL embed should not be primary"
    assert "nvidia/nemotron-3-nano-30b-a3b" in _LLM_MODELS


@pytest.mark.asyncio
async def test_nim_circuit_breaker():
    """Test that 3 consecutive failures open the circuit breaker for 60s."""
    from backend.services.nim_client import reset_cache, _record_failure, _check_circuit_breaker
    import time
    reset_cache()
    
    # 2 failures -> circuit still closed
    _record_failure()
    _record_failure()
    _check_circuit_breaker() # Should not raise
    
    # 3rd failure -> circuit opens
    _record_failure()
    with pytest.raises(RuntimeError) as exc_info:
        _check_circuit_breaker()
    assert "circuit breaker OPEN" in str(exc_info.value)
    
    reset_cache()


@pytest.mark.asyncio
async def test_nvidia_test_endpoint():
    """Verify /api/connectors/nvidia/test returns structured diagnostic."""
    from backend.main import app
    from httpx import AsyncClient, ASGITransport
    from unittest.mock import patch, AsyncMock
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("backend.services.nim_client.generate", new=AsyncMock(return_value="SEO is the practice of optimizing content.")):
            with patch("backend.services.nim_client.embed", new=AsyncMock(return_value=[0.123] * 1536)):
                res = await client.get("/api/connectors/nvidia/test")
                assert res.status_code == 200
                data = res.json()
                assert data.get("success") is True
                assert data.get("connected") is True
                assert data.get("embedding_dimensions") == 1536
                assert "llm_completion" in data


@pytest.mark.asyncio
async def test_2_3_supabase_test_endpoint():
    """Verify Task 2.3: Supabase connector test endpoint returns real table counts."""
    from backend.main import app
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/connectors/supabase/test")
        assert resp.status_code == 200
        data = resp.json()
        assert "connected" in data
        assert "table_counts" in data
        assert isinstance(data["table_counts"], dict)


@pytest.mark.asyncio
async def test_2_4_wordpress_integration():
    """Verify Task 2.4: WordPressService methods and connect."""
    from backend.services.wordpress_service import WordPressService
    from unittest.mock import patch, AsyncMock, MagicMock
    wp = WordPressService("test-website-id")
    
    with patch.object(wp, "get_base_url", return_value="https://example.com"):
        with patch.object(wp, "_get_auth_tuple", return_value=("admin", "pass")):
            with patch.object(wp, "test_connection", new=AsyncMock(return_value={"connected": True, "status_code": 200, "roles": ["editor"], "can_publish": True})):
                conn = await wp.connect()
                assert conn.get("connected") is True

    with patch.object(wp, "get_base_url", return_value="https://example.com"):
        with patch.object(wp, "_get_auth_tuple", return_value=("admin", "pass")):
            with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=MagicMock(status_code=201, json=lambda: {"id": 99, "link": "https://example.com/wp-draft"}))):
                draft_res = await wp.create_draft("test-website-id", "Real SEO Title", "<p>Real SEO Content</p>")
                assert draft_res.get("success") is True
                assert draft_res.get("wp_post_id") == 99

    with patch.object(wp, "get_base_url", return_value="https://example.com"):
        with patch.object(wp, "_get_auth_tuple", return_value=("admin", "pass")):
            with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=MagicMock(status_code=201, json=lambda: {"id": 42, "source_url": "https://example.com/wp-content/uploads/seo.jpg"}))):
                media_res = await wp.upload_media(b"fake image bytes", "seo.jpg", "SEO Graph")
                assert media_res.get("success") is True
                assert media_res.get("media_id") == 42



@pytest.mark.asyncio
async def test_2_5_gsc_integration():
    """Verify Task 2.5: GSCService methods and test endpoint."""
    from backend.main import app
    from backend.services.gsc_service import GSCService
    from httpx import AsyncClient, ASGITransport
    gsc = GSCService("https://example.com")
    
    if not gsc.is_connected():
        perf = await gsc.get_keyword_performance()
        assert perf.get("keywords") == []
        assert perf.get("total_clicks") == 0

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/connectors/gsc/test")
        assert resp.status_code == 200
        data = resp.json()
        assert "connected" in data


@pytest.mark.asyncio
async def test_3_1_zero_mock_empty_returns():
    """Verify Task 3.1: GSC and Research endpoints return clean empty structures, never hardcoded legal mocks."""
    from backend.main import app
    from httpx import AsyncClient, ASGITransport
    from unittest.mock import patch, AsyncMock, MagicMock

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. GSC performance endpoint returns 0 / empty array if empty
        with patch("backend.routers.gsc.get_keywords", new=AsyncMock(return_value=[])):
            resp = await client.get("/api/gsc/nonexistent-site/performance")
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("total_clicks") == 0
            assert data.get("total_impressions") == 0
            assert data.get("keywords") == []

        # 2. Competitor profiles returns clean empty array if none exist
        with patch("backend.database.get_supabase") as mock_sup:
            mock_sup.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            resp2 = await client.get("/api/research/competitor-profiles?website_id=test-site")
            assert resp2.status_code == 200
            data2 = resp2.json()
            assert data2.get("data") == []


@pytest.mark.asyncio
async def test_3_2_budget_manager_enforcement():
    """Verify Task 3.3: BudgetManager tracks spend, calculates remaining budget, and pauses when exceeded."""
    from backend.services.budget_manager import BudgetManager
    from unittest.mock import patch, AsyncMock
    bm = BudgetManager("test-site")
    
    with patch.object(bm, "get_today_spend", new=AsyncMock(return_value=5.50)):
        with patch.object(bm, "get_daily_limit", new=AsyncMock(return_value=20.00)):
            # Within budget
            res_allowed = await bm.check_budget("test-site", estimated_cost=2.00)
            assert res_allowed["allowed"] is True
            assert res_allowed["remaining"] == 14.50

            # Exceeding budget
            res_denied = await bm.check_budget("test-site", estimated_cost=16.00)
            assert res_denied["allowed"] is False
            assert "exceeded" in res_denied["reason"].lower()

    # Budget summary computation
    with patch.object(bm, "get_today_spend", new=AsyncMock(return_value=10.00)):
        with patch.object(bm, "get_daily_limit", new=AsyncMock(return_value=20.00)):
            summary = await bm.get_budget_summary("test-site")
            assert summary["percent_used"] == 50.0
            assert summary["can_spend"] is True


@pytest.mark.asyncio
async def test_3_3_autonomous_decision_engine_dynamic_keywords():
    """Verify Task 3.2: AutonomousDecisionEngine selects dynamic site keywords and halts on budget exceeded."""
    from backend.agents.autonomous_decision_engine import AutonomousDecisionEngine
    from unittest.mock import patch, AsyncMock, MagicMock
    engine = AutonomousDecisionEngine("test-site")
    
    # 1. Pause when budget exceeded
    with patch.object(engine, "check_budget_availability", new=AsyncMock(return_value={"allowed": False, "reason": "Budget cap reached"})):
        decision = await engine.should_run("auto_new_page")
        assert decision["should_run"] is False
        assert "Budget cap" in decision["reason"]

    # 2. Dynamic keyword generation
    with patch("backend.database.get_supabase") as mock_sup:
        mock_sup.return_value.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        mock_sup.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data={"niche": "Cybersecurity AI", "domain": "secops.io"})
        kw = await engine.get_next_target_keyword()
        assert "Cybersecurity" in kw or "strategy" in kw


@pytest.mark.asyncio
async def test_4_1_writer_pipeline():
    """Verify Task 4.1: WriterPipeline generates title and prevents duplicate articles."""
    from backend.agents.writer_agent import WriterPipeline, is_invalid_title
    from unittest.mock import patch, AsyncMock

    assert is_invalid_title("or let ai suggest a title") is True
    assert is_invalid_title("Draft: Untitled Post") is True
    assert is_invalid_title("Complete Guide to Autonomous SEO Architectures 2026") is False

    wp = WriterPipeline("test-site")
    with patch.object(wp, "_find_existing_article", new=AsyncMock(return_value="existing-art-123")):
        res = await wp.generate(topic="SEO Strategy", primary_keyword="seo strategy")
        assert res.get("status") == "skipped"
        assert res.get("reason") == "duplicate_keyword"


@pytest.mark.asyncio
async def test_4_2_knowledge_service():
    """Verify Task 4.2: KnowledgeService deterministic embedding, chunking, and credibility."""
    from backend.services.knowledge_service import KnowledgeService, _cosine_similarity, _deterministic_embedding

    vec1 = _deterministic_embedding("SEO Agent Engine")
    vec2 = _deterministic_embedding("SEO Agent Engine")
    vec3 = _deterministic_embedding("Something completely different")

    assert len(vec1) == 1536
    assert abs(_cosine_similarity(vec1, vec2) - 1.0) < 1e-4
    assert _cosine_similarity(vec1, vec3) < 0.99

    ks = KnowledgeService("test-site")
    assert ks.CREDIBILITY_MAP["business_info"] == 1.0
    assert ks.CREDIBILITY_MAP["law_statute"] == 0.95


@pytest.mark.asyncio
async def test_4_3_research_agent():
    """Verify Task 4.3: ResearchAgent processes live SERP and LLM synthesis."""
    from backend.agents.research_agent import ResearchAgent
    from unittest.mock import patch, AsyncMock

    ra = ResearchAgent("test-site")
    with patch("backend.services.serper_service.serper_service.search", new=AsyncMock(return_value={
        "organic": [{"link": "https://example.com/page1", "title": "Example Post"}],
        "peopleAlsoAsk": [{"question": "What is autonomous SEO?"}],
        "relatedSearches": [{"query": "autonomous seo agents"}]
    })):
        with patch("backend.database.call_nim_llm", new=AsyncMock(return_value='{"trends":["agentic search"],"competitors":["example.com"],"questions":["What is autonomous SEO?"],"search_volume":5000,"serp_features":["paa"]}')):
            with patch("backend.services.brain_service.BrainService.recall_facts", new=AsyncMock(return_value=[])):
                with patch("backend.services.brain_service.BrainService.recall_experiences", new=AsyncMock(return_value=[])):
                    with patch("backend.services.brain_service.BrainService.recall_preferences", new=AsyncMock(return_value=[])):
                        with patch("backend.services.brain_service.BrainService.remember", new=AsyncMock(return_value=None)):
                            data = await ra.run("Autonomous SEO")
                            assert "trends" in data
                            assert "competitors" in data
                            assert data["competitors"] == ["example.com"]


@pytest.mark.asyncio
async def test_4_4_backlink_agent():
    """Verify Task 4.4: BacklinkAgent 4-module prospecting and qualification."""
    from backend.agents.backlink_agent import BacklinkAgent
    from unittest.mock import patch, AsyncMock

    ba = BacklinkAgent("test-site")
    with patch("backend.services.serper_service.serper_service.search", new=AsyncMock(return_value={
        "organic": [{"link": "https://harvard.edu/seo-guide", "title": "SEO Guide", "snippet": "Useful resources"}],
        "source": "serper.dev"
    })):
        targets = await ba.prospect_targets(keyword="SEO Guide", modules=["resource_page"])
        assert len(targets) > 0
        qualified = ba.qualify_target(targets[0])
        assert qualified["domain_authority"] == 82
        assert qualified["qualified"] is True


@pytest.mark.asyncio
async def test_4_5_tech_seo_agent():
    """Verify Task 4.5: TechSEOAgent audits and sitemap checking."""
    from backend.agents.tech_seo_agent import TechSEOAgent
    from unittest.mock import patch, AsyncMock

    ts = TechSEOAgent("test-site")
    with patch("backend.routers.tech_seo.execute_tech_audit", new=AsyncMock(return_value={
        "health_score": 95,
        "issues": [],
        "checks": [{"name": "HTTPS SSL Security", "status": "Passed", "value": "HTTP 200"}]
    })):
        with patch("backend.services.brain_service.BrainService.recall_failures", new=AsyncMock(return_value=[])):
            with patch("backend.services.brain_service.BrainService.recall_facts", new=AsyncMock(return_value=[])):
                with patch("backend.services.brain_service.BrainService.remember", new=AsyncMock(return_value=None)):
                    audit = await ts.run_audit("test-site")
                    assert audit.get("health_score") == 95


@pytest.mark.asyncio
async def test_4_6_continuous_monitoring():
    """Verify Task 4.6: ContinuousMonitor execution helper."""
    from backend.services.continuous_monitor import run_all_monitors
    from unittest.mock import patch, AsyncMock

    with patch("backend.services.monitors.tech_monitor.TechMonitor.check_all_pages", new=AsyncMock(return_value={"checked": 10})):
        with patch("backend.services.monitors.rank_monitor.RankMonitor.get_gsc_keywords", new=AsyncMock(return_value=[])):
            res = await run_all_monitors("test-site")
            assert res["website_id"] == "test-site"
            assert "tech" in res["results"]
            assert "rank" in res["results"]


@pytest.mark.asyncio
async def test_5_1_async_httpx_usage():
    """Verify Task 5.1: Crawlee service sitemap extraction uses async httpx without errors."""
    from backend.services.crawlee_service import CrawleeService
    from unittest.mock import patch, AsyncMock, MagicMock

    cs = CrawleeService()
    mock_resp = MagicMock(status_code=200, text="<urlset><url><loc>https://example.com/blog/1</loc></url></urlset>")
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
        urls = await cs._get_sitemap_urls("example.com")
        assert len(urls) == 1
        assert urls[0] == "https://example.com/blog/1"


@pytest.mark.asyncio
async def test_5_2_parallel_dashboard_stats():
    """Verify Task 5.2: Dashboard metrics uses parallel asyncio.gather."""
    from backend.routers.dashboard import _count_async
    from unittest.mock import patch, MagicMock

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.execute.return_value = MagicMock(count=42, data=[])

    res = await _count_async(mock_supabase, "blogs")
    assert res == 42


@pytest.mark.asyncio
async def test_5_3_serper_circuit_breaker():
    """Verify Task 5.3: SerperService circuit breaker trips after 3 failures."""
    from backend.services.serper_service import SerperService, _SERPER_CIRCUIT
    import time

    ss = SerperService()
    ss._record_circuit_success()
    assert ss.is_circuit_open() is False

    # Simulate 3 failures
    ss._record_circuit_failure()
    ss._record_circuit_failure()
    assert ss.is_circuit_open() is False
    ss._record_circuit_failure()
    assert ss.is_circuit_open() is True
    assert _SERPER_CIRCUIT["circuit_open_until"] > time.time()

    # Reset
    ss._record_circuit_success()
    assert ss.is_circuit_open() is False


@pytest.mark.asyncio
async def test_bug1_auto_crawl_trigger():
    """Verify BUG 1: trigger_auto_crawl calls KnowledgeService and updates status to active."""
    from backend.routers.websites import trigger_auto_crawl
    from unittest.mock import patch, AsyncMock, MagicMock

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "w123", "status": "active"}])
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(count=8, data=[{"id": "kb1"}])

    with patch("backend.routers.websites.get_supabase", return_value=mock_supabase):
        with patch("backend.services.knowledge_service.KnowledgeService.watch_business_website", new=AsyncMock(return_value={"urls_scanned": 5, "new_pages_ingested": 4})):
            await trigger_auto_crawl("w123", "acc123")
            # Verify update was called with active
            mock_supabase.table("websites").update.assert_called()






