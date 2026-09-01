import logging
from typing import Optional
import json

import httpx

from backend.database import get_supabase
from backend.config import WORDPRESS_URL

logger = logging.getLogger("backend.tools.cms")


from rules import CriticalActionBlockedError


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


def _log_critical_action_attempt(website_id: str, agent: str, action_type: str, status: str, reason: str) -> None:
    try:
        get_supabase().table("tasks").insert({
            "website_id": website_id,
            "agent_name": agent,
            "action": "BLOCKED_CRITICAL",
            "status": "blocked",
            "payload": {"action_type": action_type, "reason": reason, "status": status},
            "real_api_called": "supabase_log_only",
            "created_at": __import__("datetime").datetime.utcnow().isoformat(),
        }).execute()
        get_supabase().table("critical_action_logs").insert({
            "website_id": website_id,
            "agent_name": agent,
            "action_type": action_type,
            "attempted_at": __import__("datetime").datetime.utcnow().isoformat(),
            "blocked": True,
            "block_reason": reason,
            "status_before": status,
            "approved_by": None,
            "created_at": __import__("datetime").datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass


def propose_fix(website_id: str, audit_id: str, issue: str, suggestion: str, agent: str = "editor") -> dict:
    row = {
        "website_id": website_id,
        "audit_id": audit_id,
        "type": "fix",
        "issue": issue,
        "suggestion": suggestion,
        "status": "pending_approval",
        "agent": agent,
    }
    res = get_supabase().table("content_log").insert(row).execute()
    _log_proof(website_id, agent, "propose_fix", "supabase", "insert")
    logger.info("Proposed fix inserted: %s", res.data)
    return res.data[0] if res.data else row


def propose_blog(website_id: str, title: str, content: str, faq_schema=None, internal_links=None, 
                 similarity_score: Optional[float] = None, embedding: Optional[list] = None, 
                 status: str = "pending", agent: str = "writer", url: Optional[str] = None) -> dict:
    row = {
        "website_id": website_id,
        "title": title,
        "content": content,
        "faq_schema": faq_schema or {},
        "internal_links": internal_links or [],
        "similarity_score": similarity_score,
        "embedding": embedding,
        "quality_checked": False,
        "status": status,
        "agent": agent,
        "url": url or "",
    }
    res = get_supabase().table("content_log").insert(row).execute()
    _log_proof(website_id, agent, "propose_blog", "supabase", "insert")
    logger.info("Proposed blog inserted: %s", res.data)
    return res.data[0] if res.data else row


def publish_blog_after_approval(content_log_id: str, wp_user: str, wp_app_password: str, 
                                website_id: str, agent: str = "writer") -> dict:
    supabase = get_supabase()
    record = supabase.table("content_log").select("*").eq("id", content_log_id).single().execute().data
    
    if not record:
        raise CriticalActionBlockedError(f"Content log {content_log_id} not found")
    
    status = record.get("status", "unknown")
    if status != "approved":
        _log_critical_action_attempt(
            website_id, agent, "publish_blog_to_wordpress", status,
            f"Publish blocked - status {status} not approved, must be 'approved'. Human approval required."
        )
        raise CriticalActionBlockedError(
            f"BLOCKED: Cannot publish blog {content_log_id} - status is {status}, must be 'approved'. "
            f"Human approval required. This is safety gate."
        )
    
    from .shared_utils import is_homepage
    page_url = record.get("url", "")
    if page_url and is_homepage(page_url):
        now = __import__("datetime").datetime.utcnow()
        cooldown_threshold = now - __import__("datetime").timedelta(days=14)
        last_fix = (
            supabase.table("audits")
            .select("*")
            .eq("website_id", website_id)
            .eq("issue_type", "homepage_update")
            .gte("created_at", cooldown_threshold.isoformat())
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        if last_fix:
            raise CriticalActionBlockedError(
                f"BLOCKED: Homepage protected - last fix {last_fix[0].get('created_at', 'unknown')}, "
                f"14-day cooldown active. Cannot update homepage without manual override."
            )
    
    if not WORDPRESS_URL:
        return {
            "status": "approved",
            "wordpress_status": "skipped_no_wordpress_url",
            "message": "Content approved and stored in Supabase. WordPress publish skipped because WORDPRESS_URL is not configured.",
            "content_log_id": content_log_id,
        }
    
    post = {
        "title": record["title"],
        "content": record["content"],
        "status": "publish",
    }
    
    try:
        r = httpx.post(
            f"{WORDPRESS_URL}/wp/v2/posts",
            auth=(wp_user, wp_app_password),
            json=post,
            timeout=30.0,
        )
        r.raise_for_status()
        _log_proof(website_id, agent, "publish_blog_after_approval", "wordpress", "post")
        logger.info("Published WP post %s for content_log %s", r.json().get("id"), content_log_id)
        return r.json()
    except CriticalActionBlockedError:
        raise
    except Exception as e:
        if "403" in str(e) or "permission" in str(e).lower():
            _log_critical_action_attempt(
                website_id, agent, "publish_blog_to_wordpress", status,
                f"WordPress permission error: {str(e)}"
            )
        raise


def update_page_after_approval(audit_id: str, wp_user: str, wp_app_password: str,
                                website_id: str, agent: str = "editor") -> dict:
    supabase = get_supabase()
    record = supabase.table("audits").select("*").eq("id", audit_id).single().execute().data
    
    if not record:
        raise CriticalActionBlockedError(f"Audit {audit_id} not found")
    
    status = record.get("status", "unknown")
    if status != "approved":
        _log_critical_action_attempt(
            website_id, agent, "update_page_on_wordpress", status,
            f"Update blocked - status {status} not approved"
        )
        raise CriticalActionBlockedError(
            f"BLOCKED: Cannot update page {record.get('page_url', 'unknown')} - "
            f"audit status {status} not approved"
        )
    
    page_url = record.get("page_url", "")
    if page_url == "/" or "/index" in page_url or page_url.rstrip("/") == "":
        now = __import__("datetime").datetime.utcnow()
        cooldown_threshold = now - __import__("datetime").timedelta(days=14)
        last_fix = (
            supabase.table("audits")
            .select("*")
            .eq("website_id", website_id)
            .eq("issue_type", "homepage_update")
            .gte("created_at", cooldown_threshold.isoformat())
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        if last_fix:
            raise CriticalActionBlockedError(
                f"BLOCKED: Homepage protected - last fix {last_fix[0].get('created_at', 'unknown')}, "
                f"14-day cooldown active. Cannot update homepage without manual override."
            )
    
    issue_type = record.get("issue_type", "")
    if issue_type == "full_content_rewrite":
        _log_critical_action_attempt(
            website_id, agent, "full_content_rewrite", status,
            "Full content rewrite forbidden"
        )
        raise CriticalActionBlockedError(
            "BLOCKED: Full content rewrite forbidden - this is critical, use writer for new blog"
        )
    
    wp_post_id = None
    m = __import__("re").search(r"/p(?:osts|ages)/(\d+)", page_url) if page_url else None
    if m:
        wp_post_id = m.group(1)
    
    if not WORDPRESS_URL or not wp_post_id:
        raise ValueError("Cannot update - missing WORDPRESS_URL or post ID")
    
    try:
        page_data = None
        if issue_type in ("missing_meta", "duplicate_title", "low_ctr_title", "missing_h1"):
            wp_resp = httpx.get(
                f"{WORDPRESS_URL}/wp/v2/pages/{wp_post_id}",
                auth=(wp_user, wp_app_password),
                timeout=30.0,
            )
            if wp_resp.status_code == 200:
                page_data = wp_resp.json()
                if issue_type in ("missing_meta", "duplicate_title", "low_ctr_title"):
                    page_data["meta"] = page_data.get("meta", {})
                    page_data["meta"]["description"] = record.get("new_value", "")
                elif issue_type == "missing_h1":
                    page_data["title"] = record.get("new_value", "") + " - " + page_data.get("title", "")
        
        if page_data:
            wp_update = httpx.post(
                f"{WORDPRESS_URL}/wp/v2/pages/{wp_post_id}",
                auth=(wp_user, wp_app_password),
                json=page_data,
                timeout=30.0,
            )
            wp_update.raise_for_status()
            _log_proof(website_id, agent, "update_page_after_approval", "wordpress", "post")
            logger.info("Updated WP page %s for audit %s", wp_post_id, audit_id)
            return wp_update.json()
        
        return record
    except CriticalActionBlockedError:
        raise
    except Exception as e:
        _log_critical_action_attempt(
            website_id, agent, "update_page_on_wordpress", status,
            f"WordPress error: {str(e)}"
        )
        raise


def delete_page_on_wordpress(page_id: str, wp_user: str, wp_app_password: str, 
                             website_id: str, agent: str = "agent") -> dict:
    status = "delete_attempted"
    _log_critical_action_attempt(
        website_id, agent, "delete_page_on_wordpress", status,
        "DELETE BLOCKED: Agents never allowed to delete pages. Manual WordPress admin only."
    )
    raise CriticalActionBlockedError(
        "DELETE BLOCKED: Agents never allowed to delete pages. Manual WordPress admin only."
    )


def publish_llms_txt(content: str, website_id: str, agent: str = "writer") -> dict:
    record = {
        "website_id": website_id,
        "content": content,
        "status": "pending_approval",
    }
    _log_critical_action_attempt(
        website_id, agent, "publish_llms_txt_live", "pending",
        "LLMS.TXT publish requires human approval via dashboard"
    )
    raise CriticalActionBlockedError(
        "BLOCKED: Cannot publish LLMS.TXT - status is pending, must be 'approved' by human"
    )


def disavow_backlink(backlink_url: str, reason: str, website_id: str, agent: str = "backlink_agent") -> dict:
    _log_critical_action_attempt(
        website_id, agent, "disavow_backlink", "requested",
        "Disavow requires human approval via dashboard - this is critical for SEO"
    )
    raise CriticalActionBlockedError(
        "BLOCKED: Cannot disavow backlink - must be approved by human via dashboard"
    )
