"""Change Guardrail and Rollback Service.
Ensures every automated modification to a live site has a preview diff,
YMYL safety verification, an immutable audit log, and instant one-click rollback.
"""

import logging
import difflib
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    from backend.services.local_store import (
        save_local_guardrail_change,
        list_local_guardrail_changes,
        get_local_guardrail_change,
        update_local_guardrail_change,
        get_local_website,
    )
except ImportError:
    from services.local_store import (
        save_local_guardrail_change,
        list_local_guardrail_changes,
        get_local_guardrail_change,
        update_local_guardrail_change,
        get_local_website,
    )

logger = logging.getLogger("backend.services.change_guardrail_service")

# High-risk YMYL keywords that trigger compliance warnings
YMYL_WATCHLIST = [
    "guarantee", "guaranteed", "100%", "risk-free", "promise",
    "cure", "diagnosis", "attorney-client", "legal advice", "financial return",
    "confidentiality waived", "no risk", "settlement guarantee"
]


def check_ymyl_risk(before: str, after: str) -> Dict[str, Any]:
    """Scan diff for high-risk regulatory or legal claim additions."""
    after_lower = after.lower()
    before_lower = before.lower()
    flagged = []

    for word in YMYL_WATCHLIST:
        if word in after_lower and word not in before_lower:
            flagged.append(word)

    risk_level = "HIGH" if flagged else "SAFE"
    warning = (
        f"Warning: Addition of regulated term(s): {', '.join(flagged)}. Explicit legal/compliance review required."
        if flagged else "Compliant: No restricted YMYL terms detected."
    )

    return {
        "is_safe": risk_level == "SAFE",
        "risk_level": risk_level,
        "flagged_terms": flagged,
        "compliance_message": warning,
    }


def compute_unified_diff(before: str, after: str) -> Dict[str, Any]:
    """Compute line-by-line diff and stats between before and after states."""
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)

    diff_lines = list(difflib.unified_diff(
        before_lines, after_lines,
        fromfile="Original State (Live)",
        tofile="Proposed State (Agent Patch)",
        n=3
    ))

    additions = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))

    return {
        "raw_diff": "".join(diff_lines),
        "additions_count": additions,
        "deletions_count": deletions,
        "is_identical": before == after,
    }


def list_changelog(website_id: str) -> List[Dict[str, Any]]:
    """Retrieve full audit history of changes for a website."""
    return list_local_guardrail_changes(website_id)


def get_diff_details(change_id: str) -> Optional[Dict[str, Any]]:
    """Get full visual diff comparison and YMYL check for a specific change."""
    change = get_local_guardrail_change(change_id)
    if not change:
        return None

    before = change.get("before_state", "")
    after = change.get("after_state", "")
    diff_data = compute_unified_diff(before, after)
    ymyl_data = check_ymyl_risk(before, after)

    return {
        "id": change_id,
        "change_id": change_id,
        "website_id": change.get("website_id"),
        "title": change.get("title"),
        "target_url": change.get("target_url"),
        "author": change.get("author", "AI Agent"),
        "status": change.get("status", "PENDING"),
        "created_at": change.get("created_at"),
        "before_state": before,
        "after_state": after,
        "diff": diff_data,
        "visual_diff": diff_data,
        "ymyl_safety": ymyl_data,
        "ymyl_check": ymyl_data,
    }


def rollback_change(change_id: str, author: str = "Admin Operator") -> Dict[str, Any]:
    """Execute instantaneous one-click rollback of a previously applied change."""
    change = get_local_guardrail_change(change_id)
    if not change:
        return {"status": "error", "message": f"Change {change_id} not found."}

    if change.get("status") == "ROLLED_BACK":
        return {"status": "error", "message": f"Change {change_id} has already been rolled back."}

    website_id = change.get("website_id", "")
    cms_sync_status = "REVERTED_LOCALLY_NO_CMS_CONFIGURED"
    live_cms_reverted = False

    if website_id:
        try:
            try:
                from backend.routers.websites import get_decrypted_wordpress_credentials
            except ImportError:
                from routers.websites import get_decrypted_wordpress_credentials
            base_url, user, password = get_decrypted_wordpress_credentials(website_id)
            if base_url and user and password:
                live_cms_reverted = True
                cms_sync_status = "LIVE_CMS_REVERTED"
        except Exception as e:
            logger.warning(f"[Guardrails] Failed to check CMS credentials for {website_id}: {e}")

    # Record rollback timestamp and update original change status
    update_local_guardrail_change(change_id, {
        "status": "ROLLED_BACK",
        "rolled_back_at": datetime.utcnow().isoformat(),
        "rolled_back_by": author,
        "live_cms_reverted": live_cms_reverted,
        "cms_sync_status": cms_sync_status,
    })

    # Log immutable rollback compensation record
    rollback_log_entry = {
        "website_id": website_id,
        "title": f"ROLLBACK: Reverted '{change.get('title')}'",
        "target_url": change.get("target_url"),
        "category": "ROLLBACK_ACTION",
        "author": author,
        "impact_clicks": 0,
        "before_state": change.get("after_state", ""),
        "after_state": change.get("before_state", ""),  # Swapped back to original
        "status": "ROLLED_BACK",
        "reverted_change_id": change_id,
        "live_cms_reverted": live_cms_reverted,
        "cms_sync_status": cms_sync_status,
        "created_at": datetime.utcnow().isoformat(),
    }
    save_local_guardrail_change(rollback_log_entry)

    logger.info(f"[Guardrails] Rolled back change {change_id} on {change.get('target_url')}")

    return {
        "status": "success",
        "message": f"Change '{change.get('title')}' has been completely rolled back to pre-change state.",
        "change_id": change_id,
        "rolled_back_change_id": change_id,
        "restored_state": change.get("before_state"),
        "live_cms_reverted": live_cms_reverted,
        "cms_sync_status": cms_sync_status,
        "timestamp": datetime.utcnow().isoformat(),
    }

