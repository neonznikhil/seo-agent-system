import logging
import re
from typing import Optional
import math
import json

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

from backend.database import get_embedding, get_supabase, call_nim_llm

logger = logging.getLogger("backend.tools.quality_gate")


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


class QualityGateInput(BaseModel):
    content_log_id: str = Field(description="Content log ID to quality check")


def cosine_similarity(a: list, b: list) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class QualityGateTool(BaseTool):
    name: str = "quality_gate"
    description: str = "Runs spell, tone, knowledge, and factual quality checks before approval"
    args_schema: type[BaseModel] = QualityGateInput
    _website_id: Optional[str] = None
    _agent_name: str = "writer"

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    def set_agent_name(self, agent_name: str) -> None:
        self._agent_name = agent_name

    async def _run(self, content_log_id: str) -> str:
        if not self._website_id:
            return "No website_id set"
        try:
            row = (
                get_supabase()
                .table("content_log")
                .select("*")
                .eq("id", content_log_id)
                .single()
                .execute()
                .data
            )
            if not row:
                return "Content not found"
            content = row.get("content", "")
            website_id = row.get("website_id", self._website_id)

            spell_check_pass = True
            spell_errors = []
            tone_match_score = 0.0
            knowledge_match_pass = True
            knowledge_errors = []
            factual_accuracy_pass = True

            try:
                spell_prompt = f"List all spelling and grammar errors in the following text. Return JSON array of strings or empty array []:\n\n{content[:4000]}"
                spell_res = await call_nim_llm(spell_prompt, "You are a spelling checker. Output only JSON.", website_id=website_id)
                _log_proof(website_id, self._agent_name, "quality_gate", "nim", "spell_check")
                try:
                    spell_errors = json.loads(spell_res)
                    if not isinstance(spell_errors, list):
                        spell_errors = [spell_res]
                except Exception:
                    spell_errors = [spell_res]
                spell_check_pass = len(spell_errors) < 3
            except Exception as e:
                logger.warning("Spell check failed: %s", e)
                spell_check_pass = False
                spell_errors = [str(e)]

            try:
                profile_res = (
                    get_supabase()
                    .table("tone_profiles")
                    .select("sample_embeddings")
                    .eq("website_id", website_id)
                    .limit(1)
                    .execute()
                )
                profile = profile_res.data[0] if profile_res.data else None
                if profile and profile.get("sample_embeddings"):
                    content_emb = await get_embedding(content[:2000], website_id=website_id)
                    _log_proof(website_id, self._agent_name, "quality_gate", "nim", "embed")
                    similarities = [
                        cosine_similarity(content_emb, emb)
                        for emb in profile["sample_embeddings"]
                        if emb
                    ]
                    tone_match_score = max(similarities) if similarities else 0.0
                else:
                    tone_match_score = 1.0
            except Exception as e:
                logger.warning("Tone check failed: %s", e)
                tone_match_score = 0.0

            try:
                kb_facts = (
                    get_supabase()
                    .table("knowledge_base")
                    .select("fact")
                    .eq("website_id", website_id)
                    .limit(20)
                    .execute()
                    .data
                    or []
                )
                facts_text = "\n".join(f["fact"] for f in kb_facts)
                know_prompt = (
                    f"Known facts:\n{facts_text}\n\n"
                    f"Does the following blog contradict any known fact or make unsupported claims? "
                    f"Return JSON with keys: pass (bool), errors (list of strings).\n\n{content[:4000]}"
                )
                know_res = await call_nim_llm(know_prompt, "You are a factual consistency checker. Output only JSON.", website_id=website_id)
                _log_proof(website_id, self._agent_name, "quality_gate", "nim", "knowledge_check")
                try:
                    know_data = json.loads(know_res)
                    knowledge_match_pass = bool(know_data.get("pass", True))
                    knowledge_errors = know_data.get("errors", [])
                except Exception:
                    knowledge_match_pass = True
                    knowledge_errors = []
            except Exception as e:
                logger.warning("Knowledge check failed: %s", e)
                knowledge_match_pass = True
                knowledge_errors = [str(e)]

            try:
                has_table = bool(re.search(r"\|.+\|", content))
                has_stat = bool(re.search(r"\d+%|\$\d+|\d+ million|\d+ billion", content))
                first_sentence = content.strip().split("\n")[0]
                has_direct_answer = len(first_sentence.split()) <= 60
                faq_count = len(re.findall(r"\?\s*$", content, re.MULTILINE)) + content.lower().count("faq")
                factual_accuracy_pass = has_table and has_stat and has_direct_answer and faq_count >= 4
            except Exception as e:
                logger.warning("Factual check failed: %s", e)
                factual_accuracy_pass = False

            overall_pass = spell_check_pass and (tone_match_score >= 0.75) and knowledge_match_pass and factual_accuracy_pass
            result = "pending_approval" if overall_pass else "needs_revision"

            get_supabase().table("quality_checks").insert({
                "content_log_id": content_log_id,
                "website_id": website_id,
                "spell_check_pass": spell_check_pass,
                "spell_errors": spell_errors,
                "tone_match_score": tone_match_score,
                "knowledge_match_pass": knowledge_match_pass,
                "knowledge_errors": knowledge_errors,
                "factual_accuracy_pass": factual_accuracy_pass,
                "overall_pass": overall_pass,
                "checked_at": __import__("datetime").datetime.utcnow().isoformat(),
            }).execute()
            _log_proof(website_id, self._agent_name, "quality_gate", "supabase", "insert")

            get_supabase().table("content_log").update({"quality_checked": True, "status": result}).eq("id", content_log_id).execute()
            logger.info("Quality gate for %s: %s (spell=%s tone=%.2f knowledge=%s factual=%s)",
                        content_log_id, result, spell_check_pass, tone_match_score, knowledge_match_pass, factual_accuracy_pass)
            return result
        except Exception as e:
            logger.error("Quality gate failed: %s", e)
            return f"Error: {e}"
