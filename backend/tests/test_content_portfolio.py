import pytest
from unittest.mock import patch, MagicMock
from services.content_portfolio_service import ContentPortfolioService


@pytest.mark.asyncio
async def test_content_portfolio_bcg_analysis():
    svc = ContentPortfolioService(website_id="default")
    
    with patch("backend.services.content_portfolio_service.get_supabase") as mock_sup:
        mock_sup.return_value.table.return_value.insert.return_value.execute.return_value = MagicMock()
        
        res = await svc.analyze_portfolio()
        assert res.get("success") is True
        assert "portfolio_health_score" in res
        assert "breakdown" in res
        assert "stars" in res["breakdown"]
        assert "cash_cows" in res["breakdown"]
        assert len(res["articles"]) >= 5
