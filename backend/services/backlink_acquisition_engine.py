import asyncio
import logging
from typing import Dict, Any, Optional

from agents.opportunity_scout_agent import OpportunityScoutAgent
from agents.asset_engineer_agent import AssetEngineerAgent
from agents.acquisition_monitor_agent import AcquisitionMonitorAgent
from agents.authority_calibration_agent import AuthorityCalibrationAgent
try:
    from services.backlink_authority_engine import BacklinkAuthorityEngine
except ImportError:
    from .backlink_authority_engine import BacklinkAuthorityEngine


logger = logging.getLogger("backend.services.backlink_acquisition_engine")


class BacklinkAcquisitionEngine:
    """Master coordinator orchestrating the 4 weekly backlink acquisition agents."""

    def __init__(self, website_id: Optional[str] = None):
        self.website_id = website_id or "default"
        self.authority_engine = BacklinkAuthorityEngine(website_id=self.website_id)
        self.scout_agent = OpportunityScoutAgent(website_id=self.website_id)
        self.asset_agent = AssetEngineerAgent(website_id=self.website_id)
        self.monitor_agent = AcquisitionMonitorAgent(website_id=self.website_id)
        self.calibration_agent = AuthorityCalibrationAgent(website_id=self.website_id)

    async def run_full_weekly_cycle(self, niche_keyword: str = "Texas personal injury legal resources") -> Dict[str, Any]:
        """Execute all 4 agent stages sequentially (for manual trigger or testing)."""
        logger.info(f"[BacklinkAcquisitionEngine] Running full 4-agent backlink cycle for '{niche_keyword}'...")
        
        # Stage 1: Scout Opportunities (Mondays 07:00)
        scout_res = await self.scout_agent.run(niche_keyword)
        
        # Stage 2: Brief Linkable Assets (Mondays 10:00)
        asset_res = await self.asset_agent.run()
        
        # Stage 3: Monitor Acquisitions (Thursdays 09:00)
        monitor_res = await self.monitor_agent.run()
        
        # Stage 4: Calibrate Authority Strategy (Sundays 21:00)
        calibration_res = await self.calibration_agent.run()

        return {
            "success": True,
            "scout_stage": scout_res,
            "asset_stage": asset_res,
            "monitor_stage": monitor_res,
            "calibration_stage": calibration_res
        }


# Singleton helper
async def run_backlink_cycle(website_id: str, keyword: str = "Texas injury claim resources"):
    engine = BacklinkAcquisitionEngine(website_id=website_id)
    return await engine.run_full_weekly_cycle(keyword)
