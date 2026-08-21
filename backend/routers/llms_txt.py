import logging
from datetime import datetime, timedelta
from fastapi import APIRouter

from ..database import get_supabase

logger = logging.getLogger("backend.routers.llms_txt")
router = APIRouter()


def should_update_llms_txt(website_id: str) -> tuple[bool, str]:
    from ..agents.rules import RULES
    from ..agents.agent_limits import AGENT_LIMITS
    limits = AGENT_LIMITS.get("llms_txt", {})
    min_days = limits.get("min_days", 30)
    try:
        log_res = (
            get_supabase()
            .table("llms_txt_log")
            .select("last_updated, next_due")
            .eq("website_id", website_id)
            .order("last_updated", desc=True)
            .limit(1)
            .execute()
        )
        if not log_res.data:
            return True, "Never generated"
        entry = log_res.data[0]
        last_updated = datetime.fromisoformat(entry["last_updated"].replace("Z", "+00:00"))
        next_due = datetime.fromisoformat(entry["next_due"].replace("Z", "+00:00"))
        now = datetime.utcnow().replace(tzinfo=last_updated.tzinfo)
        if now >= next_due:
            return True, f"Due since {last_updated.date()}"
        return False, f"Not due - {int((next_due - now).days)} days passed need {min_days} days or 10 blogs"
    except Exception as e:
        return True, f"Error checking: {e}"


@router.get("/llms-txt/{website_id}")
async def get_llms_txt(website_id: str):
    res = get_supabase().table("llms_txt_log").select("*").eq("website_id", website_id).order("last_updated", desc=True).limit(1).execute()
    return res.data[0] if res.data else {"detail": "Not found"}


@router.post("/llms-txt/generate")
async def generate_llms_txt(website_id: str):
    can_update, reason = should_update_llms_txt(website_id)
    if not can_update:
        return {"detail": reason}
    from ..agents.tools.llms_txt_tool import LlmsTxtTool
    from ..agents.tools.cms_tools import propose_blog
    tool = LlmsTxtTool()
    tool.set_website_id(website_id)
    tool.set_agent_name("llms_txt_agent")
    website = get_supabase().table("websites").select("domain,cms_url").eq("id", website_id).single().execute().data or {}
    domain = website.get("domain", "")
    cms_url = website.get("cms_url", "")
    base_url = (cms_url or f"https://{domain}").rstrip("/")
    target_url = f"{base_url}/llms.txt"
    content = tool._run(target_url)
    get_supabase().table("llms_txt_log").insert({
        "website_id": website_id,
        "content": content,
        "last_updated": datetime.utcnow().isoformat(),
        "next_due": (datetime.utcnow() + timedelta(days=30)).isoformat(),
    }).execute()
    get_supabase().table("tasks").insert({
        "website_id": website_id,
        "agent_name": "llms_txt_agent",
        "action": "generate_llms_txt",
        "status": "success",
        "real_api_called": "supabase",
    }).execute()
    return {"status": "generated", "content": content}
