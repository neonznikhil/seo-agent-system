#!/usr/bin/env python
"""Verify that critical backend imports work correctly."""
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

try:
    from backend.agents.tools import (
        WebBrowserTool, RealTimeDataTool, CompetitorAnalysisTool,
        KnowledgeCrawlerTool, AntiAIPenTool, SEOAEOGEOTool, SERPAnalyzerTool,
        ContentOptimizerTool,
    )
    print("All tools imported successfully!")

    from backend.agents.crew import auditor_agent, writer_agent, editor_agent, Agent, Crew
    print("CrewAI agents and Crew imported successfully!")

    from backend.agents.setup_agent import SetupAgent, create_setup_agent
    print("SetupAgent imported successfully!")

    print("All imports passed!")
except Exception as e:
    print(f"Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
