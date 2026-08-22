import json
import logging
import os

from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI

from .personas import AUDITOR_PERSONA, EDITOR_PERSONA, WRITER_PERSONA, TECH_SEO_PERSONA, MANAGER_PERSONA, SEO_BACKLINK_PERSONA
from .tools.think_and_log_tool import ThinkAndLogTool
from .tools.vector_memory_tool import VectorMemoryTool
from .tools.knowledge_extractor_tool import KnowledgeExtractorTool
from .tools.tone_analyzer_tool import ToneAnalyzerTool
from .tools.llms_txt_tool import LlmsTxtTool
from .tools.crawlee_tool import CrawleeTool
from .tools.quality_gate_tool import QualityGateTool
from .tools.seo_aeo_geo_tool import SEOAEOGEOTool
from .tools.serp_analyzer_tool import SERPAnalyzerTool
from .tools.content_optimizer_tool import ContentOptimizerTool

logger = logging.getLogger("backend.agents.crew")


class NIM_LLM:
    """LangChain-compatible NVIDIA NIM wrapper for CrewAI agents."""

    def __init__(self, model: str = "meta/llama-3.1-70b-instruct"):
        from ..database import NIM_API_KEY

        self.model = model
        self.llm = ChatOpenAI(
            model=model,
            api_key=NIM_API_KEY or "not-set",
            base_url="https://integrate.api.nvidia.com/v1",
            temperature=0.2,
        )

    def call(self, prompt: str, system: str = "") -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        result = self.llm.invoke(messages)
        return result.content if hasattr(result, "content") else str(result)

    def __call__(self, prompt: str, **kwargs) -> str:
        return self.call(prompt)


def _build_nim_chat(model: str = "meta/llama-3.1-70b-instruct") -> ChatOpenAI:
    from ..database import NIM_API_KEY

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


think_tool = ThinkAndLogTool()
vector_memory_tool = VectorMemoryTool()
quality_gate_tool = QualityGateTool()
knowledge_extractor_tool = KnowledgeExtractorTool()
tone_analyzer_tool = ToneAnalyzerTool()
llms_txt_tool = LlmsTxtTool()
crawlee_tool = CrawleeTool()
seo_aeo_geo_tool = SEOAEOGEOTool()
serp_analyzer_tool = SERPAnalyzerTool()
content_optimizer_tool = ContentOptimizerTool()

nim_llm = _build_nim_chat()


auditor_agent = Agent(
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

editor_agent = Agent(
    role=EDITOR_PERSONA["role"],
    goal=EDITOR_PERSONA["goal"],
    backstory=EDITOR_PERSONA["backstory"] + "\n\nSAFETY RULE: You never publish or update pages without HUMAN APPROVAL. "
                       "You propose fixes with status pending_approval. Publishing is FORBIDDEN for you. "
                       "Only humans can approve via /api/proposals/approve endpoint.",
    tools=[think_tool],
    llm=nim_llm,
    verbose=True,
)

writer_agent = Agent(
    role=WRITER_PERSONA["role"],
    goal=WRITER_PERSONA["goal"],
    backstory=WRITER_PERSONA["backstory"] + "\n\nSAFETY RULE: CRITICAL - You never publish blogs or update pages. "
                       "You create content with status 'pending_approval' via propose_blog tool. "
                       "Publishing is FORBIDDEN - only human can approve via dashboard. "
                       "If you attempt to publish directly, safety gate will BLOCK you and log CRITICAL ERROR. "
                       "Optimize for: E-E-A-T, featured snippets, AI citation, structured data, semantic depth.",
    tools=[think_tool, quality_gate_tool, llms_txt_tool, crawlee_tool, vector_memory_tool, knowledge_extractor_tool, tone_analyzer_tool, seo_aeo_geo_tool, content_optimizer_tool],
    llm=nim_llm,
    verbose=True,
)

tech_seo_agent = Agent(
    role=TECH_SEO_PERSONA["role"],
    goal=TECH_SEO_PERSONA["goal"],
    backstory=TECH_SEO_PERSONA["backstory"] + "\n\nSAFETY RULE: You never publish or update pages. "
                        "You only analyze and propose fixes. Publishing requires HUMAN APPROVAL. "
                        "Focus on: AI readiness, structured data, featured snippet technical requirements, LLM accessibility.",
    tools=[think_tool, crawlee_tool, seo_aeo_geo_tool],
    llm=nim_llm,
    verbose=True,
)

seo_backlink_agent = Agent(
    role=SEO_BACKLINK_PERSONA["role"],
    goal=SEO_BACKLINK_PERSONA["goal"],
    backstory=SEO_BACKLINK_PERSONA["backstory"] + "\n\nSAFETY RULE: You never disavow or delete backlinks directly. "
                        "You only analyze and propose. Disavow requires HUMAN APPROVAL. "
                        "Focus on: AI-citation-worthy backlinks, authoritative sources, GEO visibility.",
    tools=[think_tool, seo_aeo_geo_tool],
    llm=nim_llm,
    verbose=True,
)

manager_agent = Agent(
    role=MANAGER_PERSONA["role"],
    goal=MANAGER_PERSONA["goal"],
    backstory=MANAGER_PERSONA["backstory"] + "\n\nSAFETY RULE: You prioritize by AI visibility impact. "
                        "Human approval required for all publishing. Track metrics: rankings + AI citations.",
    tools=[think_tool],
    llm=nim_llm,
    verbose=True,
)


def plan_blogs_for_website(website_id: str) -> str:
    _set_website_id(
        [think_tool, vector_memory_tool, quality_gate_tool, knowledge_extractor_tool, 
         tone_analyzer_tool, llms_txt_tool, crawlee_tool, seo_aeo_geo_tool, content_optimizer_tool, serp_analyzer_tool], 
        website_id, "auditor"
    )
    _set_website_id([think_tool, seo_aeo_geo_tool], website_id, "editor")
    _set_website_id(
        [think_tool, quality_gate_tool, llms_txt_tool, crawlee_tool, vector_memory_tool, 
         knowledge_extractor_tool, tone_analyzer_tool, seo_aeo_geo_tool, content_optimizer_tool], 
        website_id, "writer"
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
        tools=[crawlee_tool, quality_gate_tool, llms_txt_tool, think_tool, vector_memory_tool, knowledge_extractor_tool, tone_analyzer_tool, seo_aeo_geo_tool, content_optimizer_tool],
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
        from ..database import get_supabase
        get_supabase().table("agent_thoughts").insert({
            "website_id": website_id,
            "thought": f"CrewAI kickoff completed (SEO/AEO/GEO): {str(result)[:1000]}",
            "created_at": __import__("datetime").datetime.utcnow().isoformat(),
        }).execute()
    except Exception as e:
        logger.error("Failed to log crew thought: %s", e)

    audit_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "CREWAI_AUDIT.md")
    with open(audit_path, "w", encoding="utf-8") as f:
        f.write(f"# CrewAI Audit Log (SEO/AEO/GEO Enhanced)\n\nTimestamp: {__import__('datetime').datetime.utcnow().isoformat()}\nWebsite: {website_id}\n\n## Result\n\n{result}\n")

    return str(result)