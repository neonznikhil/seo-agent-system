import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure both backend directory and repo root are always in sys.path
_backend_dir = Path(__file__).resolve().parent.parent
_repo_root = _backend_dir.parent
for _p in [str(_backend_dir), str(_repo_root)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from agents.personas import (
        AUDITOR_PERSONA,
        EDITOR_PERSONA,
        WRITER_PERSONA,
        TECH_SEO_PERSONA,
        MANAGER_PERSONA,
        SEO_BACKLINK_PERSONA,
    )
except ImportError:
    from .personas import (
        AUDITOR_PERSONA,
        EDITOR_PERSONA,
        WRITER_PERSONA,
        TECH_SEO_PERSONA,
        MANAGER_PERSONA,
        SEO_BACKLINK_PERSONA,
    )

logger = logging.getLogger("backend.agents.crew")

# Lazy attribute cache
_ATTR_CACHE: Dict[str, Any] = {}


def _get_chat_openai():
    if "_ChatOpenAI" not in _ATTR_CACHE:
        try:
            from langchain_openai import ChatOpenAI
            _ATTR_CACHE["_ChatOpenAI"] = ChatOpenAI
        except ImportError:
            try:
                from langchain_community.chat_models import ChatOpenAI
                _ATTR_CACHE["_ChatOpenAI"] = ChatOpenAI
            except ImportError:
                try:
                    from langchain.chat_models import ChatOpenAI
                    _ATTR_CACHE["_ChatOpenAI"] = ChatOpenAI
                except ImportError:
                    _ATTR_CACHE["_ChatOpenAI"] = None
    return _ATTR_CACHE["_ChatOpenAI"]


class NIM_LLM:
    """LangChain-compatible NVIDIA NIM wrapper for CrewAI agents."""

    def __init__(self, model: str = "meta/llama-3.1-70b-instruct"):
        from database import NIM_API_KEY

        ChatOpenAI = _get_chat_openai()
        self.model = model
        self.llm = (
            ChatOpenAI(
                model=model,
                api_key=NIM_API_KEY or "not-set",
                base_url="https://integrate.api.nvidia.com/v1",
                temperature=0.2,
            )
            if ChatOpenAI is not None
            else None
        )

    def call(self, prompt: str, system: str = "") -> str:
        if not self.llm:
            return ""
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        result = self.llm.invoke(messages)
        return result.content if hasattr(result, "content") else str(result)

    def __call__(self, prompt: str, **kwargs) -> str:
        return self.call(prompt)


def _build_nim_chat(model: str = "meta/llama-3.1-70b-instruct"):
    from database import NIM_API_KEY

    ChatOpenAI = _get_chat_openai()
    if ChatOpenAI is None:
        return None
    return ChatOpenAI(
        model=model,
        api_key=NIM_API_KEY or "not-set",
        base_url="https://integrate.api.nvidia.com/v1",
        temperature=0.2,
    )


def _set_website_id(tools: list, website_id: str, agent_name: str = "unknown"):
    for t in tools:
        if hasattr(t, "set_website_id"):
            t.set_website_id(website_id)
        if hasattr(t, "set_agent_name"):
            t.set_agent_name(agent_name)


# ---------------------------------------------------------------------------
# Lazy Tool & Agent Factories
# ---------------------------------------------------------------------------

def _get_crewai_classes():
    if "_crewai_classes" not in _ATTR_CACHE:
        from crewai import Agent, Task, Crew, Process
        from crewai.tools import BaseTool
        _ATTR_CACHE["_crewai_classes"] = (Agent, Task, Crew, Process, BaseTool)
    return _ATTR_CACHE["_crewai_classes"]


def _get_tool(name: str):
    if name in _ATTR_CACHE:
        return _ATTR_CACHE[name]

    if name == "think_tool":
        try:
            from agents.tools.think_and_log_tool import ThinkAndLogTool
        except ImportError:
            from .tools.think_and_log_tool import ThinkAndLogTool
        tool = ThinkAndLogTool()
    elif name == "vector_memory_tool":
        try:
            from agents.tools.vector_memory_tool import VectorMemoryTool
        except ImportError:
            from .tools.vector_memory_tool import VectorMemoryTool
        tool = VectorMemoryTool()
    elif name == "quality_gate_tool":
        try:
            from agents.tools.quality_gate_tool import QualityGateTool
        except ImportError:
            from .tools.quality_gate_tool import QualityGateTool
        tool = QualityGateTool()
    elif name == "knowledge_extractor_tool":
        try:
            from agents.tools.knowledge_extractor_tool import KnowledgeExtractorTool
        except ImportError:
            from .tools.knowledge_extractor_tool import KnowledgeExtractorTool
        tool = KnowledgeExtractorTool()
    elif name == "tone_analyzer_tool":
        try:
            from agents.tools.tone_analyzer_tool import ToneAnalyzerTool
        except ImportError:
            from .tools.tone_analyzer_tool import ToneAnalyzerTool
        tool = ToneAnalyzerTool()
    elif name == "llms_txt_tool":
        try:
            from agents.tools.llms_txt_tool import LlmsTxtTool
        except ImportError:
            from .tools.llms_txt_tool import LlmsTxtTool
        tool = LlmsTxtTool()
    elif name == "crawlee_tool":
        try:
            from agents.tools.crawlee_tool import CrawleeTool
        except ImportError:
            from .tools.crawlee_tool import CrawleeTool
        tool = CrawleeTool()
    elif name == "seo_aeo_geo_tool":
        try:
            from agents.tools.seo_aeo_geo_tool import SEOAEOGEOTool
        except ImportError:
            from .tools.seo_aeo_geo_tool import SEOAEOGEOTool
        tool = SEOAEOGEOTool()
    elif name == "serp_analyzer_tool":
        try:
            from agents.tools.serp_analyzer_tool import SERPAnalyzerTool
        except ImportError:
            from .tools.serp_analyzer_tool import SERPAnalyzerTool
        tool = SERPAnalyzerTool()
    elif name == "content_optimizer_tool":
        try:
            from agents.tools.content_optimizer_tool import ContentOptimizerTool
        except ImportError:
            from .tools.content_optimizer_tool import ContentOptimizerTool
        tool = ContentOptimizerTool()
    elif name == "propose_blog_tool":
        _, _, _, _, BaseTool = _get_crewai_classes()

        class ProposeBlogTool(BaseTool):
            name: str = "propose_blog"
            description: str = "Proposes a blog post with status pending_approval. Never publishes live."

            def _run(self, *a, **kw):
                try:
                    from agents.tools.cms_tools import propose_blog
                except ImportError:
                    from .tools.cms_tools import propose_blog
                return propose_blog(*a, **kw)

        tool = ProposeBlogTool()
    else:
        raise AttributeError(f"Unknown tool: {name}")

    _ATTR_CACHE[name] = tool
    globals()[name] = tool
    return tool


def _get_agent(name: str):
    if name in _ATTR_CACHE:
        return _ATTR_CACHE[name]

    Agent, _, _, _, _ = _get_crewai_classes()
    nim_llm = _ATTR_CACHE.get("nim_llm")
    if nim_llm is None:
        nim_llm = _build_nim_chat()
        _ATTR_CACHE["nim_llm"] = nim_llm
        globals()["nim_llm"] = nim_llm

    think_tool = _get_tool("think_tool")
    crawlee_tool = _get_tool("crawlee_tool")
    seo_aeo_geo_tool = _get_tool("seo_aeo_geo_tool")
    serp_analyzer_tool = _get_tool("serp_analyzer_tool")

    if name == "auditor_agent":
        agent = Agent(
            role=AUDITOR_PERSONA["role"],
            goal=AUDITOR_PERSONA["goal"],
            backstory=AUDITOR_PERSONA["backstory"] + "\n\nSAFETY RULE: You are NEVER allowed to call publish or update WordPress directly. "
                                "You only propose issues. Publishing requires human approval via dashboard. "
                                "Your job is RESEARCH AND PROPOSAL ONLY - never execution. "
                                "Focus on: 1) SEO technical issues, 2) AEO/SERP optimization gaps, 3) GEO/LLM visibility barriers.",
            tools=[think_tool, crawlee_tool, seo_aeo_geo_tool, serp_analyzer_tool],
            llm=nim_llm,
            verbose=True,
        )
    elif name == "editor_agent":
        agent = Agent(
            role=EDITOR_PERSONA["role"],
            goal=EDITOR_PERSONA["goal"],
            backstory=EDITOR_PERSONA["backstory"] + "\n\nSAFETY RULE: You never publish or update pages without HUMAN APPROVAL. "
                               "You propose fixes with status pending_approval. Publishing is FORBIDDEN for you. "
                               "Only humans can approve via /api/proposals/approve endpoint.",
            tools=[think_tool],
            llm=nim_llm,
            verbose=True,
        )
    elif name == "writer_agent":
        agent = Agent(
            role=WRITER_PERSONA["role"],
            goal=WRITER_PERSONA["goal"],
            backstory=WRITER_PERSONA["backstory"] + "\n\nSAFETY RULE: CRITICAL - You never publish blogs or update pages. "
                               "You create content with status 'pending_approval' via propose_blog tool. "
                               "Publishing is FORBIDDEN - only human can approve via dashboard. "
                               "If you attempt to publish directly, safety gate will BLOCK you and log CRITICAL ERROR. "
                               "Optimize for: E-E-A-T, featured snippets, AI citation, structured data, semantic depth.",
            tools=[
                think_tool,
                _get_tool("propose_blog_tool"),
                _get_tool("quality_gate_tool"),
                _get_tool("llms_txt_tool"),
                crawlee_tool,
                _get_tool("vector_memory_tool"),
                _get_tool("knowledge_extractor_tool"),
                _get_tool("tone_analyzer_tool"),
                seo_aeo_geo_tool,
                _get_tool("content_optimizer_tool"),
            ],
            llm=nim_llm,
            verbose=True,
        )
    elif name == "tech_seo_agent":
        agent = Agent(
            role=TECH_SEO_PERSONA["role"],
            goal=TECH_SEO_PERSONA["goal"],
            backstory=TECH_SEO_PERSONA["backstory"] + "\n\nSAFETY RULE: You never publish or update pages. "
                                "You only analyze and propose fixes. Publishing requires HUMAN APPROVAL. "
                                "Focus on: AI readiness, structured data, featured snippet technical requirements, LLM accessibility.",
            tools=[think_tool, crawlee_tool, seo_aeo_geo_tool],
            llm=nim_llm,
            verbose=True,
        )
    elif name == "seo_backlink_agent":
        agent = Agent(
            role=SEO_BACKLINK_PERSONA["role"],
            goal=SEO_BACKLINK_PERSONA["goal"],
            backstory=SEO_BACKLINK_PERSONA["backstory"] + "\n\nSAFETY RULE: You never disavow or delete backlinks directly. "
                                "You only analyze and propose. Disavow requires HUMAN APPROVAL. "
                                "Focus on: AI-citation-worthy backlinks, authoritative sources, GEO visibility.",
            tools=[think_tool, seo_aeo_geo_tool],
            llm=nim_llm,
            verbose=True,
        )
    elif name == "manager_agent":
        agent = Agent(
            role=MANAGER_PERSONA["role"],
            goal=MANAGER_PERSONA["goal"],
            backstory=MANAGER_PERSONA["backstory"] + "\n\nSAFETY RULE: You prioritize by AI visibility impact. "
                                "Human approval required for all publishing. Track metrics: rankings + AI citations.",
            tools=[think_tool],
            llm=nim_llm,
            verbose=True,
        )
    else:
        raise AttributeError(f"Unknown agent: {name}")

    _ATTR_CACHE[name] = agent
    globals()[name] = agent
    return agent


def plan_blogs_for_website(website_id: str) -> str:
    Agent, Task, Crew, Process, _ = _get_crewai_classes()

    auditor_agent = _get_agent("auditor_agent")
    editor_agent = _get_agent("editor_agent")
    writer_agent = _get_agent("writer_agent")
    tech_seo_agent = _get_agent("tech_seo_agent")
    seo_backlink_agent = _get_agent("seo_backlink_agent")
    manager_agent = _get_agent("manager_agent")

    think_tool = _get_tool("think_tool")
    vector_memory_tool = _get_tool("vector_memory_tool")
    quality_gate_tool = _get_tool("quality_gate_tool")
    knowledge_extractor_tool = _get_tool("knowledge_extractor_tool")
    tone_analyzer_tool = _get_tool("tone_analyzer_tool")
    llms_txt_tool = _get_tool("llms_txt_tool")
    crawlee_tool = _get_tool("crawlee_tool")
    seo_aeo_geo_tool = _get_tool("seo_aeo_geo_tool")
    serp_analyzer_tool = _get_tool("serp_analyzer_tool")
    content_optimizer_tool = _get_tool("content_optimizer_tool")

    _set_website_id(
        [
            think_tool,
            vector_memory_tool,
            quality_gate_tool,
            knowledge_extractor_tool,
            tone_analyzer_tool,
            llms_txt_tool,
            crawlee_tool,
            seo_aeo_geo_tool,
            content_optimizer_tool,
            serp_analyzer_tool,
        ],
        website_id,
        "auditor",
    )
    _set_website_id([think_tool, seo_aeo_geo_tool], website_id, "editor")
    _set_website_id(
        [
            think_tool,
            quality_gate_tool,
            llms_txt_tool,
            crawlee_tool,
            vector_memory_tool,
            knowledge_extractor_tool,
            tone_analyzer_tool,
            seo_aeo_geo_tool,
            content_optimizer_tool,
        ],
        website_id,
        "writer",
    )
    _set_website_id([think_tool, crawlee_tool, seo_aeo_geo_tool], website_id, "tech_seo")
    _set_website_id([think_tool, seo_aeo_geo_tool], website_id, "seo_backlink")
    _set_website_id([think_tool], website_id, "manager")

    audit_task = Task(
        description=(
            f"Audit website {website_id} for SEO, AEO, and GEO optimization. "
            "Crawl up to 50 pages with Crawlee where last_audited>7 days AND impressions>100. "
            "Use seo_aeo_geo_tool to identify: 1) Traditional SEO issues, 2) Featured snippet opportunities, 3) AI/LLM visibility barriers. "
            "Use serp_analyzer_tool for keyword SERP analysis. "
            "Calculate AI impact score = impressions * (3 - CTR). "
            "Log top 10 issues by AI visibility impact via think_tool. "
            "SAFETY RULE: Never publish directly. Only create proposals with status pending_approval."
        ),
        expected_output="List of up to 10 prioritized SEO/AEO/GEO issues with impact scores",
        agent=auditor_agent,
        tools=[crawlee_tool, think_tool, seo_aeo_geo_tool, serp_analyzer_tool],
    )

    write_task = Task(
        description=(
            f"Generate up to 2 blog posts for website {website_id} based on active keywords from GSC with impressions>500 and CTR<3%. "
            "Target KEYWORDS for featured snippets and AI summarization. "
            "Fetch knowledge_base + tone_profiles. Check duplicates via vector_memory. "
            "Use content_optimizer_tool for SEO/AEO/GEO optimization. "
            "Convert keyword to use-case title. "
            "Write 1500-2000 words optimized for: Google ranking, featured snippets, AI/LLM summarization, E-E-A-T, structured data. "
            "Include: 50-word direct answer, data table, statistics, 5+ FAQ, internal links. "
            "Run quality_gate before marking pending_approval. "
            "SAFETY RULE: Never publish directly. Content must have status='pending_approval'."
        ),
        expected_output="Up to 2 quality-gated blog posts in pending_approval status with SEO/AEO/GEO optimization notes",
        agent=writer_agent,
        tools=[
            crawlee_tool,
            quality_gate_tool,
            llms_txt_tool,
            think_tool,
            vector_memory_tool,
            knowledge_extractor_tool,
            tone_analyzer_tool,
            seo_aeo_geo_tool,
            content_optimizer_tool,
        ],
    )

    tech_task = Task(
        description=(
            f"Run technical SEO and AI-readiness check for website {website_id}. "
            "Check: sitemap.xml, robots.txt, canonical, broken links, 404s, redirect chains, schema (FAQ/HowTo), "
            "Core Web Vitals (LCP<2.5s, FID<100ms, CLS<0.1), LLM accessibility. "
            "Use seo_aeo_geo_tool for AI-ready assessment. "
            "SAFETY RULE: Never update robots.txt or sitemap directly. Only propose changes."
        ),
        expected_output="Technical audit report saved to technical_audits with AI-readiness score",
        agent=tech_seo_agent,
        tools=[crawlee_tool, think_tool, seo_aeo_geo_tool],
    )

    backlink_task = Task(
        description=(
            f"Analyze backlinks for website {website_id} using GSC link data. "
            "Identify AI-citation-worthy domains and toxic links. "
            "Calculate backlink equity for GEO visibility. "
            "SAFETY RULE: Never disavow backlinks directly. Only analyze and log suggestions."
        ),
        expected_output="Backlink analysis saved to backlinks table with AI-citation score",
        agent=seo_backlink_agent,
        tools=[think_tool, seo_aeo_geo_tool],
    )

    manager_task = Task(
        description=(
            f"Prioritize work for website {website_id} based on AI visibility impact score. "
            "Balance: 1) Featured snippet opportunities, 2) AI summarization potential, 3) Traditional SEO value. "
            "Ensure human approval for all publishing actions. "
            "Track metrics: search rankings + AI citation frequency."
        ),
        expected_output="Prioritized task queue with AI impact scores",
        agent=manager_agent,
        tools=[think_tool],
    )

    crew = Crew(
        agents=[auditor_agent, editor_agent, writer_agent, tech_seo_agent, seo_backlink_agent, manager_agent],
        tasks=[audit_task, write_task, tech_task, backlink_task, manager_task],
        process=Process.sequential,
        verbose=2,
    )

    result = crew.kickoff()

    try:
        from database import get_supabase

        get_supabase().table("agent_thoughts").insert({
            "website_id": website_id,
            "thought": f"CrewAI kickoff completed (SEO/AEO/GEO): {str(result)[:1000]}",
            "created_at": __import__("datetime").datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        logger.error("Failed to log crew thought: %s", e)

    audit_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "CREWAI_AUDIT.md")
    with open(audit_path, "w", encoding="utf-8") as f:
        f.write(
            f"# CrewAI Audit Log (SEO/AEO/GEO Enhanced)\n\nTimestamp: {__import__('datetime').datetime.now(timezone.utc).isoformat()}\nWebsite: {website_id}\n\n## Result\n\n{result}\n"
        )

    return str(result)


# ---------------------------------------------------------------------------
# PEP 562 Lazy Module Attribute Access
# ---------------------------------------------------------------------------

_TOOL_ATTRS = {
    "think_tool",
    "vector_memory_tool",
    "quality_gate_tool",
    "knowledge_extractor_tool",
    "tone_analyzer_tool",
    "llms_txt_tool",
    "crawlee_tool",
    "seo_aeo_geo_tool",
    "serp_analyzer_tool",
    "content_optimizer_tool",
    "propose_blog_tool",
}

_AGENT_ATTRS = {
    "auditor_agent",
    "editor_agent",
    "writer_agent",
    "tech_seo_agent",
    "seo_backlink_agent",
    "manager_agent",
}

_TOOL_CLASSES = {
    "ThinkAndLogTool": "agents.tools.think_and_log_tool",
    "VectorMemoryTool": "agents.tools.vector_memory_tool",
    "QualityGateTool": "agents.tools.quality_gate_tool",
    "KnowledgeExtractorTool": "agents.tools.knowledge_extractor_tool",
    "ToneAnalyzerTool": "agents.tools.tone_analyzer_tool",
    "LlmsTxtTool": "agents.tools.llms_txt_tool",
    "CrawleeTool": "agents.tools.crawlee_tool",
    "SEOAEOGEOTool": "agents.tools.seo_aeo_geo_tool",
    "SERPAnalyzerTool": "agents.tools.serp_analyzer_tool",
    "ContentOptimizerTool": "agents.tools.content_optimizer_tool",
}


def __getattr__(name: str) -> Any:
    if name in _TOOL_ATTRS:
        return _get_tool(name)
    if name in _AGENT_ATTRS:
        return _get_agent(name)
    if name == "nim_llm":
        val = _build_nim_chat()
        _ATTR_CACHE["nim_llm"] = val
        globals()["nim_llm"] = val
        return val
    if name in ("Agent", "Task", "Crew", "Process", "BaseTool"):
        classes = _get_crewai_classes()
        mapping = {
            "Agent": classes[0],
            "Task": classes[1],
            "Crew": classes[2],
            "Process": classes[3],
            "BaseTool": classes[4],
        }
        val = mapping[name]
        globals()[name] = val
        return val
    if name in _TOOL_CLASSES:
        mod_name = _TOOL_CLASSES[name]
        try:
            mod = __import__(mod_name, fromlist=[name])
        except ImportError:
            sub = mod_name.split(".")[-1]
            mod = __import__(f"backend.agents.tools.{sub}", fromlist=[name])
        cls = getattr(mod, name)
        globals()[name] = cls
        return cls
    if name == "ProposeBlogTool":
        tool_obj = _get_tool("propose_blog_tool")
        cls = type(tool_obj)
        globals()["ProposeBlogTool"] = cls
        return cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "NIM_LLM",
    "_build_nim_chat",
    "_set_website_id",
    "plan_blogs_for_website",
    "auditor_agent",
    "editor_agent",
    "writer_agent",
    "tech_seo_agent",
    "seo_backlink_agent",
    "manager_agent",
    "think_tool",
    "vector_memory_tool",
    "quality_gate_tool",
    "knowledge_extractor_tool",
    "tone_analyzer_tool",
    "llms_txt_tool",
    "crawlee_tool",
    "seo_aeo_geo_tool",
    "serp_analyzer_tool",
    "content_optimizer_tool",
    "propose_blog_tool",
    "nim_llm",
    "Agent",
    "Task",
    "Crew",
    "Process",
]