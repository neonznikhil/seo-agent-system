import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from services.knowledge_evolution_service import KnowledgeEvolutionService


@pytest.mark.asyncio
async def test_knowledge_evolution_jobs():
    svc = KnowledgeEvolutionService(website_id="default")
    
    mock_serp = {
        "organic": [{"link": "https://texasbar.com/update", "title": "2026 Legal Update", "snippet": "New statute rules"}]
    }
    
    with patch("backend.services.serper_service.serper_service.search", new=AsyncMock(return_value=mock_serp)):
        with patch("backend.services.serper_service.serper_service.scholar", new=AsyncMock(return_value=mock_serp)):
            with patch("backend.services.knowledge_evolution_service.get_supabase") as mock_sup:
                mock_sup.return_value.table.return_value.insert.return_value.execute.return_value = MagicMock()
                
                res = await svc.run_daily_evolution_jobs()
                assert res.get("success") is True
                assert "knowledge_health_score" in res
                assert res["knowledge_health_score"] >= 80
