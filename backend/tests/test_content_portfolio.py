import pytest
from unittest.mock import patch, MagicMock
from services.content_portfolio_service import ContentPortfolioService


@pytest.mark.asyncio
async def test_content_portfolio_bcg_analysis():
    svc = ContentPortfolioService(website_id="default")
    
    with patch("services.content_portfolio_service.get_supabase") as mock_sup:
        mock_blogs = [
            {"id": f"blog_{i}", "title": f"Article {i}", "status": "published" if i % 2 == 0 else "draft", "slug": f"/post-{i}", "primary_keyword": f"kw {i}", "html_content": "<p>Content</p>"}
            for i in range(6)
        ]
        mock_sup.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=mock_blogs)
        mock_sup.return_value.table.return_value.insert.return_value.execute.return_value = MagicMock()
        
        res = await svc.analyze_portfolio()
        assert res.get("success") is True
        assert "portfolio_health_score" in res
        assert "breakdown" in res
        assert "stars" in res["breakdown"]
        assert "cash_cows" in res["breakdown"]
        assert len(res["articles"]) >= 5
