#!/usr/bin/env python
import sys
sys.path.insert(0, r"C:\Users\nikhil\Desktop\seo-agent-system")

try:
    from backend.agents.tools import (
        WebBrowserTool, RealTimeDataTool, CompetitorAnalysisTool,
        KnowledgeCrawlerTool, AntiAIPenTool, SEOAEOGEOTool, SERPAnalyzerTool,
        ContentOptimizerTool
    )
    print("All tools imported successfully!")
    
    from backend.agents.setup_agent import SetupAgent, create_setup_agent
    print("SetupAgent imported successfully!")
    
    print("All imports passed!")
except Exception as e:
    print(f"Import error: {e}")
    import traceback
    traceback.print_exc()