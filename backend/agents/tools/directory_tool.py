import logging
from typing import Optional, List, Dict, Any
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

from backend.database import get_supabase

logger = logging.getLogger("backend.tools.directory")


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


class DirectorySubmissionInput(BaseModel):
    directory_name: str = Field(description="Name of the directory")
    directory_url: str = Field(description="URL of the directory")
    website_id: str = Field(description="Website ID for context")


class DirectoryTool(BaseTool):
    name: str = "directory_submission"
    description: str = "Manages web directory submissions for backlinks"
    args_schema: type[BaseModel] = DirectorySubmissionInput
    _website_id: Optional[str] = None
    _agent_name: str = "backlink_agent"

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    def set_agent_name(self, agent_name: str) -> None:
        self._agent_name = agent_name

    def _run(self, directory_name: str, directory_url: str, website_id: str) -> str:
        try:
            existing = get_supabase().table("directory_submissions").select("*").eq("website_id", website_id).eq("directory_url", directory_url).execute().data
            if existing:
                return json.dumps({
                    "status": "already_submitted",
                    "directory": directory_name,
                    "url": directory_url,
                    "message": "Already submitted to this directory"
                })

            submission_id = __import__("uuid").uuid4().hex
            submission = {
                "id": submission_id,
                "website_id": website_id,
                "directory_name": directory_name,
                "directory_url": directory_url,
                "status": "pending",
                "submission_url": None,
                "approved_url": None,
                "da_estimate": 0,
                "notes": "",
                "submitted_at": __import__("datetime").datetime.utcnow().isoformat(),
                "approved_at": None,
            }

            get_supabase().table("directory_submissions").insert(submission).execute()
            _log_proof(website_id, self._agent_name, "directory", "supabase", f"submit:{directory_name}")

            return json.dumps({
                "submission_id": submission_id,
                "directory": directory_name,
                "url": directory_url,
                "status": "pending",
                "message": "Directory submission tracked. Manual submission or automation required."
            })

        except Exception as e:
            logger.error("Directory submission failed: %s", e)
            _log_proof(website_id, self._agent_name, "directory", "error", str(e))
            return f"# Error: Directory submission failed: {str(e)[:200]}"
