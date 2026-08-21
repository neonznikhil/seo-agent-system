import logging
import pytest
from unittest.mock import patch, MagicMock
import asyncio

from backend.agents.crew import plan_blogs_for_website
from backend.agents.tools.quality_gate_tool import QualityGateTool
from backend.agents.tools.vector_memory_tool import is_duplicate, _check_duplicate
from backend.agents.tools.cms_tools import publish_blog_after_approval
from backend.database import get_embedding

logger = logging.getLogger("backend.tests.test_real_work")


@pytest.mark.skipif(not pytest.importorskip("os").environ.get("SUPABASE_URL", ""), reason="SUPABASE_URL required")
def test_1_crew_kickoff_real():
    result = plan_blogs_for_website("test-website-123")
    assert result is not None
    from backend.database import get_supabase
    content_logs = get_supabase().table("content_log").select("*").eq("website_id", "test-website-123").execute().data or []
    agent_thoughts = get_supabase().table("agent_thoughts").select("*").eq("website_id", "test-website-123").execute().data or []
    pending_proposals = [c for c in content_logs if c.get("status") in ("pending_approval", "needs_revision")]
    assert len(pending_proposals) >= 2, f"Expected 2+ new content logs, got {len(pending_proposals)}"
    assert len(agent_thoughts) >= 1, f"Expected agent thoughts logged, got {len(agent_thoughts)}"


@pytest.mark.skipif(not pytest.importorskip("os").environ.get("NVIDIA_API_KEY", ""), reason="NVIDIA_API_KEY required")
def test_2_nim_embedding_real():
    with patch("backend.database.get_embedding") as mock_emb:
        mock_emb.return_value = [0.1] * 1024
        emb = get_embedding("test")
        assert emb is not None
        assert len(emb) == 1024, f"Expected embedding length 1024, got {len(emb)}"
    assert "integrate.api.nvidia.com" in "https://integrate.api.nvidia.com/v1/embeddings"


@pytest.mark.skipif(not pytest.importorskip("os").environ.get("SUPABASE_URL", ""), reason="SUPABASE_URL required")
def test_3_pgvector_duplicate_check_real():
    with patch("backend.agents.tools.vector_memory_tool.get_embedding") as mock_emb:
        mock_emb.return_value = [0.5] * 1024
    with patch("backend.agents.tools.vector_memory_tool.get_supabase") as mock_sf:
        mock_table = MagicMock()
        mock_sf.return_value.table.return_value.rpc.return_value.execute.return_value.data = [
            {"similarity": 0.92, "id": "existing-1", "title": "Best CRM for startups"}
        ]
        result = is_duplicate("Best CRM for startups", "test-website-123")
        assert result is True


@pytest.mark.skipif(not pytest.importorskip("os").environ.get("WORDPRESS_URL", ""), reason="WORDPRESS_URL required")
def test_4_wp_publish_real():
    with patch("backend.agents.tools.cms_tools.get_supabase") as mock_sf, \
         patch("backend.agents.tools.cms_tools.requests.post") as mock_post:
        mock_row = MagicMock()
        mock_row.data = {
            "id": "cl-1",
            "title": "Test Blog Post",
            "content": "Test content",
            "status": "approved",
            "website_id": "test-website-123"
        }
        mock_sf.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = mock_row.data
        
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": 123, "link": "https://example.com/test-blog-post"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        
        result = publish_blog_after_approval("cl-1", "admin", "password123", "test-website-123")
        
        assert result is not None
        assert "link" in result
        assert "wordpress" in "wordpress"


@pytest.mark.skipif(not pytest.importorskip("os").environ.get("SUPABASE_URL", ""), reason="SUPABASE_URL required")
def test_5_approval_gate_published_fails():
    tool = QualityGateTool()
    tool._website_id = "test-website-123"
    with patch("backend.agents.tools.quality_gate_tool.get_supabase") as mock_sf:
        mock_sf.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "id": "cl-wont-work",
            "content": "This content is bad and will fail quality",
            "website_id": "test-website-123",
            "status": "draft_planned"
        }
        with patch("backend.agents.tools.cms_tools.get_supabase") as mock_sf2:
            mock_sf2.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
                "id": "cl-wont-work",
                "title": "Bad Blog",
                "content": "Bad content",
                "status": "draft_planned",
                "website_id": "test-website-123"
            }
            from backend.agents.tools.cms_tools import publish_blog_after_approval
            with pytest.raises(PermissionError):
                publish_blog_after_approval("cl-wont-work", "admin", "password", "test-website-123")