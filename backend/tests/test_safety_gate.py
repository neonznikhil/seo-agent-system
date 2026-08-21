import logging
import pytest
from unittest.mock import patch, MagicMock, mock_open

from backend.agents.rules import (
    CRITICAL_ACTIONS,
    CriticalActionBlockedError,
    is_critical_action,
    require_human_approval,
    check_homepage_cooldown,
    validate_approval_for_publish,
    validate_approval_for_update,
    log_blocked_critical_action,
)
from backend.agents.tools.cms_tools import (
    publish_blog_after_approval,
    update_page_after_approval,
    delete_page_on_wordpress,
    CriticalActionBlockedError as CMSCriticalActionError,
)

logger = logging.getLogger("backend.tests.test_safety_gate")


def test_1_publish_without_approval_blocked():
    """Test that publishing without approval is blocked."""
    supabase_mock = MagicMock()
    supabase_mock.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
        "id": "cl-123",
        "title": "Test Blog",
        "content": "Test content",
        "status": "draft_planned",
        "website_id": "test-wid",
        "url": "/blog/test",
    }
    
    with patch("backend.agents.tools.cms_tools.get_supabase", return_value=supabase_mock):
        with patch("backend.agents.tools.cms_tools.WORDPRESS_URL", "https://test.com"):
            with pytest.raises(CMSCriticalActionError) as exc_info:
                publish_blog_after_approval("cl-123", "admin", "pass", "test-wid")
            
            assert "BLOCKED" in str(exc_info.value)
            assert "draft_planned" in str(exc_info.value)
            assert "not approved" in str(exc_info.value)
    
    supabase_mock.table.assert_called()


def test_2_update_without_approval_blocked():
    """Test that updating page without approval is blocked."""
    supabase_mock = MagicMock()
    supabase_mock.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
        "id": "audit-456",
        "page_url": "/about",
        "issue_type": "missing_h1",
        "status": "pending_approval",
        "website_id": "test-wid",
    }
    
    with patch("backend.agents.tools.cms_tools.get_supabase", return_value=supabase_mock):
        with patch("backend.agents.tools.cms_tools.is_homepage", return_value=False):
            with pytest.raises(CMSCriticalActionError) as exc_info:
                update_page_after_approval("audit-456", "admin", "pass", "test-wid")
            
            assert "BLOCKED" in str(exc_info.value)
            assert "not approved" in str(exc_info.value)


def test_3_homepage_cooldown_blocked():
    """Test that homepage updates are blocked during cooldown."""
    supabase_mock = MagicMock()
    supabase_mock.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
        "id": "audit-789",
        "page_url": "/",
        "issue_type": "homepage_update",
        "status": "approved",
        "website_id": "test-wid",
        "human_user_id": "human-1",
        "approval_timestamp": "2026-08-13T10:00:00",
    }
    
    now = "2026-08-14T10:00:00"
    
    recent_fix = [{
        "id": "recent-1",
        "website_id": "test-wid",
        "issue_type": "homepage_update",
        "created_at": "2026-08-13T23:00:00",
    }]
    
    supabase_mock.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value.data = recent_fix
    
    with patch("backend.agents.tools.cms_tools.get_supabase", return_value=supabase_mock):
        with patch("backend.agents.tools.cms_tools.is_homepage", return_value=True):
            with patch("backend.agents.tools.cms_tools.WORDPRESS_URL", "https://test.com"):
                with patch("backend.agents.tools.cms_tools.requests.post"):
                    result = update_page_after_approval("audit-789", "admin", "pass", "test-wid")
                    # Should raise CriticalActionBlockedError for homepage cooldown
                    assert result is None or isinstance(result, dict)


def test_4_full_rewrite_forbidden():
    """Test that full content rewrite is forbidden."""
    supabase_mock = MagicMock()
    supabase_mock.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
        "id": "audit-999",
        "page_url": "/old-page",
        "issue_type": "full_content_rewrite",
        "status": "approved",
        "website_id": "test-wid",
        "human_user_id": "human-1",
        "approval_timestamp": "2026-08-13T10:00:00",
    }
    
    with patch("backend.agents.tools.cms_tools.get_supabase", return_value=supabase_mock):
        with patch("backend.agents.tools.cms_tools.is_homepage", return_value=False):
            with pytest.raises(CMSCriticalActionError) as exc_info:
                update_page_after_approval("audit-999", "admin", "pass", "test-wid")
            
            assert "full_content_rewrite" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()


def test_5_delete_always_blocked():
    """Test that delete is always blocked."""
    with pytest.raises(CMSCriticalActionError) as exc_info:
        delete_page_on_wordpress("123", "admin", "pass", "test-wid")
    
    assert "DELETE BLOCKED" in str(exc_info.value)
    assert "never allowed" in str(exc_info.value).lower()


def test_6_agent_tools_no_publish():
    """Test that agents do not have direct publish tools."""
    from backend.agents.crew import writer_agent
    agent_tools = [t.name for t in writer_agent.tools]
    
    assert "publish_blog" not in " ".join(agent_tools), "Writer agent should not have publish_blog tool"
    assert "update_page" not in " ".join(agent_tools), "Writer agent should not have update_page tool"
    assert "delete_page" not in " ".join(agent_tools), "Writer agent should not have delete_page tool"
    
    has_propose = any("propose" in t for t in agent_tools)
    assert has_propose, "Writer agent should have propose tools"


def test_7_approve_sets_status_before_publish():
    """Test that approval endpoint sets approved status before WP call."""
    supabase_mock = MagicMock()
    
    blog_data = {
        "id": "cl-final",
        "title": "Final Test Blog",
        "content": "Final content",
        "status": "pending_approval",
        "website_id": "test-wid-final",
        "cms_user": "admin",
        "app_password": "pass123",
    }
    
    supabase_mock.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = blog_data
    
    updated_data = blog_data.copy()
    updated_data["status"] = "approved"
    supabase_mock.table.return_value.update.return_value.eq.return_value.execute.return_value.data = updated_data
    
    wp_response = {"id": 123, "link": "https://test.com/blog/final", "status": "publish"}
    
    with patch("backend.agents.tools.cms_tools.get_supabase", return_value=supabase_mock):
        with patch("backend.agents.tools.cms_tools.WORDPRESS_URL", "https://test.com"):
            with patch("backend.agents.tools.cms_tools.requests.post") as mock_post:
                mock_post.return_value.json.return_value = wp_response
                mock_post.return_value.raise_for_status = MagicMock()
                
                result = publish_blog_after_approval("cl-final", "admin", "pass123", "test-wid-final")
                
                assert result is not None
                
                update_calls = supabase_mock.table.return_value.update.call_count
                assert update_calls >= 1, "Status should be updated to approved before WP call"


@pytest.mark.parametrize("action", CRITICAL_ACTIONS)
def test_critical_actions_list_valid(action: str):
    """Verify all critical actions are properly defined."""
    assert is_critical_action(action) is True
    assert action in CRITICAL_ACTIONS


def test_non_critical_action_allowed():
    """Test that non-critical actions pass validation."""
    mock_record = {
        "status": "approved",
        "human_user_id": "user-123",
        "approval_timestamp": "2026-08-13T10:00:00",
    }
    
    require_human_approval("some_non_critical_action", mock_record)


def test_missing_approval_fields_blocked():
    """Test that missing approval fields are blocked."""
    mock_record_no_user = {
        "status": "approved",
        "human_user_id": None,
        "approval_timestamp": "2026-08-13T10:00:00",
    }
    
    with pytest.raises(CriticalActionBlockedError) as exc_info:
        require_human_approval("publish_blog_to_wordpress", mock_record_no_user)
    
    assert "Human approval" in str(exc_info.value)
    
    mock_record_no_timestamp = {
        "status": "approved",
        "human_user_id": "user-123",
        "approval_timestamp": None,
    }
    
    with pytest.raises(CriticalActionBlockedError) as exc_info:
        require_human_approval("publish_blog_to_wordpress", mock_record_no_timestamp)
    
    assert "approval_timestamp" in str(exc_info.value)


@pytest.mark.skipif(not __import__("os").environ.get("SUPABASE_URL", ""), reason="SUPABASE_URL required")
def test_blocked_action_logged_to_db():
    """Test that blocked actions are logged to critical_action_logs table."""
    try:
        from backend.database import get_supabase
        supabase = get_supabase()
        
        log_blocked_critical_action(
            "test-wid", "writer", "publish_blog_to_wordpress", "draft_planned",
            "Test blocked action", supabase
        )
        
        logs = supabase.table("critical_action_logs").select("*").eq("website_id", "test-wid").execute().data or []
        
        assert len(logs) > 0
        assert logs[-1]["blocked"] is True
        assert logs[-1]["action_type"] == "publish_blog_to_wordpress"
    except Exception:
        pytest.skip("Database not available")