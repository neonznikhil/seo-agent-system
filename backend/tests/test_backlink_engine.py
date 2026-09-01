import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from services.backlink_authority_engine import BacklinkAuthorityEngine
from agents.opportunity_scout_agent import OpportunityScoutAgent
from agents.asset_engineer_agent import AssetEngineerAgent
from agents.acquisition_monitor_agent import AcquisitionMonitorAgent
from agents.authority_calibration_agent import AuthorityCalibrationAgent


@pytest.mark.asyncio
async def test_opportunity_scout_agent_dr_filter():
    scout = OpportunityScoutAgent(website_id="default")
    
    mock_serp = {
        "organic": [
            {"link": "https://www.texasbar.com/resources", "title": "Legal Resources", "snippet": "State resources"},
            {"link": "https://lowdr-spam.biz/links", "title": "Spam", "snippet": "Spam directory"}
        ]
    }
    
    with patch("backend.services.serper_service.serper_service.search", new=AsyncMock(return_value=mock_serp)):
        with patch("backend.agents.opportunity_scout_agent.get_supabase") as mock_sup:
            mock_sup.return_value.table.return_value.insert.return_value.execute.return_value = MagicMock()
            mock_sup.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data={"domain": "accident.innovatcs.com"})
            
            res = await scout.run("Texas accident lawyer")
            assert res.get("success") is True
            assert "total_discovered" in res


@pytest.mark.asyncio
async def test_authority_calibration_agent():
    calibrator = AuthorityCalibrationAgent(website_id="default")
    mock_llm_json = '{"opportunity_priority": ["statistics_citation"], "minimum_dr_threshold": 30, "priority_asset_type": "statistics_page", "strategic_rationale": "High conversion"}'
    
    with patch("backend.agents.authority_calibration_agent.call_nim_llm", new=AsyncMock(return_value=mock_llm_json)):
        with patch("backend.agents.authority_calibration_agent.get_supabase") as mock_sup:
            mock_sup.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            mock_sup.return_value.table.return_value.upsert.return_value.execute.return_value = MagicMock()
            
            res = await calibrator.run()
            assert res.get("success") is True
            assert "calibration" in res
            assert res["calibration"]["minimum_dr_threshold"] == 30
