import os
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from database import get_supabase

logger = logging.getLogger('backend.services.budget_manager')

DEFAULT_DAILY_LIMIT_USD = 20.0

class BudgetManager:
    def __init__(self, website_id: Optional[str] = None):
        self.website_id = website_id

    async def get_today_spend(self, website_id: Optional[str] = None) -> float:
        wid = website_id or self.website_id
        today_str = datetime.utcnow().strftime('%Y-%m-%d')
        supabase = get_supabase()
        try:
            q = supabase.table('daily_costs').select('cost_usd').eq('date', today_str)
            if wid and wid != 'default':
                q = q.eq('website_id', wid)
            res = q.execute()
            rows = res.data or []
            total = sum(float(r.get('cost_usd') or 0.0) for r in rows)
            return round(total, 4)
        except Exception as e:
            logger.warning(f'Budget error: {e}')
            return 0.0

    async def get_daily_limit(self, website_id: Optional[str] = None) -> float:
        wid = website_id or self.website_id
        env_limit = os.getenv('DAILY_BUDGET_USD') or os.getenv('DAILY_BUDGET')
        if env_limit:
            try:
                return float(env_limit)
            except ValueError:
                pass
        if wid and wid != 'default':
            try:
                from services.local_store import get_local_website
                site = get_local_website(wid)
                if site and site.get('daily_budget_usd'):
                    return float(site['daily_budget_usd'])
            except Exception:
                pass
        return DEFAULT_DAILY_LIMIT_USD

    async def check_budget(self, website_id: Optional[str] = None, estimated_cost: float = 0.0) -> Dict[str, Any]:
        wid = website_id or self.website_id
        today_spend = await self.get_today_spend(wid)
        daily_limit = await self.get_daily_limit(wid)
        remaining = max(0.0, round(daily_limit - today_spend, 4))
        if (today_spend + estimated_cost) > daily_limit:
            try:
                get_supabase().table('critical_action_logs').insert({
                    'website_id': wid or 'default',
                    'action': 'budget_exceeded_pause',
                    'status': 'paused',
                    'payload': {'today_spend': today_spend, 'daily_limit': daily_limit, 'estimated_cost': estimated_cost},
                    'created_at': datetime.utcnow().isoformat()
                }).execute()
            except Exception:
                pass
            return {'allowed': False, 'today_spend': today_spend, 'daily_limit': daily_limit, 'remaining': remaining, 'reason': f'Daily budget limit of ${daily_limit:.2f} exceeded (today spend: ${today_spend:.2f})'}
        return {'allowed': True, 'today_spend': today_spend, 'daily_limit': daily_limit, 'remaining': remaining, 'reason': 'Within daily budget'}

    async def record_spend(self, agent_name: str, tokens: int, cost_usd: float, website_id: Optional[str] = None) -> None:
        wid = website_id or self.website_id or 'default'
        try:
            get_supabase().table('daily_costs').insert({
                'id': str(uuid.uuid4()),
                'website_id': wid,
                'date': datetime.utcnow().strftime('%Y-%m-%d'),
                'agent_name': agent_name,
                'tokens': tokens,
                'cost_usd': cost_usd,
                'created_at': datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            logger.warning(f'Record spend error: {e}')

    async def get_budget_summary(self, website_id: Optional[str] = None) -> Dict[str, Any]:
        wid = website_id or self.website_id
        today_spend = await self.get_today_spend(wid)
        daily_limit = await self.get_daily_limit(wid)
        remaining = max(0.0, round(daily_limit - today_spend, 4))
        percent_used = min(100.0, round((today_spend / max(0.01, daily_limit)) * 100, 1))
        return {'today_spend': today_spend, 'daily_limit': daily_limit, 'remaining': remaining, 'percent_used': percent_used, 'can_spend': today_spend < daily_limit}

budget_manager = BudgetManager()
