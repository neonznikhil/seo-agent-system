import logging
from typing import Optional, List, Dict, Any
import json
import re

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from ...database import get_supabase

logger = logging.getLogger("backend.tools.outreach")


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


class OutreachInput(BaseModel):
    prospect_id: str = Field(description="Backlink prospect ID to send outreach to")
    website_id: str = Field(description="Website ID for context")
    custom_message: Optional[str] = Field(None, description="Custom message override")


class OutreachTool(BaseTool):
    name: str = "outreach"
    description: str = "Sends personalized outreach emails to backlink prospects"
    args_schema: type[BaseModel] = OutreachInput
    _website_id: Optional[str] = None
    _agent_name: str = "backlink_agent"

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    def set_agent_name(self, agent_name: str) -> None:
        self._agent_name = agent_name

    def _run(self, prospect_id: str, website_id: str, custom_message: Optional[str] = None) -> str:
        try:
            prospect = get_supabase().table("backlink_prospects").select("*").eq("id", prospect_id).eq("website_id", website_id).single().execute().data
            if not prospect:
                return "# Error: Prospect not found"

            website = get_supabase().table("websites").select("*").eq("id", website_id).single().execute().data
            if not website:
                return "# Error: Website not found"

            domain = website.get("domain", "")
            prospect_name = prospect.get("name", "")
            prospect_url = prospect.get("url", "")
            prospect_type = prospect.get("type", "unknown")
            contact_email = prospect.get("contact_email", "")
            notes = prospect.get("notes", "")

            if not contact_email:
                return "# Error: No contact email available for this prospect. Manual outreach required."

            from ...database import call_nim_llm

            prompt = f"""Write a personalized outreach email for backlink opportunity.

            Our website: {domain}
            Prospect: {prospect_name} ({prospect_url})
            Prospect type: {prospect_type}
            Contact: {contact_email}
            Prospect notes: {notes}

            Write a concise, personalized email (150-200 words) that:
            1. Shows genuine interest in their content
            2. Explains why our content is relevant to their audience
            3. Makes a specific, reasonable request
            4. Has a clear call-to-action
            5. Is professional but not spammy

            Return JSON:
            {{
              "subject": "Email subject line",
              "body": "Email body with proper formatting",
              "personalization_score": 8,
              "tone": "professional"
            }}"""

            result = call_nim_llm(prompt, "You are an expert outreach copywriter. Write personalized, non-spammy emails.")
            _log_proof(website_id, self._agent_name, "outreach", "nim", f"email:{prospect_id}")

            email_data = json.loads(result)
            subject = email_data.get("subject", f"Partnership opportunity with {domain}")
            body = email_data.get("body", "")
            personalization_score = email_data.get("personalization_score", 5)

            outreach_id = __import__("uuid").uuid4().hex
            outreach_record = {
                "id": outreach_id,
                "website_id": website_id,
                "prospect_id": prospect_id,
                "contact_email": contact_email,
                "subject": subject,
                "body": body,
                "status": "draft",
                "personalization_score": personalization_score,
                "sent_at": None,
                "response_received": False,
                "follow_up_count": 0,
                "created_at": __import__("datetime").datetime.utcnow().isoformat(),
            }

            get_supabase().table("outreach_campaigns").insert(outreach_record).execute()

            get_supabase().table("backlink_prospects").update({
                "status": "contacted",
                "last_contacted_at": __import__("datetime").datetime.utcnow().isoformat(),
            }).eq("id", prospect_id).execute()

            return json.dumps({
                "outreach_id": outreach_id,
                "to": contact_email,
                "subject": subject,
                "body_preview": body[:200] + "...",
                "status": "draft",
                "personalization_score": personalization_score,
                "message": "Outreach email created. Use /api/outreach/send to send."
            })

        except Exception as e:
            logger.error("Outreach failed: %s", e)
            _log_proof(website_id, self._agent_name, "outreach", "error", str(e))
            return f"# Error: Outreach failed: {str(e)[:200]}"
