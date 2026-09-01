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

from database import get_embedding, get_supabase, call_nim_llm

logger = logging.getLogger("backend.tools.tone_analyzer")


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


class ToneAnalyzerInput(BaseModel):
    content: str = Field(description="Homepage/about/product/blog concatenated content")


class ToneAnalyzerTool(BaseTool):
    name: str = "tone_analyzer"
    description: str = "Analyzes brand tone and saves tone_profile with averaged sample embeddings"
    args_schema: type[BaseModel] = ToneAnalyzerInput
    _website_id: Optional[str] = None
    _agent_name: str = "knowledge_agent"

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    def set_agent_name(self, agent_name: str) -> None:
        self._agent_name = agent_name

    def _run(self, content: str) -> str:
        if not self._website_id:
            return "No website_id set"
        try:
            prompt = (
                "Analyze the brand tone of the following content. "
                "Return JSON with keys: tone_description (e.g., 'Professional friendly direct short sentences'), "
                "writing_style, vocabulary (list of strings), forbidden_words (list of strings). "
                f"Content:\n\n{content[:8000]}"
            )
            system = "You are a tone analyst. Output only valid JSON."
            raw = asyncio.run(call_nim_llm(prompt, system, website_id=self._website_id))
            _log_proof(self._website_id, self._agent_name, "tone_analyzer", "nim", "llm")
            try:
                tone_data = json.loads(raw)
            except Exception:
                tone_data = {
                    "tone_description": raw[:200],
                    "writing_style": "unknown",
                    "vocabulary": [],
                    "forbidden_words": [],
                }

            sentences = [s.strip() for s in content.replace("\n", ". ").split(". ") if s.strip()][:10]
            embeddings = []
            for sentence in sentences:
                try:
                    emb = asyncio.run(get_embedding(sentence, website_id=self._website_id))
                    embeddings.append(emb)
                except Exception:
                    continue

            avg_embedding = None
            if embeddings:
                dim = len(embeddings[0])
                avg_embedding = [sum(emb[i] for emb in embeddings) / len(embeddings) for i in range(dim)]

            profile = {
                "website_id": self._website_id,
                "tone_description": tone_data.get("tone_description", ""),
                "writing_style": tone_data.get("writing_style", ""),
                "vocabulary": tone_data.get("vocabulary", []),
                "forbidden_words": tone_data.get("forbidden_words", []),
                "sample_embeddings": [avg_embedding] if avg_embedding else [],
                "updated_at": __import__("datetime").datetime.utcnow().isoformat(),
            }
            get_supabase().table("tone_profiles").upsert(profile, on_conflict="website_id").execute()
            _log_proof(self._website_id, self._agent_name, "tone_analyzer", "supabase", "upsert")
            logger.info("Saved tone profile for website %s", self._website_id)
            return json.dumps({
                "tone_description": profile["tone_description"],
                "writing_style": profile["writing_style"],
                "vocabulary": profile["vocabulary"],
                "forbidden_words": profile["forbidden_words"],
            })
        except Exception as e:
            logger.error("Tone analysis failed: %s", e)
            return json.dumps({"error": str(e)})
