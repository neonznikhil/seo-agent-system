"""Tools package with PEP 562 lazy exports to ensure instantaneous backend startup."""
from typing import Any
import importlib

_TOOL_MAP = {
    "WebBrowserTool": ".web_browser_tool",
    "RealTimeDataTool": ".real_time_data_tool",
    "CompetitorAnalysisTool": ".competitor_analysis_tool",
    "KnowledgeCrawlerTool": ".knowledge_crawler_tool",
    "AntiAIPenTool": ".anti_ai_pen_tool",
    "SEOAEOGEOTool": ".seo_aeo_geo_tool",
    "SERPAnalyzerTool": ".serp_analyzer_tool",
    "ContentOptimizerTool": ".content_optimizer_tool",
    "ThinkAndLogTool": ".think_and_log_tool",
    "VectorMemoryTool": ".vector_memory_tool",
    "KnowledgeExtractorTool": ".knowledge_extractor_tool",
    "ToneAnalyzerTool": ".tone_analyzer_tool",
    "LlmsTxtTool": ".llms_txt_tool",
    "CrawleeTool": ".crawlee_tool",
    "QualityGateTool": ".quality_gate_tool",
    "ProspectResearchTool": ".prospect_research_tool",
    "DirectoryTool": ".directory_tool",
    "RankTools": ".rank_tools",
}


def __getattr__(name: str) -> Any:
    if name in _TOOL_MAP:
        mod = importlib.import_module(_TOOL_MAP[name], __package__)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = list(_TOOL_MAP.keys())


