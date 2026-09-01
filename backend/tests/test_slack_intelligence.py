import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from services.slack_intelligence_service import SlackIntelligenceService
from services.slack_app_service import SlackAppService


@pytest.mark.asyncio
async def test_slack_reports_generation():
    svc = SlackIntelligenceService()
    
    with patch("backend.services.slack_app_service.slack_app_service.post_block_message", new=AsyncMock(return_value=True)):
        with patch("backend.services.slack_intelligence_service.get_supabase") as mock_sup:
            mock_sup.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            
            # 1. Morning Brief
            m_res = await svc.send_morning_brief("default")
            assert m_res is True

            # 2. Evening Summary
            e_res = await svc.send_evening_summary("default")
            assert e_res is True

            # 3. Backlink Intelligence
            b_res = await svc.send_backlink_intelligence_report("default")
            assert b_res is True

            # 4. Weekly Report
            w_res = await svc.send_weekly_intelligence_report("default")
            assert w_res is True

            # 5. Crisis Alert
            c_res = await svc.send_crisis_alert("default", "Traffic Cliff", "25% drop detected", "Checked GSC")
            assert c_res is True

            # 6. New Learning Alert
            l_res = await svc.send_new_learning_alert("default", "Comparison Guides Rank 40% Faster", "Tuned writer prompt", 0.94, 25)
            assert l_res is True
