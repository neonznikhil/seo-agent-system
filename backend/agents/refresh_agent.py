"""RankForge Refresh Agent.
Identifies decaying articles, performs SERP gap analysis, generates refreshed content
via CrewAI/NVIDIA NIM, and stages drafts directly into the human approval queue.
"""
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger("backend.agents.refresh")


class RefreshAgent:
    """Auto-refresh decaying content by delegating to real content_refresh engine."""
    
    def __init__(self, website_id: Optional[str] = None):
        self.website_id = website_id
        self.decay_log_id = None
        self.content_id = None
        self.original_url = None
        self.primary_keyword = None
    
    async def refresh_content(self, decay_log_id: str, website_id: Optional[str] = None) -> Dict[str, Any]:
        """Run real pipeline refresh for decayed content and stage for approval."""
        if website_id:
            self.website_id = website_id
        
        self.decay_log_id = decay_log_id
        self.content_id = str(uuid.uuid4())
        
        from database import get_supabase
        decay = {}
        try:
            supabase = get_supabase()
            res = supabase.table("content_decay_logs").select("*").eq("id", decay_log_id).maybe_single().execute()
            decay = res.data or {}
            if not decay:
                res_q = supabase.table("content_refresh_queue").select("*").eq("id", decay_log_id).maybe_single().execute()
                decay = res_q.data or {}
        except Exception:
            decay = {}
        
        if not decay:
            from services.local_store import list_local_content, list_local_refresh_queue
            for item in list_local_refresh_queue(self.website_id):
                if str(item.get("id")) == str(decay_log_id):
                    decay = item
                    break
            if not decay:
                for item in list_local_content(self.website_id):
                    if str(item.get("id")) == str(decay_log_id) or str(item.get("decay_log_id")) == str(decay_log_id):
                        decay = item
                        break

        self.original_url = decay.get("page_url") or decay.get("url")
        self.primary_keyword = decay.get("primary_keyword") or decay.get("target_keyword") or "decaying-topic"
        
        from services.content_refresh import refresh_decaying_article
        queue_item = {
            "website_id": self.website_id or decay.get("website_id", "default"),
            "blog_id": decay.get("blog_id") or decay.get("page_id") or decay_log_id,
            "wp_post_id": decay.get("wp_post_id"),
            "target_keyword": self.primary_keyword,
            "reason": decay.get("reason") or f"Decay detected on {self.original_url}",
            "status": "pending",
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "id": decay_log_id,
        }
        
        try:
            approval = await refresh_decaying_article(queue_item)
            
            # Update decay log and refresh queue if supabase connected
            try:
                supabase = get_supabase()
                supabase.table("content_decay_logs").update({
                    "status": "draft_ready",
                    "refreshed_content_id": approval.get("id") if approval else self.content_id
                }).eq("id", decay_log_id).execute()
                supabase.table("content_refresh_queue").update({
                    "status": "completed"
                }).eq("id", decay_log_id).execute()
            except Exception:
                pass

            try:
                from services.local_store import save_local_refresh_queue
                save_local_refresh_queue({"id": decay_log_id, "status": "completed"})
            except Exception:
                pass
                
            return {
                "status": "completed",
                "content_id": self.content_id,
                "decay_log_id": decay_log_id,
                "original_url": self.original_url,
                "primary_keyword": self.primary_keyword,
                "pipeline_status": "completed",
                "approval_id": approval.get("id") if approval else None,
                "title": approval.get("title") if approval else None,
                "seo_score": approval.get("seo_score") if approval else None,
                "is_refresh": True,
            }
        except Exception as e:
            logger.error(f"[RefreshAgent] Error executing refresh for {decay_log_id}: {e}")
            return {"status": "error", "error": str(e), "decay_log_id": decay_log_id}


async def run_refresh_pipeline(decay_log_id: str, website_id: str) -> Dict[str, Any]:
    agent = RefreshAgent(website_id=website_id)
    return await agent.refresh_content(decay_log_id, website_id)


run_refresh_agent = run_refresh_pipeline