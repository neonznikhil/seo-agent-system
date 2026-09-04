import logging
import pytest
import re
import math
from unittest.mock import patch, MagicMock, AsyncMock
from backend.agents.tools.quality_gate_tool import QualityGateTool

logger = logging.getLogger("backend.tests.test_quality_gate")


def _make_table_chain(row_data, use_single=False):
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq

    if use_single:
        mock_single = MagicMock()
        mock_eq.single.return_value = mock_single
        mock_exec = MagicMock()
        mock_single.execute.return_value = mock_exec
        mock_exec.data = row_data if isinstance(row_data, dict) else (row_data[0] if row_data else {})
    else:
        mock_limit = MagicMock()
        mock_eq.limit.return_value = mock_limit
        mock_exec = MagicMock()
        mock_limit.execute.return_value = mock_exec
        mock_exec.data = row_data

    return mock_table


def _make_mock_supabase():
    mock_sb = MagicMock()

    content_row = {
        "id": "cl-1",
        "content": "<h1>Test</h1>\n<p>Content with table and stats.</p>\n| col1 | col2 |\nThis is 50% growth and $1 million revenue.\n<h2>FAQ</h2>\n<h3>Q1?</h3>\n<p>A1.</p>\n<h3>Q2?</h3>\n<p>A2.</p>\n<h3>Q3?</h3>\n<p>A3.</p>\n<h3>Q4?</h3>\n<p>A4.</p>",
        "website_id": "wid-1",
    }

    table_map = {
        "content_log": [_make_table_chain(content_row, use_single=True)],
        "tone_profiles": [_make_table_chain([{"sample_embeddings": [[0.1, 0.2, 0.3]]}])],
        "knowledge_base": [_make_table_chain([{"fact": "We serve Houston."}])],
        "quality_checks": [_make_table_chain([])],
    }

    def _table_side_effect(name):
        chains = table_map.get(name, [_make_table_chain([])])
        return chains.pop(0) if chains else _make_table_chain([])

    mock_sb.table.side_effect = _table_side_effect
    return mock_sb


@pytest.mark.asyncio
async def test_quality_gate_spell_fail(monkeypatch):
    tool = QualityGateTool()
    tool._website_id = "wid-1"
    mock_sb = _make_mock_supabase()
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.get_supabase", lambda: mock_sb)
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.call_nim_llm", AsyncMock(return_value="FAIL: spelling errors detected"))
    result = await tool._run("cl-1")
    assert result == "needs_revision"


@pytest.mark.asyncio
async def test_quality_gate_tone_low_fail(monkeypatch):
    tool = QualityGateTool()
    tool._website_id = "wid-1"
    mock_sb = _make_mock_supabase()
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.get_supabase", lambda: mock_sb)
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.call_nim_llm", AsyncMock(return_value="PASS"))
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.cosine_similarity", lambda a, b: 0.1)
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.get_embedding", AsyncMock(return_value=[0.1, 0.2, 0.3]))
    result = await tool._run("cl-2")
    assert result == "needs_revision"


@pytest.mark.asyncio
async def test_quality_gate_knowledge_contradict_fail(monkeypatch):
    tool = QualityGateTool()
    tool._website_id = "wid-1"
    mock_sb = _make_mock_supabase()
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.get_supabase", lambda: mock_sb)
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.call_nim_llm", AsyncMock(return_value="FAIL: contradicts known facts"))
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.cosine_similarity", lambda a, b: 0.9)
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.get_embedding", AsyncMock(return_value=[0.1, 0.2, 0.3]))
    result = await tool._run("cl-3")
    assert result == "needs_revision"


@pytest.mark.asyncio
async def test_quality_gate_pass(monkeypatch):
    content = "<h1>Test</h1>\n<p>Content.</p>\n| a | b |\n50% growth.\nFAQ?\nFAQ?\nFAQ?\nFAQ?"

    tool = QualityGateTool()
    tool._website_id = "wid-1"
    mock_sb = _make_mock_supabase()
    mock_sb.table.side_effect = lambda name: (
        _make_table_chain({
            "id": "cl-1",
            "content": content,
            "website_id": "wid-1",
        }, use_single=True) if name == "content_log" else (
            _make_table_chain([{"sample_embeddings": [[0.1, 0.2, 0.3]]}]) if name == "tone_profiles" else (
                _make_table_chain([{"fact": "We serve Houston."}]) if name == "knowledge_base" else (
                    _make_table_chain([]) if name == "quality_checks" else _make_table_chain([])
                )
            )
        )
    )
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.get_supabase", lambda: mock_sb)
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.call_nim_llm", AsyncMock(return_value="PASS"))
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.cosine_similarity", lambda a, b: 0.9)
    monkeypatch.setattr("backend.agents.tools.quality_gate_tool.get_embedding", AsyncMock(return_value=[0.1, 0.2, 0.3]))
    result = await tool._run("cl-4")
    assert result == "pending_approval"
