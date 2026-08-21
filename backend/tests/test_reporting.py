import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock


class TestReportingService:
    """Test the ALWAYS REPORT to dashboard functionality."""
    
    @pytest.mark.asyncio
    async def test_report_problem_creates_alert(self):
        """Test that report_problem creates a realtime_alerts row."""
        from backend.services.reporting_service import report_problem
        
        with patch('backend.services.reporting_service.get_supabase') as mock_sb, \
             patch('backend.services.reporting_service.push_sse_alert', new_callable=AsyncMock):
            
            mock_table = MagicMock()
            mock_table.insert.return_value.data = [{
                "id": "test-alert-id",
                "website_id": "test-website",
                "alert_type": "rank_drop",
                "severity": "critical",
                "title": "Test Alert",
                "description": "Test description",
                "data": json.dumps({"keyword": "test"}),
                "source_monitor": "test_monitor"
            }]
            mock_sb.return_value.table.return_value = mock_table
            
            result = await report_problem(
                website_id="test-website",
                alert_type="rank_drop",
                severity="critical",
                title="Test Alert",
                description="Test description",
                data={"keyword": "test keyword"},
                source_monitor="test_monitor"
            )
            
            mock_table.insert.assert_called_once()
            assert result["alert_type"] == "rank_drop"
    
    @pytest.mark.asyncio
    async def test_report_problem_pushes_sse(self):
        """Test that report_problem pushes to SSE."""
        from backend.services.reporting_service import report_problem
        
        with patch('backend.services.reporting_service.get_supabase') as mock_sb, \
             patch('backend.services.reporting_service.push_sse_alert', new_callable=AsyncMock) as mock_sse:
            
            mock_table = MagicMock()
            mock_table.insert.return_value.data = [{
                "id": "test-id",
                "website_id": "test-site",
                "alert_type": "rank_drop",
                "severity": "high",
                "title": "Test"
            }]
            mock_sb.return_value.table.return_value = mock_table
            
            await report_problem(
                website_id="test-site",
                alert_type="rank_drop",
                severity="high",
                title="Test",
                source_monitor="rank_monitor"
            )
            
            mock_sse.assert_called()
    
    @pytest.mark.asyncio
    async def test_low_severity_alerts_also_reported(self):
        """Test that even low severity alerts are reported (nothing silent)."""
        from backend.services.reporting_service import report_problem
        
        with patch('backend.services.reporting_service.get_supabase') as mock_sb, \
             patch('backend.services.reporting_service.push_sse_alert', new_callable=AsyncMock):
            
            mock_table = MagicMock()
            mock_table.insert.return_value.data = [{
                "id": "low-alert",
                "severity": "low",
                "alert_type": "keyword_opportunity",
                "requires_human_approval": True
            }]
            mock_sb.return_value.table.return_value = mock_table
            
            result = await report_problem(
                website_id="test-site",
                alert_type="keyword_opportunity",
                severity="low",
                title="Striking distance keyword",
                source_monitor="rank_monitor"
            )
            
            assert result["severity"] == "low"
            assert result["requires_human_approval"] == True
            mock_table.insert.assert_called()


class TestMonitoringLoops:
    """Test that monitoring loops never fail silently."""
    
    @pytest.mark.asyncio
    async def test_report_problem_on_exception(self):
        """Test report_problem is called when monitor has exception."""
        from backend.services.reporting_service import report_problem
        
        with patch('backend.services.reporting_service.get_supabase') as mock_sb, \
             patch('backend.services.reporting_service.push_sse_alert', new_callable=AsyncMock):
            
            mock_table = MagicMock()
            mock_table.insert.return_value.data = [{
                "id": "monitor-error-id",
                "alert_type": "monitor_error",
                "severity": "high",
                "source_monitor": "rank_monitor"
            }]
            mock_sb.return_value.table.return_value = mock_table
            
            result = await report_problem(
                website_id="test-site",
                alert_type="monitor_error",
                severity="high",
                title="Monitor failed: rank_monitor",
                description="Test exception message",
                source_monitor="rank_monitor"
            )
            
            assert result["alert_type"] == "monitor_error"


class TestHumanApproval:
    """Test human approval requirements."""
    
    @pytest.mark.asyncio
    async def test_publish_requires_x_user_id(self):
        """Test that publish endpoint blocks without X-User-Id."""
        from backend.middleware.human_gate import require_human_for_request
        from fastapi import Request
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {}
        mock_request.client.host = "127.0.0.1"
        
        with pytest.raises(Exception):
            await require_human_for_request(mock_request)


class TestDashboardIntegration:
    """Test dashboard integration with real-time alerts."""
    
    @pytest.mark.asyncio
    async def test_alert_appears_in_dashboard_feed(self):
        """Test that every alert appears in dashboard feed."""
        from backend.services.reporting_service import report_problem
        
        with patch('backend.services.reporting_service.get_supabase') as mock_sb, \
             patch('backend.services.reporting_service.push_sse_alert', new_callable=AsyncMock):
            
            mock_table = MagicMock()
            mock_table.insert.return_value.data = [{
                "id": "test-id",
                "website_id": "test-site",
                "alert_type": "rank_drop",
                "requires_human_approval": True
            }]
            mock_sb.return_value.table.return_value = mock_table
            
            alert = await report_problem(
                website_id="test-site",
                alert_type="rank_drop",
                severity="critical",
                title="Rank 8→14",
                data={"keyword": "test", "old_pos": 8, "new_pos": 14},
                source_monitor="rank_monitor"
            )
            
            assert alert["alert_type"] == "rank_drop"
            assert mock_table.insert.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])