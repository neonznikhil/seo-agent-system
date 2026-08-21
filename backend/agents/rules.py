from typing import Optional, Any
from datetime import datetime, timedelta

CRITICAL_ACTIONS = [
    "publish_blog_to_wordpress",
    "update_page_on_wordpress",
    "delete_page_on_wordpress",
    "update_homepage_title",
    "update_homepage_content",
    "publish_llms_txt_live",
    "disavow_backlink",
    "update_robots_txt",
    "update_sitemap",
    "bulk_update_more_than_5_pages",
    "full_content_rewrite",
]


class CriticalActionBlockedError(Exception):
    """Raised when an agent attempts a critical action without human approval."""
    pass


def is_critical_action(action_type: str) -> bool:
    """Check if an action is critical and requires human approval."""
    return action_type in CRITICAL_ACTIONS


def require_human_approval(action_type: str, db_record: dict) -> None:
    """
    Verify that a critical action has proper human approval.
    
    Raises CriticalActionBlockedError if:
    - Action is not critical (returns silently)
    - Record status is not 'approved'
    - No human_user_id present
    - No approval_timestamp present
    """
    if not is_critical_action(action_type):
        return
    
    status = db_record.get("status", "unknown")
    human_user_id = db_record.get("human_user_id")
    approval_timestamp = db_record.get("approval_timestamp")
    
    if status != "approved":
        raise CriticalActionBlockedError(
            f"CRITICAL ACTION BLOCKED: {action_type} requires human approval - "
            f"status is {status}, not approved"
        )
    
    if not human_user_id:
        raise CriticalActionBlockedError(
            f"CRITICAL ACTION BLOCKED: {action_type} requires human_user_id - not present"
        )
    
    if not approval_timestamp:
        raise CriticalActionBlockedError(
            f"CRITICAL ACTION BLOCKED: {action_type} requires approval_timestamp - not present"
        )


def check_homepage_cooldown(website_id: str, db_client, cooldown_days: int = 14) -> Optional[dict]:
    """
    Check if homepage is in cooldown period.
    
    Returns dict with cooldown info if in cooldown, None if can proceed.
    """
    from urllib.parse import urlparse
    
    now = datetime.utcnow()
    cooldown_threshold = now - timedelta(days=cooldown_days)
    
    try:
        recent_fix = (
            db_client.table("audits")
            .select("*")
            .eq("website_id", website_id)
            .eq("issue_type", "homepage_update")
            .gte("created_at", cooldown_threshold.isoformat())
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        if recent_fix:
            return recent_fix[0]
    except Exception:
        pass
    
    return None


def validate_approval_for_publish(content_log_id: str, db_client) -> dict:
    """
    Validate that a content log is approved for publishing.
    Returns the record if valid, raises if not.
    """
    record = (
        db_client.table("content_log")
        .select("*")
        .eq("id", content_log_id)
        .single()
        .execute()
        .data
    )
    
    if not record:
        raise CriticalActionBlockedError(f"Content log {content_log_id} not found")
    
    require_human_approval("publish_blog_to_wordpress", record)
    
    return record


def validate_approval_for_update(audit_id: str, db_client, url: str) -> dict:
    """
    Validate that an audit is approved for page update.
    Returns the record if valid, raises if not.
    """
    from .tools.shared_utils import is_homepage
    
    record = (
        db_client.table("audits")
        .select("*")
        .eq("id", audit_id)
        .single()
        .execute()
        .data
    )
    
    if not record:
        raise CriticalActionBlockedError(f"Audit {audit_id} not found")
    
    require_human_approval("update_page_on_wordpress", record)
    
    if is_homepage(url):
        cooldown = check_homepage_cooldown(record.get("website_id", ""), db_client)
        if cooldown:
            raise CriticalActionBlockedError(
                f"BLOCKED: Homepage protected - last fix {cooldown.get('created_at', 'unknown')}, "
                f"{14}-day cooldown active. Cannot update homepage without manual override."
            )
    
    issue_type = record.get("issue_type", "")
    if issue_type == "full_content_rewrite":
        raise CriticalActionBlockedError(
            "BLOCKED: Full content rewrite forbidden - this is critical, use writer for new blog"
        )
    
    return record


def log_blocked_critical_action(
    website_id: str,
    agent_name: str,
    action_type: str,
    status_before: str,
    reason: str,
    db_client
) -> None:
    """Log a blocked critical action to critical_action_logs table."""
    try:
        db_client.table("critical_action_logs").insert({
            "website_id": website_id,
            "agent_name": agent_name,
            "action_type": action_type,
            "attempted_at": datetime.utcnow().isoformat(),
            "blocked": True,
            "block_reason": reason,
            "status_before": status_before,
            "approved_by": None,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass


def log_successful_approval(
    website_id: str,
    agent_name: str,
    action_type: str,
    approved_by: str,
    db_client
) -> None:
    """Log a successful human approval."""
    try:
        db_client.table("critical_action_logs").insert({
            "website_id": website_id,
            "agent_name": agent_name,
            "action_type": action_type,
            "attempted_at": datetime.utcnow().isoformat(),
            "blocked": False,
            "block_reason": None,
            "status_before": "pending_approval",
            "approved_by": approved_by,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass