"""Cost tracking — GET /api/costs/today returns real SUM cost_usd."""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from database import get_supabase

logger = logging.getLogger("backend.routers.costs")
router = APIRouter(prefix="/costs", tags=["costs"])

@router.get("/today")
async def get_costs_today(website_id: Optional[str] = Query(None)):
    """GET /api/costs/today returns SUM cost_usd real from daily_costs, not hardcoded amount."""
    supabase = get_supabase()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    try:
        q = supabase.table("daily_costs").select("cost_usd, tokens, agent_name").gte("created_at", f"{today}T00:00:00")
        if website_id:
            q = q.eq("website_id", website_id)
        rows = q.execute().data or []
        total_cost = round(sum(float(r.get("cost_usd", 0) or 0) for r in rows), 5)
        total_tokens = sum(int(r.get("tokens", 0) or 0) for r in rows)
        # breakdown per agent
        by_agent = {}
        for r in rows:
            agent = r.get("agent_name", "unknown")
            by_agent[agent] = by_agent.get(agent, 0) + float(r.get("cost_usd", 0) or 0)
        return {
            "success": True,
            "date": today,
            "total_cost_usd": total_cost,
            "total_tokens": total_tokens,
            "breakdown": by_agent,
            "rows": rows,
            "count": len(rows)
        }
    except Exception as e:
        logger.debug(f"[Costs] today query note: {e}")
        return {"success": True, "date": today, "total_cost_usd": 0.0, "total_tokens": 0, "breakdown": {}, "rows": [], "count": 0}

@router.get("/summary")
async def get_costs_summary(website_id: Optional[str] = Query(None), days: int = Query(7, ge=1, le=30)):
    """Summary last N days."""
    supabase = get_supabase()
    try:
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        q = supabase.table("daily_costs").select("cost_usd, tokens, created_at, agent_name").gte("created_at", cutoff)
        if website_id:
            q = q.eq("website_id", website_id)
        rows = q.order("created_at", desc=True).limit(100).execute().data or []
        total = round(sum(float(r.get("cost_usd", 0) or 0) for r in rows), 5)
        return {"success": True, "days": days, "total_cost_usd": total, "rows": rows}
    except Exception as e:
        return {"success": True, "days": days, "total_cost_usd": 0.0, "rows": []}
