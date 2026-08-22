import logging
from datetime import datetime
from typing import Any, Dict, Optional

from ..database import get_supabase, call_nim_llm
from ..services.brain_service import BrainService
from ..services.reporting_service import report_problem

logger = logging.getLogger("backend.services.outreach_draft")


async def create_outreach_draft(
    website_id: str, prospect_id: str, approved_by_user_id: str
) -> Optional[str]:
    supabase = get_supabase()
    prospect = (
        supabase.table("backlink_prospects")
        .select("*")
        .eq("id", prospect_id)
        .eq("website_id", website_id)
        .single()
        .execute()
        .data
    )
    if not prospect:
        raise ValueError("Prospect not found")

    target_page_url = prospect.get("target_page_url", "")
    target_content = ""
    if target_page_url:
        content_rows = (
            supabase.table("content_log")
            .select("title,body")
            .eq("website_id", website_id)
            .eq("published_url", target_page_url)
            .limit(1)
            .execute()
            .data
            or []
        )
        if content_rows:
            target_content = content_rows[0].get("body", "")[:2000]

    tone = (
        supabase.table("tone_profiles")
        .select("company_name,founder_name")
        .eq("website_id", website_id)
        .single()
        .execute()
        .data
        or {}
    )
    founder_name = tone.get("founder_name") or tone.get("company_name") or "the team"

    brain = BrainService(website_id)
    memories = await brain.recall(website_id, "outreach that got reply", top_k=3)
    memory_text = "; ".join(
        f"{m['title']}: {m['content'][:100]}" for m in memories
    ) if memories else "No successful outreach templates yet."

    competitor_pricing = ""
    if target_page_url:
        try:
            from crawlee.crawlers import BeautifulSoupCrawler

            crawler = BeautifulSoupCrawler(max_requests_per_crawl=1)
            captured: Dict[str, Any] = {}

            @crawler.router.default_handler
            async def handler(context):
                soup = context.soup
                text = soup.get_text(separator=" ", strip=True)
                pricing_lines = [
                    line
                    for line in text.split("\n")
                    if any(word in line.lower() for word in ["$", "price", "pricing", "plan", "month"])
                ]
                captured["pricing"] = "\n".join(pricing_lines[:20])

            await crawler.run([target_page_url])
            competitor_pricing = captured.get("pricing", "")
        except Exception:
            competitor_pricing = ""

    broken_link = prospect.get("broken_link_url", "")
    strategy = prospect.get("strategy", "")
    keyword = prospect.get("target_keyword", "")
    prospect_url = prospect.get("prospect_url", "")
    prospect_title = prospect.get("prospect_url", "")

    subject = ""
    body = ""
    try:
        prompt = (
            "Write outreach email subject and body:\n"
            f"Prospect: {prospect_url}\n"
            f"Prospect title: {prospect_title}\n"
            f"Strategy: {strategy}\n"
            f"Broken link: {broken_link}\n"
            f"Our article: {target_page_url}\n"
            f"Keyword: {keyword}\n"
            f"Founder: {founder_name}\n"
            f"Successful templates: {memory_text}\n"
            f"Competitor pricing: {competitor_pricing}\n\n"
            "Rules:\n"
            "- Subject max 60 chars mention broken link or resource\n"
            "- Body max 120 words personal not template\n"
            "- Mention real broken link 404\n"
            "- Mention real better resource with 2026 pricing table\n"
            "- No spam words like free, guarantee, no pressure\n"
            "- Sign founder name\n"
            "- No fake name"
        )
        response = await call_nim_llm(prompt, website_id=website_id)
        lines = response.split("\n", 1)
        subject = lines[0].strip().strip('"')
        body = lines[1].strip() if len(lines) > 1 else response.strip()
        if len(subject) > 60:
            subject = subject[:57] + "..."
    except Exception as exc:
        logger.error("LLM outreach generation failed: %s", exc)
        subject = f"Quick question about {keyword}"
        body = (
            f"Hi, I noticed a broken link on {prospect_url} and thought our article on {keyword} might be a good replacement. "
            f"Our team at {founder_name}."
        )

    draft = {
        "website_id": website_id,
        "prospect_id": prospect_id,
        "subject": subject,
        "body": body,
        "status": "draft_ready",
        "approved_by": approved_by_user_id,
        "created_at": datetime.utcnow().isoformat(),
    }
    result = supabase.table("outreach_drafts").insert(draft).execute()
    draft_id = result.data[0]["id"] if result.data else None

    supabase.table("backlink_prospects").update({"status": "approved"}).eq("id", prospect_id).execute()

    try:
        supabase.table("critical_action_logs").insert(
            {
                "website_id": website_id,
                "user_id": approved_by_user_id,
                "action": "create_outreach_draft",
                "prospect_id": prospect_id,
                "status": "success",
                "created_at": datetime.utcnow().isoformat(),
            }
        ).execute()
    except Exception:
        pass

    return draft_id


async def mark_outreach_sent(
    website_id: str, draft_id: str, user_id: str
) -> Dict[str, Any]:
    supabase = get_supabase()
    now = datetime.utcnow().isoformat()
    supabase.table("outreach_drafts").update({"status": "sent", "sent_at": now}).eq(
        "id", draft_id
    ).eq("website_id", website_id).execute()

    draft = (
        supabase.table("outreach_drafts")
        .select("prospect_id")
        .eq("id", draft_id)
        .single()
        .execute()
        .data
    )
    if draft:
        supabase.table("backlink_prospects").update({"status": "contacted"}).eq(
            "id", draft["prospect_id"]
        ).execute()

    try:
        supabase.table("critical_action_logs").insert(
            {
                "website_id": website_id,
                "user_id": user_id,
                "action": "mark_outreach_sent",
                "prospect_id": draft.get("prospect_id") if draft else None,
                "status": "success",
                "created_at": now,
            }
        ).execute()
    except Exception:
        pass

    return {"status": "sent"}
