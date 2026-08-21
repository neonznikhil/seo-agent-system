AGENT_LIMITS = {
    "auditor": {
        "schedule": "weekly",
        "max_pages": 50,
        "max_issues": 10,
        "cooldown_days": 7,
        "priority": "high_impact_only",
    },
    "editor": {
        "schedule": "twice_weekly",
        "days": ["Tue", "Fri"],
        "max_fixes": 5,
        "cooldown_days_homepage": 14,
        "forbidden": ["full_rewrite", "homepage_daily", "all_pages"],
        "condition": "ctr<3% or impressions>500",
    },
    "writer": {
        "schedule": "daily",
        "max_blogs": 2,
        "min_hours": 12,
        "condition": "active_keywords_exist",
        "threshold": 0.85,
    },
    "llms_txt": {
        "schedule": "monthly",
        "min_days": 30,
        "condition": "new_blogs>=10 or 30 days",
        "max_per_month": 1,
    },
    "tech_seo": {
        "schedule": "weekly",
        "max_issues": 20,
    },
    "backlink": {
        "schedule": "weekly",
    },
}


def should_run_agent(agent_name: str, website_id: str) -> tuple[bool, str]:
    from ..database import get_supabase
    from datetime import datetime, timedelta
    import time

    limits = AGENT_LIMITS.get(agent_name, {})
    now = datetime.utcnow()
    reasons = []

    try:
        if agent_name == "auditor":
            weekday = now.strftime("%a")
            if weekday != "Mon":
                return False, f"Not Monday ({weekday})"
            cutoff = now - timedelta(days=limits.get("cooldown_days", 7))
            res = (
                get_supabase()
                .table("tasks")
                .select("created_at")
                .eq("website_id", website_id)
                .eq("action", "run_auditor")
                .gte("created_at", cutoff.isoformat())
                .limit(1)
                .execute()
            )
            if res.data:
                return False, "Cooldown: ran this week"

        elif agent_name == "editor":
            weekday = now.strftime("%a")
            if weekday not in limits.get("days", []):
                return False, f"Not scheduled day ({weekday})"
            cutoff = now - timedelta(days=limits.get("cooldown_days_homepage", 14))
            res = (
                get_supabase()
                .table("tasks")
                .select("created_at, metadata")
                .eq("website_id", website_id)
                .eq("action", "run_editor")
                .gte("created_at", cutoff.isoformat())
                .limit(1)
                .execute()
            )
            if res.data:
                return False, "Cooldown: ran recently"

        elif agent_name == "writer":
            cutoff = now - timedelta(hours=limits.get("min_hours", 12))
            res = (
                get_supabase()
                .table("tasks")
                .select("created_at")
                .eq("website_id", website_id)
                .eq("action", "run_writer")
                .gte("created_at", cutoff.isoformat())
                .limit(1)
                .execute()
            )
            if res.data:
                return False, "Cooldown: ran within 12h"

        elif agent_name == "tech_seo":
            cutoff = now - timedelta(days=7)
            res = (
                get_supabase()
                .table("tasks")
                .select("created_at")
                .eq("website_id", website_id)
                .eq("action", "run_tech_seo")
                .gte("created_at", cutoff.isoformat())
                .limit(1)
                .execute()
            )
            if res.data:
                return False, "Cooldown: ran this week"

        elif agent_name == "backlink":
            cutoff = now - timedelta(days=7)
            res = (
                get_supabase()
                .table("tasks")
                .select("created_at")
                .eq("website_id", website_id)
                .eq("action", "run_backlink")
                .gte("created_at", cutoff.isoformat())
                .limit(1)
                .execute()
            )
            if res.data:
                return False, "Cooldown: ran this week"

        elif agent_name == "llms_txt":
            cutoff = now - timedelta(days=limits.get("min_days", 30))
            res = (
                get_supabase()
                .table("tasks")
                .select("created_at")
                .eq("website_id", website_id)
                .eq("action", "run_llms_txt")
                .gte("created_at", cutoff.isoformat())
                .limit(1)
                .execute()
            )
            if res.data:
                return False, "Cooldown: ran within 30 days"

        return True, "OK"
    except Exception as e:
        return True, f"Error checking limits: {e}"
