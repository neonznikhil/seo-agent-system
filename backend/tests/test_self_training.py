import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from services.self_training_service import SelfTrainingService


@pytest.mark.asyncio
async def test_self_training_cycle():
    svc = SelfTrainingService(website_id="default")
    
    with patch("backend.services.self_training_service.slack_intelligence_service.send_new_learning_alert", new=AsyncMock(return_value=True)):
        with patch("backend.services.self_training_service.get_supabase") as mock_sup:
            mock_sup.return_value.table.return_value.insert.return_value.execute.return_value = MagicMock()
            mock_sup.return_value.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()
            mock_sup.return_value.table.return_value.upsert.return_value.execute.return_value = MagicMock()
            
            res = await svc.run_self_training_cycle()
            assert res.get("success") is True
            assert "active_prompt_versions" in res
            assert "calibrated_parameters" in res
            assert len(res["active_prompt_versions"]) >= 2
