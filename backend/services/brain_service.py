import logging
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger("backend.services.brain")


class BrainService:
    """Memory and learning service for the SEO brain."""

    def __init__(self, website_id: str = None):
        self.website_id = website_id
        self.supabase = None

    def _get_supabase(self):
        if not self.supabase:
            from ..database import get_supabase
            self.supabase = get_supabase()
        return self.supabase

    async def _get_embedding(self, text: str) -> List[float]:
        from ..database import get_embedding
        return await get_embedding(text, website_id=self.website_id)

    async def remember(
        self,
        website_id: str,
        memory_type: str,
        title: str,
        content: str,
        source_type: str,
        source_id: str,
        confidence: float = 0.8,
    ) -> Optional[str]:
        """Store a memory. If a very similar memory exists, update it instead of duplicating."""
        supabase = self._get_supabase()
        text = f"{title}\n{content[:500]}"
        try:
            embedding = await self._get_embedding(text)
        except Exception as e:
            logger.error(f"Brain remember embedding failed: {e}")
            return None

        existing = []
        try:
            existing = (
                supabase.rpc(
                    "match_brain_memory",
                    {
                        "query_embedding": embedding,
                        "match_threshold": 0.92,
                        "p_website_id": website_id,
                    },
                )
                .execute()
                .data
                or []
            )
        except Exception:
            logger.debug("match_brain_memory RPC not available, skipping duplicate check")

        if existing:
            mem_id = existing[0]["id"]
            try:
                current = (
                    supabase.table("brain_memory")
                    .select("times_used,confidence")
                    .eq("id", mem_id)
                    .single()
                    .execute()
                    .data
                )
                times_used = (current.get("times_used", 0) if current else 0) + 1
                old_conf = current.get("confidence", 0.8) if current else 0.8
                new_conf = round((confidence + old_conf) / 2, 2)
                supabase.table("brain_memory").update(
                    {
                        "times_used": times_used,
                        "confidence": new_conf,
                        "last_used_at": datetime.utcnow().isoformat(),
                    }
                ).eq("id", mem_id).execute()
                return mem_id
            except Exception as e:
                logger.warning(f"Brain duplicate update failed: {e}")

        memory = {
            "id": str(uuid.uuid4()),
            "website_id": website_id,
            "memory_type": memory_type,
            "title": title,
            "content": content,
            "embedding": embedding,
            "source_type": source_type,
            "source_id": source_id,
            "confidence": confidence,
            "times_used": 1,
            "times_successful": 0,
            "last_used_at": datetime.utcnow().isoformat(),
            "created_at": datetime.utcnow().isoformat(),
        }
        supabase.table("brain_memory").insert(memory).execute()
        return memory["id"]

    async def recall(
        self,
        website_id: str,
        query: str,
        memory_type: str = None,
        top_k: int = 5,
        min_confidence: float = 0.6,
    ) -> List[Dict]:
        """Recall memories relevant to query, ranked by weighted score."""
        supabase = self._get_supabase()
        try:
            embedding = await self._get_embedding(query)
        except Exception as e:
            logger.error(f"Brain recall embedding failed: {e}")
            return []

        rows: List[Dict] = []
        try:
            rows = (
                supabase.rpc(
                    "match_brain_memory",
                    {
                        "query_embedding": embedding,
                        "match_threshold": min_confidence,
                        "p_website_id": website_id,
                    },
                )
                .execute()
                .data
                or []
            )
        except Exception:
            logger.debug("match_brain_memory RPC unavailable for recall")

        if not rows:
            return []

        ids = [r["id"] for r in rows[: max(top_k * 3, 20)]]
        full: List[Dict] = []
        try:
            full = (
                supabase.table("brain_memory").select("*").in_("id", ids).execute().data or []
            )
        except Exception:
            pass

        if memory_type:
            full = [m for m in full if m.get("memory_type") == memory_type]

        scored = []
        for m in full:
            sim = next((r["similarity"] for r in rows if r["id"] == m["id"]), 0.0)
            used = max(m.get("times_used", 1), 1)
            success_rate = m.get("times_successful", 0) / used
            score = sim * success_rate * m.get("confidence", 0.8)
            scored.append({**m, "recall_score": round(score, 4)})

        scored.sort(key=lambda x: x["recall_score"], reverse=True)
        return scored[:top_k]

    async def learn_from_content(self, content_id: str) -> Dict[str, Any]:
        """Learn from a published piece of content after 14 days."""
        supabase = self._get_supabase()
        content_rows = (
            supabase.table("content_log").select("*").eq("id", content_id).execute().data or []
        )
        if not content_rows:
            return {"error": "content not found"}
        content = content_rows[0]
        website_id = content["website_id"]
        published_at = content.get("published_at")
        if not published_at:
            return {"status": "not_published"}

        try:
            pub_date = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except Exception:
            return {"status": "invalid_date"}

        if datetime.utcnow().replace(tzinfo=pub_date.tzinfo) - pub_date < timedelta(days=14):
            return {"status": "too_early"}

        keyword = (
            content.get("keyword")
            or content.get("primary_keyword")
            or content.get("title", "").split()[0]
        )
        page_url = content.get("published_url") or content.get("original_page_url")
        position_history: List[Dict] = []
        what_worked: Dict[str, Any] = {}
        what_failed: Dict[str, Any] = {}

        if page_url:
            ranks = (
                supabase.table("rank_tracking")
                .select("*")
                .eq("page_url", page_url)
                .order("created_at")
                .execute()
                .data
                or []
            )
            if ranks:
                position_history = [
                    {
                        "date": r["created_at"],
                        "position": r.get("current_position"),
                        "impressions": r.get("impressions", 0),
                    }
                    for r in ranks
                ]
                start_pos = ranks[0].get("current_position") or 0
                end_pos = ranks[-1].get("current_position") or 0
                if start_pos > 0 and end_pos > 0 and (start_pos - end_pos) >= 3:
                    what_worked["position_improved"] = True
                    what_worked["position_change"] = f"{start_pos} -> {end_pos}"

            decays = (
                supabase.table("content_decay_logs")
                .select("*")
                .eq("website_id", website_id)
                .execute()
                .data
                or []
            )
            page_decays = [d for d in decays if d.get("page_url") == page_url]
            if page_decays:
                what_failed["decay_detected"] = True
                what_failed["decay_percent"] = page_decays[-1].get("decay_percent")

        try:
            from .gsc_service import GSCService

            website = (
                supabase.table("websites")
                .select("domain,gsc_property")
                .eq("id", website_id)
                .single()
                .execute()
                .data
                or {}
            )
            gsc_url = website.get("gsc_property") or f"https://{website.get('domain', '')}"
            gsc = GSCService(website_url=gsc_url)
            if gsc.is_connected():
                end_date = datetime.utcnow().strftime("%Y-%m-%d")
                start_date = (datetime.utcnow() - timedelta(days=28)).strftime("%Y-%m-%d")
                perf = await gsc.get_keyword_performance(
                    start_date=start_date, end_date=end_date, row_limit=2000
                )
                kw_data = [
                    k for k in perf.get("keywords", []) if page_url and k.get("page") == page_url
                ]
                total_clicks = sum(k.get("clicks", 0) for k in kw_data)
                if total_clicks > 100:
                    what_worked["gsc_clicks"] = total_clicks
        except Exception as e:
            logger.warning(f"GSC check failed during learn: {e}")

        recent_geo_cutoff = datetime.utcnow() - timedelta(days=30)
        geo_logs = (
            supabase.table("geo_visibility_logs")
            .select("*")
            .eq("website_id", website_id)
            .execute()
            .data
            or []
        )
        recent_geo = []
        for g in geo_logs:
            try:
                checked = datetime.fromisoformat(g.get("checked_at", "").replace("Z", "+00:00"))
                if checked > recent_geo_cutoff:
                    recent_geo.append(g)
            except Exception:
                pass
        if any(g.get("was_cited") for g in recent_geo):
            what_worked["geo_cited"] = True

        reviews = (
            supabase.table("content_expert_reviews")
            .select("score,passed")
            .eq("content_id", content_id)
            .execute()
            .data
            or []
        )
        if reviews:
            min_score = min(r.get("score", 0) for r in reviews)
            if min_score < 70:
                what_failed["expert_score_below_70"] = min_score

        if what_worked:
            await self.remember(
                website_id=website_id,
                memory_type="outcome",
                title=f"Success: {keyword}",
                content=json.dumps(
                    {"what_worked": what_worked, "content_id": content_id, "keyword": keyword}
                ),
                source_type="content_log",
                source_id=content_id,
                confidence=0.85,
            )
        elif what_failed:
            await self.remember(
                website_id=website_id,
                memory_type="failure",
                title=f"Failure: {keyword}",
                content=json.dumps(
                    {"what_failed": what_failed, "content_id": content_id, "keyword": keyword}
                ),
                source_type="content_log",
                source_id=content_id,
                confidence=0.8,
            )

        perf_record = {
            "id": str(uuid.uuid4()),
            "content_id": content_id,
            "website_id": website_id,
            "keyword": keyword,
            "position_history": json.dumps(position_history),
            "what_worked": json.dumps(what_worked),
            "what_failed": json.dumps(what_failed),
            "learned_at": datetime.utcnow().isoformat(),
        }
        supabase.table("brain_content_performance").insert(perf_record).execute()
        return {"status": "learned", "what_worked": what_worked, "what_failed": what_failed}

    async def get_brand_brain(self, website_id: str) -> str:
        """Get brand context string from memories."""
        facts = await self.recall(
            website_id, "brand facts product tone founder preferences", memory_type="fact", top_k=5
        )
        prefs = await self.recall(
            website_id, "brand preferences tone voice CTA", memory_type="preference", top_k=3
        )
        experiences = await self.recall(
            website_id, "what worked SEO success", memory_type="experience", top_k=3
        )

        parts = []
        if facts:
            parts.append(
                "We know: "
                + "; ".join(f"{m['title']}" for m in facts)
            )
        if prefs:
            parts.append(
                "Preferences: "
                + "; ".join(f"{m['title']}" for m in prefs)
            )
        if experiences:
            parts.append(
                "Experiences: "
                + "; ".join(
                    f"{m['title']} (success {m.get('times_successful', 0)}/{m.get('times_used', 1)})"
                    for m in experiences
                )
            )
        return ". ".join(parts) if parts else "No brand brain yet."

    async def should_auto_add_page(
        self,
        website_id: str,
        keyword: str,
        reason: str,
        priority_score: float,
        business_potential: int = 2,
    ) -> Dict[str, Any]:
        """Decide if a new page should be auto-added."""
        supabase = self._get_supabase()

        failures = (
            supabase.table("brain_memory")
            .select("id,content")
            .eq("website_id", website_id)
            .eq("memory_type", "failure")
            .execute()
            .data
            or []
        )
        failed_count = 0
        for f in failures:
            content = f.get("content", "")
            if keyword.lower() in content.lower():
                failed_count += 1

        if failed_count >= 2:
            return {
                "auto_approve": False,
                "reason": f"Failed {failed_count} times for similar keyword",
            }

        successes = await self.recall(website_id, keyword, memory_type="experience", top_k=3)
        confidence = 0.7
        if successes:
            confidence += 0.1 * min(len(successes), 3)

        auto_approve = (
            priority_score > 80
            and confidence > 0.85
            and business_potential >= 2
            and failed_count < 2
        )

        queue_item = {
            "id": str(uuid.uuid4()),
            "website_id": website_id,
            "suggested_topic": keyword,
            "primary_keyword": keyword,
            "reason": reason,
            "priority_score": priority_score,
            "source": "daily_search",
            "status": "approved_auto" if auto_approve else "suggested",
            "auto_approve": auto_approve,
            "created_at": datetime.utcnow().isoformat(),
        }
        supabase.table("brain_auto_pages_queue").insert(queue_item).execute()

        if auto_approve:
            try:
                await self.remember(
                    website_id=website_id,
                    memory_type="preference",
                    title=f"Auto-approved page: {keyword}",
                    content=f"Priority {priority_score}, reason: {reason}",
                    source_type="brain_auto_pages_queue",
                    source_id=queue_item["id"],
                    confidence=0.9,
                )
            except Exception:
                pass

        return {
            "auto_approve": auto_approve,
            "queue_id": queue_item["id"],
            "confidence": confidence,
        }
