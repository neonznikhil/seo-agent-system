import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from ..database import get_supabase
from .slack_app_service import slack_app_service, SLACK_CHANNELS

logger = logging.getLogger("backend.services.slack_intelligence_service")


def _fmt(n) -> str:
    try:
        return f"{int(n):,}"
    except Exception:
        return "0"


class SlackIntelligenceService:
    """Slack reporting built ONLY from real Supabase rows. If a source table is
    empty the report says so — fabricated metrics are never sent."""

    def __init__(self):
        self.app = slack_app_service

    # ------------------------------------------------------------------
    # Helpers: real aggregates
    # ------------------------------------------------------------------
    def _count(self, table: str, filters: Optional[dict] = None, gte_field=None, gte_value=None) -> int:
        try:
            q = get_supabase().table(table).select("id", count="exact")
            for k, v in (filters or {}).items():
                q = q.eq(k, v)
            if gte_field and gte_value:
                q = q.gte(gte_field, gte_value)
            res = q.execute()
            return getattr(res, "count", None) or len(res.data or [])
        except Exception:
            return 0

    def _recent_rows(self, table: str, columns: str, filters: Optional[dict] = None,
                     order: str = "created_at", limit: int = 5) -> List[dict]:
        try:
            q = get_supabase().table(table).select(columns)
            for k, v in (filters or {}).items():
                q = q.eq(k, v)
            return q.order(order, desc=True).limit(limit).execute().data or []
        except Exception:
            return []

    def _resolve_domain(self, website_id: str) -> str:
        try:
            row = (
                get_supabase().table("websites")
                .select("domain")
                .eq("id", website_id)
                .single()
                .execute()
                .data or {}
            )
            return row.get("domain") or "connected website"
        except Exception:
            return "connected website"

    # -------------------------------------------------------------------------
    # Report 1: Morning Brief (Daily at 08:00 IST) -> #rankforge-daily
    # -------------------------------------------------------------------------
    async def send_morning_brief(self, website_id: str = "default") -> bool:
        """Real data briefing: pending approvals, yesterday's published posts, next scheduled run."""
        logger.info("[SlackIntelligence] Generating Daily Morning Brief...")
        domain = self._resolve_domain(website_id)
        today = datetime.utcnow().date().isoformat()

        pending_count = self._count("blog_approvals", {"status": "pending"})
        published_yesterday = self._recent_rows(
            "blog_approvals", "title, approved_at",
            {"status": "published"}, order="approved_at", limit=5,
        )
        published_yesterday = [
            r for r in published_yesterday
            if (r.get("approved_at") or "")[:10] >= (datetime.utcnow() - timedelta(days=1)).date().isoformat()
        ]
        recent_audits = self._recent_rows("technical_audits", "health_score, created_at", None, limit=1)
        health_score = recent_audits[0].get("health_score") if recent_audits else None

        wins_lines = []
        for p in published_yesterday[:3]:
            wins_lines.append(f"• ✅ Published: _{p.get('title', 'Untitled')}_")
        if health_score is not None:
            wins_lines.append(f"• 🩺 Latest technical audit health score: *{health_score}/100*")
        if not wins_lines:
            wins_lines.append("• No completed actions in the last 24h yet — autonomous jobs will fill this in.")

        pending_text = (
            f"⚠️ *{pending_count} article(s) waiting for your approval*" if pending_count
            else "✅ *Approval queue clear*"
        )

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🌅 RankForge Morning Brief — {domain} — {datetime.utcnow().strftime('%B %d, %Y')}"}
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Last 24 Hours:*\n" + "\n".join(wins_lines)}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ("*Today's Autonomous Schedule (Asia/Kolkata):*\n"
                             "• 📝 *11:00 IST* — WriterPipeline generates today's highest-priority article\n"
                             "• 🔗 *11:30 IST* — BacklinkAgent prospecting sweep via Serper.dev\n"
                             "• 🛠 *12:00 IST* — TechSEOAgent full technical audit")
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Needs Your Attention:*\n{pending_text}\n• Direct Link: <{self._frontend_url()}/approvals|Open Approvals Queue →>"
                }
            },
            {"type": "divider"}
        ]

        fallback = f"🌅 RankForge Morning Brief: {pending_count} pending approvals."
        return await self.app.post_block_message(SLACK_CHANNELS["daily"], blocks, fallback, "morning_brief", website_id)

    @staticmethod
    def _frontend_url() -> str:
        import os
        return os.getenv("FRONTEND_URL", "http://localhost:3000")

    # -------------------------------------------------------------------------
    # Report 2: Evening Summary (Daily at 20:00 IST) -> #rankforge-daily
    # -------------------------------------------------------------------------
    async def send_evening_summary(self, website_id: str = "default") -> bool:
        """Real evening wrap-up from tasks + content_log + brain_memory."""
        logger.info("[SlackIntelligence] Generating Daily Evening Summary...")
        day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        generated_today = self._count("content_log", {}, gte_field="created_at", gte_value=day_start)
        published_today = self._count("blog_approvals", {"status": "published"}, gte_field="approved_at", gte_value=day_start)
        opportunities_total = self._count("backlink_opportunities")
        memories_count = self._count("brain_memory")

        accomplishment_lines = [
            f"• *Content*: {_fmt(generated_today)} article(s) entered the pipeline today",
            f"• *Publishing*: {_fmt(published_today)} post(s) approved & published today",
            f"• *Backlinks*: {_fmt(opportunities_total)} total opportunities discovered so far",
            f"• *Brain*: {_fmt(memories_count)} memories learned and stored",
        ]

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🌙 RankForge Evening Summary — {datetime.utcnow().strftime('%B %d, %Y')}"}
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*What We Accomplished Today:*\n" + "\n".join(accomplishment_lines)}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📊 Live System Telemetry:*\n• Pending approvals: `{_fmt(self._count('blog_approvals', {'status': 'pending'}))}`\n• Published all-time: `{_fmt(self._count('blog_approvals', {'status': 'published'}))}`\n• Knowledge base chunks: `{_fmt(self._count('knowledge_base'))}`"
                }
            },
            {"type": "divider"}
        ]

        fallback = f"🌙 RankForge Evening Summary: {generated_today} articles generated, {published_today} published today."
        return await self.app.post_block_message(SLACK_CHANNELS["daily"], blocks, fallback, "evening_summary", website_id)

    # -------------------------------------------------------------------------
    # Report 3: Backlink Intelligence Report -> #rankforge-backlinks
    # -------------------------------------------------------------------------
    async def send_backlink_intelligence_report(self, website_id: str = "default") -> bool:
        """Weekly backlink report from real backlinks/backlink_opportunities tables."""
        logger.info("[SlackIntelligence] Generating Weekly Backlink Intelligence Report...")

        discovered = self._count("backlink_opportunities", {"status": "discovered"})
        briefed = self._count("backlink_opportunities", {"status": "asset_briefed"})
        published_assets = self._count("backlink_opportunities", {"status": "asset_published"})
        acquired_links = self._count("backlinks")

        top_opps = self._recent_rows(
            "backlink_opportunities", "target_domain, domain_rating, opportunity_type",
            {"status": "discovered"}, order="priority_score", limit=3,
        )
        opp_lines = "\n".join(
            f"• *{o.get('target_domain', 'unknown')}* (DR {o.get('domain_rating', '?')}) — {o.get('opportunity_type', 'type').replace('_', ' ')}"
            for o in top_opps
        ) or "• No tier-1 opportunities discovered yet — OpportunityScoutAgent runs automatically."

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🔗 Weekly Backlink Intelligence — {datetime.utcnow().strftime('%B %d, %Y')}"}
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (f"*Pipeline Status:*\n"
                             f"• {_fmt(discovered)} Opportunities Discovered • {_fmt(briefed)} Assets Briefed\n"
                             f"• {_fmt(published_assets)} Assets Published • {_fmt(acquired_links)} Links Acquired All-Time")
                }
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*🎯 Top Tier-1 Opportunities:*\n{opp_lines}"}
            },
            {"type": "divider"}
        ]

        fallback = f"🔗 Weekly Backlink Intelligence: {acquired_links} acquired links, {discovered} open opportunities."
        return await self.app.post_block_message(SLACK_CHANNELS["backlinks"], blocks, fallback, "backlink_report", website_id)

    # -------------------------------------------------------------------------
    # Report 4: Weekly Intelligence Report -> #rankforge-weekly
    # -------------------------------------------------------------------------
    async def send_weekly_intelligence_report(self, website_id: str = "default") -> bool:
        """Weekly founder report from real tables only."""
        logger.info("[SlackIntelligence] Generating Weekly Founder Intelligence Report...")
        week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()

        published_week = self._count("blog_approvals", {"status": "published"}, gte_field="approved_at", gte_value=week_ago)
        generated_week = self._count("content_log", {}, gte_field="created_at", gte_value=week_ago)
        links_week = self._count("backlinks", {}, gte_field="acquired_date", gte_value=week_ago)
        failed_tasks = self._count("tasks", {"status": "failed"}, gte_field="created_at", gte_value=week_ago)

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"📊 RankForge Weekly Intelligence — Week of {datetime.utcnow().strftime('%B %d, %Y')}"}
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (f"*This Week in Numbers:*\n"
                             f"• *Articles Generated*: `{_fmt(generated_week)}`\n"
                             f"• *Articles Published*: `{_fmt(published_week)}`\n"
                             f"• *New Backlinks Acquired*: `{_fmt(links_week)}`\n"
                             f"• *Failed Agent Tasks*: `{_fmt(failed_tasks)}`")
                }
            },
            {"type": "divider"}
        ]

        fallback = f"📊 RankForge Weekly Intelligence: {generated_week} articles, {links_week} links this week."
        return await self.app.post_block_message(SLACK_CHANNELS["weekly"], blocks, fallback, "weekly_report", website_id)

    # -------------------------------------------------------------------------
    # Report 5: Crisis Alert (Immediate) -> #rankforge-alerts
    # -------------------------------------------------------------------------
    async def send_crisis_alert(self, website_id: str, crisis_type: str,
                                description: str, action_taken: str) -> bool:
        logger.warning(f"[SlackIntelligence] Dispatching Immediate Crisis Alert: '{crisis_type}'...")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🚨 CRISIS DETECTED — {crisis_type.upper()}"}
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Event*: {description}\n\n*System Automated Action*: {action_taken}"
                }
            },
            {"type": "divider"}
        ]

        fallback = f"🚨 CRISIS ALERT: {crisis_type} — {description[:80]}"
        return await self.app.post_block_message(SLACK_CHANNELS["alerts"], blocks, fallback, "crisis_alert", website_id)

    # -------------------------------------------------------------------------
    # Report 6: New Learning Alert -> #rankforge-daily
    # -------------------------------------------------------------------------
    async def send_new_learning_alert(self, website_id: str, pattern_name: str,
                                      behavior_change: str, confidence: float,
                                      samples_count: int) -> bool:
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🧠 System Learned Something Important"}
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (f"*Insight*: The system has learned with *{(confidence*100):.0f}% confidence* "
                             f"(based on {samples_count} sampled data points) that *{pattern_name}*.\n\n"
                             f"*Action*: Starting today, *{behavior_change}*.")
                }
            },
            {"type": "divider"}
        ]

        fallback = f"🧠 Brain Learning Alert: {pattern_name} (Confidence: {(confidence*100):.0f}%)"
        return await self.app.post_block_message(SLACK_CHANNELS["daily"], blocks, fallback, "new_learning", website_id)

    # -------------------------------------------------------------------------
    # Event notifications used by agents/pipelines
    # -------------------------------------------------------------------------
    async def notify_agent_completion(self, website_id: str, agent_name: str,
                                      summary: str, items_processed: int) -> bool:
        """[AgentName] completed task: [summary] — [N] items processed."""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"✅ *{agent_name}* completed task: {summary} — *{items_processed}* item(s) processed."
                }
            }
        ]
        fallback = f"✅ {agent_name} completed: {summary} — {items_processed} items processed."
        return await self.app.post_block_message(SLACK_CHANNELS["daily"], blocks, fallback, "agent_completion", website_id)

    async def notify_agent_failure(self, website_id: str, agent_name: str, error: str) -> bool:
        """⚠️ [AgentName] failed: [error message]."""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"⚠️ *{agent_name}* failed: {error[:500]}"
                }
            }
        ]
        fallback = f"⚠️ {agent_name} failed: {error[:120]}"
        return await self.app.post_block_message(SLACK_CHANNELS["alerts"], blocks, fallback, "agent_failure", website_id)

    async def notify_content_generated(self, website_id: str, title: str,
                                       word_count: int, seo_score: float) -> bool:
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (f"📝 *New draft ready for your approval*\n"
                             f"*{title}*\n"
                             f"{word_count:,} words · SEO score {seo_score}/100\n"
                             f"<{self._frontend_url()}/approvals|Review & Approve →>")
                }
            }
        ]
        fallback = f"📝 New draft ready: {title} ({word_count} words)."
        return await self.app.post_block_message(SLACK_CHANNELS["daily"], blocks, fallback, "content_generated", website_id)

    async def notify_content_published(self, website_id: str, title: str,
                                       wordpress_url: Optional[str]) -> bool:
        url_line = f"\n<{wordpress_url}|View live post →>" if wordpress_url else ""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🚀 *Published to WordPress*\n*{title}*{url_line}"
                }
            }
        ]
        fallback = f"🚀 Published: {title}"
        return await self.app.post_block_message(SLACK_CHANNELS["daily"], blocks, fallback, "content_published", website_id)

    async def notify_backlink_discovered(self, website_id: str, domain: str,
                                         domain_rating, opportunity_type: str) -> bool:
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (f"🔗 *New backlink opportunity discovered*\n"
                             f"*{domain}* (DR {domain_rating}) — {opportunity_type.replace('_', ' ')}")
                }
            }
        ]
        fallback = f"🔗 New opportunity: {domain} (DR {domain_rating})"
        return await self.app.post_block_message(SLACK_CHANNELS["backlinks"], blocks, fallback, "backlink_discovered", website_id)


# Global Singleton
slack_intelligence_service = SlackIntelligenceService()
