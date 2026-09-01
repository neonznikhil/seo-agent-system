import logging
from typing import Optional
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

from database import get_supabase

logger = logging.getLogger("backend.tools.think_and_log")


class ThinkAndLogInput(BaseModel):
    thought: str = Field(description="The thought to log")


def _log_proof(website_id: str, agent: str, tool: str, real_api: str, action: str) -> None:
    try:
        get_supabase().table("tasks").insert({
            "website_id": website_id,
            "action": f"proof:{agent}:{tool}:{action}",
            "status": "success",
            "error": json.dumps({"real_api_called": real_api}),
            "created_at": __import__("datetime").datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass


class ThinkAndLogTool(BaseTool):
    name: str = "think_and_log"
    description: str = "Logs a thought or reasoning step to the agent_thoughts table"
    args_schema: type[BaseModel] = ThinkAndLogInput
    _website_id: Optional[str] = None
    _agent_name: str = "unknown"

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    def set_agent_name(self, agent_name: str) -> None:
        self._agent_name = agent_name

    def _run(self, thought: str) -> str:
        if not self._website_id:
            return "No website_id set"
        try:
            get_supabase().table("agent_thoughts").insert({
                "website_id": self._website_id,
                "thought": thought,
                "created_at": __import__("datetime").datetime.utcnow().isoformat(),
            }).execute()
            _log_proof(self._website_id, self._agent_name, "think_and_log", "supabase", "insert")
            logger.info("Thought logged for website %s", self._website_id)
            return "Logged"
        except Exception as e:
            logger.error("Failed to log thought: %s", e)
            return f"Error: {e}"
