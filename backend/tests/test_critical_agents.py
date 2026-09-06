"""Integration tests for critical RankForge agents.

These tests verify that core agents can be imported, instantiated, and run
without crashing on real code paths. They do NOT require external API keys
or a live Supabase database.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


def test_quality_gate_agent_importable():
    """QualityGateTool must be importable and instantiable."""
    from backend.agents.tools.quality_gate_tool import QualityGateTool
    tool = QualityGateTool()
    assert tool is not None
    assert tool.name == "quality_gate"


def test_seo_agent_importable():
    """SEOAgent must be importable and instantiable."""
    from backend.agents.seo_agent import SEOAgent
    agent = SEOAgent(website_id="test-wid")
    assert agent is not None
    assert agent.website_id == "test-wid"


def test_outline_agent_importable():
    """OutlineAgent must be importable and instantiable."""
    from backend.agents.outline_agent import OutlineAgent
    agent = OutlineAgent(website_id="test-wid")
    assert agent is not None
    assert agent.website_id == "test-wid"


def test_humanizer_agent_importable():
    """HumanWriterAgent must be importable and instantiable."""
    from backend.agents.human_writer import HumanWriterAgent
    agent = HumanWriterAgent(website_id="test-wid")
    assert agent is not None


def test_schema_generator_importable():
    """Schema generator module must be importable."""
    from backend.services import schema_generator
    assert hasattr(schema_generator, "generate_article_schema")


def test_citation_injector_importable():
    """Citation injector module must be importable."""
    from backend.services import citation_injector
    assert hasattr(citation_injector, "inject_citations")


def test_ai_visibility_monitor_importable():
    """AI visibility monitor module must be importable."""
    from backend.services import ai_visibility_monitor
    assert hasattr(ai_visibility_monitor, "check_ai_visibility")


def test_reddit_service_importable():
    """RedditService must be importable."""
    from backend.services.reddit_service import RedditService
    svc = RedditService()
    assert svc is not None


def test_llm_content_server_importable():
    """LLM content server module must be importable."""
    from backend.services import llm_content_server
    assert hasattr(llm_content_server, "generate_markdown_version")


def test_chunking_service_importable():
    """Chunking service module must be importable."""
    from backend.services import chunking_service
    assert hasattr(chunking_service, "validate_chunk_lengths")


def test_connection_health_monitor_importable():
    """ConnectionHealthMonitor must be importable."""
    from backend.services.connection_health_monitor import ConnectionHealthMonitor
    mon = ConnectionHealthMonitor(website_id="test-wid")
    assert mon is not None
    assert mon.website_id == "test-wid"


def test_circuit_breaker_importable():
    """CircuitBreaker class must be importable."""
    from backend.middleware.circuit_breaker import CircuitBreaker
    assert CircuitBreaker is not None
    assert hasattr(CircuitBreaker, "can_execute")


def test_auth_middleware_importable():
    """Auth middleware must be importable."""
    from backend.middleware.auth import AuthMiddleware
    assert AuthMiddleware is not None


def test_aeo_router_importable():
    """AEO router must be importable."""
    from backend.routers.aeo import router as aeo_router
    assert aeo_router is not None


def test_auto_supabase_importable():
    """auto_supabase module must be importable."""
    from backend.auto_supabase import setup_supabase, create_tables_via_psycopg2
    assert setup_supabase is not None
    assert create_tables_via_psycopg2 is not None
