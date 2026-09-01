import logging
import pytest

from agents.tools.quality_gate_tool import QualityGateTool

logger = logging.getLogger("backend.tests.test_quality_gate")


@pytest.mark.skipif(not __import__("os").getenv("SUPABASE_URL"), reason="SUPABASE_URL required")
def test_quality_gate_spell_fail(monkeypatch):
    tool = QualityGateTool()
    tool._website_id = "wid-1"
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.call_nim_llm", lambda prompt, system, website_id=None: "FAIL: spelling errors detected")
    result = tool._run("cl-1")
    assert result == "needs_revision"


@pytest.mark.skipif(not __import__("os").getenv("SUPABASE_URL"), reason="SUPABASE_URL required")
def test_quality_gate_tone_low_fail(monkeypatch):
    tool = QualityGateTool()
    tool._website_id = "wid-1"
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.call_nim_llm", lambda prompt, system, website_id=None: "PASS")
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.cosine_similarity", lambda a, b: 0.1)
    result = tool._run("cl-2")
    assert result == "needs_revision"


@pytest.mark.skipif(not __import__("os").getenv("SUPABASE_URL"), reason="SUPABASE_URL required")
def test_quality_gate_knowledge_contradict_fail(monkeypatch):
    tool = QualityGateTool()
    tool._website_id = "wid-1"
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.call_nim_llm", lambda prompt, system, website_id=None: "FAIL: contradicts known facts")
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.cosine_similarity", lambda a, b: 0.9)
    result = tool._run("cl-3")
    assert result == "needs_revision"


@pytest.mark.skipif(not __import__("os").getenv("SUPABASE_URL"), reason="SUPABASE_URL required")
def test_quality_gate_pass(monkeypatch):
    tool = QualityGateTool()
    tool._website_id = "wid-1"
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.call_nim_llm", lambda prompt, system, website_id=None: "PASS")
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.cosine_similarity", lambda a, b: 0.9)
    result = tool._run("cl-4")
    assert result == "pending_approval"
