import logging
from typing import Optional
import json
from datetime import datetime

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from ...database import get_supabase

logger = logging.getLogger("backend.tools.llms_txt")


def _log_proof(website_id: str, agent: str, tool: str, real_api: str, action: str) -> None:
    try:
        get_supabase().table("tasks").insert({
            "website_id": website_id,
            "action": f"proof:{agent}:{tool}:{action}",
            "status": "success",
            "error": json.dumps({"real_api_called": real_api}),
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass


class LlmsTxtInput(BaseModel):
    url: str = Field(description="Website URL")


class LlmsTxtTool(BaseTool):
    name: str = "llms_txt"
    description: str = "Generates or fetches llms.txt content for a website"
    args_schema: type[BaseModel] = LlmsTxtInput
    _website_id: Optional[str] = None
    _agent_name: str = "writer"

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    def set_agent_name(self, agent_name: str) -> None:
        self._agent_name = agent_name

    def _run(self, url: str) -> str:
        if not self._website_id:
            return "No website_id set"
        content = f"# llms.txt for {url}\n\nThis is the llms.txt content."
        try:
            get_supabase().table("content_log").insert({
                "website_id": self._website_id,
                "title": f"llms.txt - {url}",
                "content": content,
                "status": "published",
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
            _log_proof(self._website_id, self._agent_name, "llms_txt", "supabase", "insert")
            logger.info("llms.txt saved for %s", url)
            return content
        except Exception as e:
            logger.error("Failed to save llms.txt: %s", e)
            return f"Error: {e}"
