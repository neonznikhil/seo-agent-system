import pytest
from unittest.mock import patch, MagicMock
from services.crisis_response_service import CrisisResponseService


@pytest.mark.asyncio
async def test_crisis_response_evaluation():
    svc = CrisisResponseService(website_id="default")
    
    with patch("backend.services.crisis_response_service.get_supabase") as mock_sup:
        mock_sup.return_value.table.return_value.insert.return_value.execute.return_value = MagicMock()
        
        res = await svc.evaluate_crises()
        assert res.get("success") is True
        assert res.get("all_systems_operational") is True
        assert "mean_time_to_resolution_mttr" in res
        assert "crisis_history" in res
