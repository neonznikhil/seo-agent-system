"""Grounding bundle: richer real context in, zero invented filler out."""
import sys
import types
from unittest.mock import MagicMock

import pytest


def _chain(data):
    m = MagicMock()
    m.select.return_value = m
    m.eq.return_value = m
    m.limit.return_value = m
    m.order.return_value = m
    m.gte.return_value = m
    m.single.return_value = m
    exec_res = MagicMock()
    exec_res.data = data
    m.execute.return_value = exec_res
    return m


TABLES = {}


def _fake_supabase():
    mock_sb = MagicMock()
    mock_sb.table.side_effect = lambda name: _chain(TABLES.get(name, []))
    return mock_sb


def _install_stubs(monkeypatch, rag_hits=None, serp=None):
    rag_mod = types.ModuleType("services.rag_service")

    class _RAG:
        def __init__(self, website_id=None):
            pass

        async def retrieve(self, query=None, top_k=5, filters=None):
            return rag_hits or []

        async def rerank(self, query=None, hits=None, top_k=5):
            return hits or []

    rag_mod.RAGService = _RAG
    monkeypatch.setitem(sys.modules, "services.rag_service", rag_mod)

    ks_mod = types.ModuleType("services.knowledge_service")

    class _KS:
        def __init__(self, website_id=None):
            pass

        async def retrieve_relevant_hybrid(self, keyword=None, top_k=5):
            return []

    ks_mod.KnowledgeService = _KS
    monkeypatch.setitem(sys.modules, "services.knowledge_service", ks_mod)

    bv_mod = types.ModuleType("services.brand_voice_service")

    async def _load(website_id):
        return {"tone": "Plain", "verified_facts": ["Fact one"],
                "banned_phrases": [], "required_phrases": [],
                "good_examples": ["Approved example text"],
                "bad_examples": ["Rejected example text"]}

    bv_mod.load_brand_voice = _load
    bv_mod.build_brand_voice_block = lambda guide: "Tone: Plain"
    monkeypatch.setitem(sys.modules, "services.brand_voice_service", bv_mod)

    ser_mod = types.ModuleType("services.serper_service")
    ser_mod.serper_service = MagicMock()
    ser_mod.serper_service.api_key = ""
    monkeypatch.setitem(sys.modules, "services.serper_service", ser_mod)

    import backend.agents.crew_blog_writer as writer_mod
    monkeypatch.setattr(writer_mod, "get_supabase", _fake_supabase)
    return writer_mod


@pytest.mark.asyncio
async def test_no_invented_links_or_questions(monkeypatch):
    TABLES.clear()
    TABLES["websites"] = [{"id": "w1", "domain": "example.com"}]
    mod = _install_stubs(monkeypatch)
    bundle = await mod.build_grounding_bundle("w1", "injury claims")
    assert bundle["internal_links"] == []
    assert bundle["internal_links_provenance"] == "empty"
    assert bundle["paa_questions"] == []
    assert bundle["paa_provenance"] == "none"
    assert bundle["striking_keywords"] == []
    assert bundle["gsc_queries"] == []
    assert bundle["cannibalization_warning"] is None
    assert bundle["past_wins"] == []
    # Brand examples still flow through
    assert bundle["good_examples"] == ["Approved example text"]
    assert bundle["verified_facts"] == ["Fact one"]


@pytest.mark.asyncio
async def test_seo_context_from_measured_rows(monkeypatch):
    TABLES.clear()
    TABLES["websites"] = [{"id": "w1", "domain": "example.com"}]
    TABLES["rank_tracking"] = [
        {"target_keyword": "injury claims process", "current_position": 12,
         "wp_url": "https://example.com/a", "title": "A"},
        {"target_keyword": "injury claims process", "current_position": 4,
         "wp_url": "https://example.com/b", "title": "B"},
        {"target_keyword": "unrelated topic", "current_position": 15,
         "wp_url": "https://example.com/c", "title": "C"},
        {"target_keyword": "injury claims guide", "current_position": 3,
         "wp_url": "https://example.com/d", "title": "Winner"},
    ]
    TABLES["keyword_opportunities"] = [
        {"keyword": "injury claims timeline", "impressions": 900, "clicks": 12},
    ]
    mod = _install_stubs(monkeypatch)
    bundle = await mod.build_grounding_bundle("w1", "injury claims")
    striking = bundle["striking_keywords"]
    assert len(striking) == 1 and striking[0]["position"] == 12
    assert bundle["gsc_queries"][0]["keyword"] == "injury claims timeline"
    assert bundle["past_wins"][0]["position"] == 3
    # Two pages share topic terms -> cannibalization warning fires
    assert bundle["cannibalization_warning"] is not None


def test_writer_prompt_contains_examples_and_seo_block():
    import backend.agents.crew_blog_writer as mod
    import inspect
    src = inspect.getsource(mod._build_writer_task_prompt)
    assert "examples_block" in src
    assert "seo_context_block" in src
    assert "Do NOT invent links" in src
    template_src = mod.WRITER_TASK_PROMPT_TEMPLATE
    assert "{examples_block}" in template_src
    assert "{seo_context_block}" in template_src
