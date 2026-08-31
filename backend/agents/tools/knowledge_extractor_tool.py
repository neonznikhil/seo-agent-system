import logging
from typing import Optional
import json
import asyncio

try:
    from crewai.tools import BaseTool
except ImportError:
    try:
        from crewai_tools import BaseTool  # type: ignore
    except ImportError:
        class BaseTool:  # fallback stub for py_compile without crewai
            name: str = ""
            description: str = ""
            def _run(self, *a, **kw):
                raise NotImplementedError("crewai not installed")
from pydantic import BaseModel, Field

from ...database import get_embedding, get_supabase, call_nim_llm

logger = logging.getLogger("backend.tools.knowledge_extractor")


def _log_proof(website_id: str, agent: str, tool: str, real_api: str, action: str) -> None:
    try:
        get_supabase().table("tasks").insert({
            "website_id": website_id,
            "agent_name": agent,
            "action": f"proof:{agent}:{tool}:{action}",
            "status": "success",
            "result": {"real_api_called": real_api},
            "real_api_called": real_api,
            "created_at": __import__("datetime").datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass


class KnowledgeExtractorInput(BaseModel):
    pages_content: str = Field(description="Concatenated markdown from crawled pages")


class KnowledgeExtractorTool(BaseTool):
    name: str = "knowledge_extractor"
    description: str = "Extracts 20-30 structured facts from content and saves to knowledge_base with embeddings"
    args_schema: type[BaseModel] = KnowledgeExtractorInput
    _website_id: Optional[str] = None
    _agent_name: str = "knowledge_agent"

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    def set_agent_name(self, agent_name: str) -> None:
        self._agent_name = agent_name

    def _run(self, pages_content: str) -> str:
        if not self._website_id:
            return "No website_id set"
        try:
            prompt = (
                "Extract 20-30 factual statements from the following content. "
                "Return JSON list of objects with keys: fact, fact_type (product_name|pricing|feature|company_info|tone_rule), source_url. "
                f"Content:\n\n{pages_content[:12000]}"
            )
            system = "You are a knowledge extractor. Output only valid JSON."
            raw = asyncio.run(call_nim_llm(prompt, system, website_id=self._website_id))
            _log_proof(self._website_id, self._agent_name, "knowledge_extractor", "nim", "llm")
            try:
                facts = json.loads(raw)
                if not isinstance(facts, list):
                    facts = [{"fact": raw, "fact_type": "company_info", "source_url": ""}]
            except Exception:
                facts = [{"fact": raw, "fact_type": "company_info", "source_url": ""}]

            rows = []
            for item in facts[:30]:
                fact_text = item.get("fact", "").strip()
                if not fact_text:
                    continue
                try:
                    emb = asyncio.run(get_embedding(fact_text, website_id=self._website_id))
                    rows.append({
                        "website_id": self._website_id,
                        "fact": fact_text,
                        "fact_type": item.get("fact_type", "company_info"),
                        "source_url": item.get("source_url", ""),
                        "embedding": emb,
                        "created_at": __import__("datetime").datetime.utcnow().isoformat(),
                    })
                except Exception:
                    continue
            if rows:
                get_supabase().table("knowledge_base").insert(rows).execute()
                _log_proof(self._website_id, self._agent_name, "knowledge_extractor", "supabase", "insert")
                logger.info("Saved %d knowledge facts for website %s", len(rows), self._website_id)
            return json.dumps({"extracted_count": len(rows), "facts": [r["fact"] for r in rows]})
        except Exception as e:
            logger.error("Knowledge extraction failed: %s", e)
            return json.dumps({"error": str(e), "extracted_count": 0})
