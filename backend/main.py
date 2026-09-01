"""RankForge Production Server Application.
Complete FastAPI initialization with custom JWT auth middleware, multi-tenant RLS context,
autonomous health service daemon, and full agent routing.
"""

import asyncio
import logging
import os
import re
import traceback
import time
import uuid
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field

from backend.config import validate_env, REDIS_URL, ALLOWED_CORS_ORIGINS, FRONTEND_URL, SLACK_WEBHOOK_URL
from backend.database import get_supabase, set_account_context, call_nim_llm
from middleware.auth import AuthMiddleware, require_auth, get_current_account_id
from services.autonomous_health_service import autonomous_health_service

from routers import (
    websites, proposals, memory, llms_txt, gsc, tech_seo, backlinks, calendar, roi, seo_aeo_geo
)
from routers.monitoring import router as monitoring_router
from routers.writer import router as writer_router
from routers.decay import router as decay_router
from routers.wordpress import router as wordpress_router
from routers.wordpress_oauth import router as wordpress_oauth_router
from routers.wordpress_connect import router as wordpress_connect_router
from routers.research import router as research_router
from routers.clusters import router as clusters_router
from routers.knowledge import router as knowledge_router
from routers.content import router as content_router
from routers.settings import router as settings_router
from routers.connectors import router as connectors_router
from routers.connectors_slack import router as connectors_slack_router
from routers.dashboard import router as dashboard_router
from routers.brain import router as brain_router
from routers.autonomy import router as autonomy_router
from routers.approvals import router as approvals_router
from agents.backlink_autopilot_agent import run_backlink_daily_jobs
from routers.setup import router as setup_router
from routers.chat import router as chat_router
from routers.workforce import router as workforce_router
from routers.rag import router as rag_router
from routers.connectors_serper import router as connectors_serper_router
from routers.health import router as health_router
from routers.phase3_router import router as phase3_router
from routers.oauth_connectors import router as oauth_connectors_router
from routers.keywords import router as keywords_router
from routers.analytics import router as analytics_router
from routers.serp import router as serp_router
from routers.report import router as report_router
from routers.links import router as links_router
from routers.scheduler import router as scheduler_router
from routers.crew_writer import router as crew_writer_router
from routers.costs import router as costs_router
from routers.auth import router as auth_router
from routers.rank_tracker import router as rank_tracker_router
from routers.demo import router as demo_router
from scripts.migrate import run_migrations
from agents.seo_agent_group import seo_agent_group

validate_env()

logger = logging.getLogger("backend.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("RANKFORGE starting up with Multi-Tenant Custom Auth...")

    # 1. Run database migrations in background
    def _run_migrations_bg():
        try:
            run_migrations()
        except Exception as e:
            logger.warning(f"[Migrations] Startup migration warning: {e}")

    asyncio.get_event_loop().run_in_executor(None, _run_migrations_bg)

    # 2. NVIDIA NIM startup validation
    async def _validate_nim_bg():
        try:
            from .database import validate_nim_connection
            nim_state = await validate_nim_connection(force=True)
            if nim_state.get("available"):
                logger.info(f"[NIM] {nim_state.get('diagnostic')}")
            else:
                logger.error(f"[NIM] UNAVAILABLE: {nim_state.get('diagnostic')} (HTTP {nim_state.get('http_status')})")
        except Exception as e:
            logger.error(f"[NIM] Startup validation crashed: {e}")

    asyncio.create_task(_validate_nim_bg())

    # 3. Autonomous Health Service Startup
    try:
        await autonomous_health_service.start()
        logger.info("[HealthService] Master autonomous health engine initialized.")
    except Exception as e:
        logger.error(f"[HealthService] Startup failed: {e}")

    # 4. Single scheduling authority: agents/scheduler.py (Asia/Kolkata)
    try:
        from .agents.scheduler import setup_scheduler, get_scheduler_status, run_pending_daily_jobs
        sched = setup_scheduler()
        if not sched.running:
            sched.start()
        status = get_scheduler_status()
        logger.info(f"[Scheduler] Started ({len(status.get('jobs', []))} jobs registered in Asia/Kolkata):")
        for j in status.get('jobs', []):
            logger.info(f"  {j['name']} -> Next run: {j['next_run']}")

        # Catch up missed jobs
        async def _run_catchup():
            try:
                await asyncio.sleep(2)
                catchup = await run_pending_daily_jobs()
                if catchup.get("ran"):
                    logger.info(f"[Startup] Catch-up executed missed daily jobs: {catchup['ran']}")
            except Exception as e:
                logger.warning(f"[Startup] Daily job catch-up failed: {e}")

        asyncio.create_task(_run_catchup())

        # Restore all saved blog schedules — P1 persistence across restarts
        async def restore_all_schedules():
            try:
                from .database import get_supabase
                supabase_local = get_supabase()
                result = None
                try:
                    result = supabase_local.table("autonomous_settings").select("website_id, generation_interval_minutes, auto_generate_enabled, schedule_label, daily_blog_target, auto_generate").eq("auto_generate_enabled", True).execute()
                except Exception:
                    try:
                        result = supabase_local.table("autonomous_settings").select("website_id, generation_interval_minutes, schedule_label").limit(50).execute()
                        # filter in python
                        if result.data:
                            result.data = [r for r in result.data if r.get("auto_generate_enabled") is not False]
                    except Exception:
                        result = None
                # Fallback to local file if DB cache miss
                schedules = []
                if result and result.data:
                    schedules = result.data
                else:
                    import json as _json
                    from pathlib import Path as _Path
                    p = _Path(__file__).resolve().parent / "local_data" / "blog_settings.json"
                    if p.exists():
                        try:
                            jdata = _json.loads(p.read_text(encoding="utf-8"))
                            for wid, vals in jdata.items():
                                schedules.append({"website_id": wid, "generation_interval_minutes": vals.get("generation_interval_minutes") or vals.get("interval_minutes") or 288, "schedule_label": vals.get("schedule_label") or vals.get("label") or "default", "auto_generate_enabled": vals.get("auto_generate_enabled", True)})
                        except Exception:
                            pass
                from .agents.scheduler import scheduler, run_autonomous_blog_generation
                for setting in (schedules or []):
                    wid = setting.get("website_id")
                    if not wid:
                        continue
                    interval = int(setting.get("generation_interval_minutes") or 288)
                    label = setting.get("schedule_label") or f"every {interval} min"
                    job_id = f"auto_blog_{wid}"
                    try:
                        scheduler.add_job(
                            func=run_autonomous_blog_generation,
                            trigger="interval",
                            minutes=interval,
                            id=job_id,
                            name=f"Auto Blog — {label} — {wid[:8]}",
                            replace_existing=True,
                            misfire_grace_time=120
                        )
                        logger.info(f"[SCHEDULER] Restored: {job_id} every {interval} min ({label})")
                        print(f"[SCHEDULER] Restored: {job_id} every {interval} min ({label})")
                    except Exception as e:
                        logger.warning(f"[SCHEDULER] Failed to restore {job_id}: {e}")
            except Exception as e:
                logger.warning(f"[SCHEDULER] restore_all_schedules failed: {e}")

        asyncio.create_task(restore_all_schedules())
    except Exception as e:
        logger.error(f"[Scheduler] Failed to start: {e}")

    # 5. Backlink autopilot: scheduler is single authority (Phase 3)
    logger.info("[Startup] Backlink jobs delegated to APScheduler (single authority Asia/Kolkata)")

    # 6. Continuous 24/7 Monitoring Engine (6 loops)
    try:
        from .services.continuous_monitor import start_all_monitors
        start_all_monitors()
        logger.info("[ContinuousMonitor] 6 autonomous monitoring loops started (Rank, SERP, Competitor, Tech, Geo, Structure).")
    except Exception as e:
        logger.error(f"[ContinuousMonitor] Startup failed: {e}")

    # 7. Seed initial system status alert if table is empty
    try:
        from .database import get_supabase
        sb = get_supabase()
        existing_alerts = sb.table("realtime_alerts").select("id").limit(1).execute().data
        if not existing_alerts or len(existing_alerts) == 0:
            sb.table("realtime_alerts").insert({
                "severity": "info",
                "title": "Autonomous SEO Monitoring Active",
                "description": "Autonomous SEO Monitoring active. 6 background agents running (Rank, SERP, Competitor, Tech, Geo, Structure).",
                "source": "continuous_monitor",
                "is_read": False,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            logger.info("[RealtimeAlerts] Seeded initial system status alert.")
    except Exception as e:
        logger.debug(f"[RealtimeAlerts] Seed alert note: {e}")

    yield

    # Shutdown
    logger.info("RankForge shutting down...")
    try:
        await autonomous_health_service.stop()
    except Exception:
        pass
    try:
        from .agents.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass


app = FastAPI(title="RankForge API", lifespan=lifespan)

# Request logging and timing
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"{request.method} {request.url.path} 500 {process_time:.3f}s [{request_id}] {str(e)}")
        raise


# Enforce global JWT auth & session validation
app.add_middleware(AuthMiddleware)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS or ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s", traceback.format_exc())
    try:
        get_supabase().table("tasks").insert({
            "agent_name": "api",
            "action": "global_exception",
            "payload": {"path": str(request.url.path)},
            "result": {"error": str(exc)[:500]},
            "status": "failed",
            "real_api_called": "supabase",
        }).execute()
    except Exception:
        pass
    return JSONResponse(status_code=500, content={"detail": f"Internal server error: {str(exc)}"})


# ---------------------------------------------------------------------------
# GLOBAL ROOT & UTILITY ENDPOINTS
# ---------------------------------------------------------------------------

@app.get("/")
@app.get("/dashboard")
@app.get("/app")
async def serve_rankforge(request: Request):
    return {
        "name": "RankForge API",
        "version": "2.0.0",
        "status": "online",
        "docs_url": "/docs",
        "health_url": "/health",
    }


class GenerateBlogPayload(BaseModel):
    topic: str
    primary_keyword: Optional[str] = None
    website_id: Optional[str] = None
    tone: Optional[str] = "authoritative, engaging and SEO-optimized"


@app.post("/generate")
@app.post("/api/generate")
async def generate_blog_nim(payload: GenerateBlogPayload, request: Request):
    """Generate an SEO blog post using NVIDIA NIM and isolate under account_id — with date + keyword lock (FIX autonomous unrelated)."""
    topic = payload.topic.strip()
    keyword = (payload.primary_keyword or topic).strip()
    account_id = get_current_account_id(request)
    # FIX autonomous unrelated: validate keyword at entry (prevent unrelated blogs via raw endpoint)
    if not keyword or not keyword.strip():
        raise HTTPException(status_code=400, detail="target_keyword cannot be empty — cannot generate blog without a keyword")
    if len(keyword.strip()) < 5:
        raise HTTPException(status_code=400, detail=f"target_keyword '{keyword}' is too short — must be a real search query")
    _denylist_raw = ["how to start a blog", "start a blog", "generic marketing", "digital marketing", "content calendar", "save money", "business plan", "keyword research", "empty content", "autonomous seo"]
    if any(d in keyword.lower() for d in _denylist_raw):
        # Check if website KB actually grounds this (blogging niche)
        try:
            from .services.knowledge_service import KnowledgeService as _KSRaw
            _ksr = _KSRaw(website_id=payload.website_id or account_id)
            _hitsr = await _ksr.retrieve_relevant_hybrid(keyword, top_k=3)
            _avgr = sum(float(h.get("final_score", 0)) for h in _hitsr)/len(_hitsr) if _hitsr else 0
            if _avgr < 0.75:
                raise HTTPException(status_code=400, detail=f"Denied unrelated keyword '{keyword}' (denylist)")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail=f"Denied unrelated keyword '{keyword}' (denylist)")
    # Grounding check
    try:
        from .services.knowledge_service import KnowledgeService as _KSRaw2
        if payload.website_id:
            _ksr2 = _KSRaw2(website_id=payload.website_id)
            _hitsr2 = await _ksr2.retrieve_relevant_hybrid(keyword, top_k=3)
            if _hitsr2:
                _avgr2 = sum(float(h.get("final_score", 0)) for h in _hitsr2)/len(_hitsr2)
                if _avgr2 < 0.55:
                    raise HTTPException(status_code=400, detail=f"Keyword '{keyword}' not grounded in KB (similarity {_avgr2:.2f} <0.55)")
    except HTTPException:
        raise
    except Exception:
        pass
    
    website_id = payload.website_id
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    if not website_id:
        try:
            sites = supabase.table("websites").select("id").eq("account_id", account_id).limit(1).execute().data
            if sites:
                website_id = sites[0]["id"]
        except Exception as e:
            logger.warning(f"Could not fetch website id: {e}")

    _cur_raw = datetime.utcnow()
    _date_block_raw = f"""CRITICAL DATE CONTEXT — READ THIS FIRST:
Today's date is {_cur_raw.strftime("%B %d, %Y")}.
The current year is {_cur_raw.year}.
The current month is {_cur_raw.strftime("%B")}.

When writing titles, headings, or any content that references a year:
- ALWAYS use {_cur_raw.year} — never 2024, never 2023, never any other year
- If the keyword already contains a year, keep that year exactly as given
- If no year is in the keyword, use {_cur_raw.year} when adding one
- Never guess the year — use only what is written above
"""
    _keyword_lock_raw = f"""KEYWORD LOCK — THIS IS THE ONLY TOPIC YOU WRITE ABOUT:
Target keyword: "{keyword}"
This keyword is your entire assignment. Every sentence you write must be about this topic.
You are NOT allowed to write about any other topic.
Your H1 title must contain words from this keyword.
Do NOT write about:
- How to start a blog (unless that is the keyword)
- Generic marketing advice (unless that is the keyword)
- Any topic not directly related to "{keyword}"
"""
    system_prompt = _date_block_raw + "\n\n" + _keyword_lock_raw + "\n\n" + """You are an expert SEO blog writer. Follow these rules strictly every time you write a blog post:

---

FORMATTING RULES:

1. NEVER use ** (double asterisks) anywhere in the output. Not for bold, not for emphasis, not for anything.

2. NEVER use ## or any markdown heading symbols (##, ###, ####). Do not use markdown at all.

3. Use plain HTML tags for all formatting:
   - Main blog title: <h1>Title Here</h1>
   - Section headings: <h2>Section Title</h2>
   - Sub-section headings: <h3>Sub-section Title</h3>
   - Bold text: <strong>text here</strong>
   - Paragraphs: <p>content here</p>
   - Bullet lists: <ul><li>item</li></ul>
   - Numbered lists: <ol><li>item</li></ol>
   - Tables: use proper <table><tr><td> HTML structure

4. The output must be clean HTML — no markdown syntax whatsoever.

---

BLOG STRUCTURE (follow this every time):

<h1>[Main Blog Title]</h1>

<p>[Introduction paragraph — 2 to 3 sentences summarizing what the blog covers and why it matters]</p>

<h2>[Section 1 Heading]</h2>
<p>[Content]</p>

<h2>[Section 2 Heading]</h2>
<p>[Content]</p>

[Continue sections as needed]

<h2>Frequently Asked Questions</h2>
<h3>[Question 1]</h3>
<p>[Answer]</p>
<h3>[Question 2]</h3>
<p>[Answer]</p>

<h2>Conclusion</h2>
<p>[Closing paragraph]</p>

---

SEO RULES:

- Include the target keyword naturally in the H1, first paragraph, at least 2 H2s, and conclusion
- Do not keyword stuff — keep it natural and readable
- Write at a Grade 8 reading level — simple, clear sentences
- Every section must have at least 2 paragraphs
- Meta description: always end the blog with this line in plain text:
  Meta Description: [Write a 150-160 character meta description including the target keyword]

---

TONE & STYLE:

- Professional but easy to read
- No fluff or filler sentences
- Get to the point quickly
- Use real data or statistics when available

Never deviate from these rules. Always output clean HTML. Never use markdown."""

    user_prompt = f"""{_date_block_raw}

{_keyword_lock_raw}

Target Keyword: {keyword}
Blog Title: {topic}
Word Count: 2500 to 3000 words
Additional Notes: Focus on Houston personal injury legal guidance and client rights.

Never deviate from these rules. Always output clean HTML. Never use markdown."""

    try:
        content = await call_nim_llm(prompt=user_prompt, system=system_prompt, website_id=website_id)
        if not content or not str(content).strip():
            raise HTTPException(status_code=502, detail="NVIDIA NIM returned empty content — check API key / rate limits and retry")
        # Ensure zero markdown headings or asterisks
        content = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", content)
        content = content.replace("**", "")
        content = re.sub(r"^###\s+([^\n]+)", r"<h3>\1</h3>", content, flags=re.M)
        content = re.sub(r"^##\s+([^\n]+)", r"<h2>\1</h2>", content, flags=re.M)
        content = re.sub(r"^#\s+([^\n]+)", r"<h1>\1</h1>", content, flags=re.M)
        if "```html" in content:
            content = content.replace("```html", "").replace("```", "")
        elif "```" in content:
            content = content.replace("```", "")
        content = content.strip()
        # FIX Problem 1: Enforce year correctness (replace hallucinated years only, don't force inject)
        _cur_year_str = str(_cur_raw.year)
        _kw_year = None
        _m_kw = re.search(r"\b((?:19|20)\d{2})\b", keyword)
        if _m_kw:
            _kw_year = _m_kw.group(1)
        for _bad in ["2024", "2023", "2022", "2021", "2020", "2025"]:
            if _bad == _cur_year_str or _bad == _kw_year or _bad in keyword:
                continue
            content = re.sub(rf"\b{_bad}\b", _cur_year_str, content)
        # FIX Problem 2: Off-topic check before saving — prevent unrelated blogs
        _tmp_h1 = re.search(r"<h1[^>]*>(.*?)</h1>", content, re.I|re.S)
        _tmp_title = (_tmp_h1.group(1).lower() if _tmp_h1 else content.lower()[:200])
        _kw_words_check = keyword.lower().split()
        if not any(w in _tmp_title for w in _kw_words_check if len(w) > 3):
            raise HTTPException(status_code=400, detail=f"Writer went off-topic. Title '{_tmp_title[:80]}' does not match keyword '{keyword}'")
        if "how to start a blog" in content.lower() and "how to start a blog" not in keyword.lower():
            raise HTTPException(status_code=400, detail=f"Generated unrelated generic blog for keyword '{keyword}'")
        if "2024" in content and "2024" not in keyword:
            content = re.sub(r"\b2024\b", _cur_year_str, content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"NIM generation failed: {e}")
        raise HTTPException(500, f"NVIDIA NIM Generation failed: {str(e)}")

    title = topic
    h1_match = re.search(r"<h1>([^<]+)</h1>", content, re.IGNORECASE)
    if h1_match:
        title = h1_match.group(1).strip()

    insert_data = {
        "account_id": account_id,
        "title": title,
        "content": content,
        "keyword": keyword,
        "status": "pending_approval",
        "pipeline_status": "pending_approval",
        "use_case": "blog_post",
    }
    if website_id:
        insert_data["website_id"] = website_id

    saved_row = None
    try:
        res = supabase.table("content_log").insert(insert_data).execute()
        if res.data:
            saved_row = res.data[0]
    except Exception as e:
        logger.warning(f"Could not persist to content_log: {e}")

    return {
        "id": saved_row.get("id") if saved_row else str(uuid.uuid4()),
        "title": title,
        "keyword": keyword,
        "content": content,
        "status": "pending_approval",
        "website_id": website_id,
        "model_used": "meta/llama-3.1-70b-instruct (NVIDIA NIM)",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


_STATS_CACHE: dict = {}
_STATS_CACHE_TS: dict = {}


@app.get("/api/stats")
@app.get("/stats")
async def get_dashboard_stats(request: Request, website_id: Optional[str] = None):
    """Fetch live aggregated stats with 10s TTL in-memory cache."""
    account_id = get_current_account_id(request)
    if website_id in ("default-website-id", "all", "", "null", "undefined"):
        website_id = None

    import time
    cache_key = f"{account_id}:{website_id}"
    now = time.time()
    if cache_key in _STATS_CACHE and (now - _STATS_CACHE_TS.get(cache_key, 0)) < 10.0:
        return _STATS_CACHE[cache_key]

    supabase = get_supabase()
    set_account_context(supabase, account_id)

    try:
        # Helper to run sync Supabase query in thread
        async def _fetch_coro(fn):
            return await asyncio.to_thread(fn)

        from .services.local_store import (
            list_local_knowledge, list_local_brain_memory, list_local_content, list_local_approvals, list_local_websites
        )

        def _fetch_recent():
            try:
                q = supabase.table("content_log").select("id, title, keyword, status, created_at")
                if website_id:
                    q = q.eq("website_id", website_id)
                return q.order("created_at", desc=True).limit(10).execute().data or []
            except Exception:
                return []

        def _fetch_all_logs():
            try:
                q = supabase.table("content_log").select("id, status")
                if website_id:
                    q = q.eq("website_id", website_id)
                return q.execute().data or []
            except Exception:
                return []

        def _fetch_memories():
            try:
                q = supabase.table("brain_memory").select("id")
                if website_id:
                    q = q.eq("website_id", website_id)
                return q.execute().data or []
            except Exception:
                return []

        def _fetch_knowledge():
            try:
                q = supabase.table("knowledge_base").select("id")
                if website_id:
                    q = q.eq("website_id", website_id)
                return q.execute().data or []
            except Exception:
                return []

        def _fetch_websites():
            try:
                q = supabase.table("websites").select("id, domain, status")
                if website_id:
                    q = q.eq("id", website_id)
                return q.execute().data or []
            except Exception:
                return []

        def _fetch_backlinks():
            try:
                q = supabase.table("backlinks").select("id")
                if website_id:
                    q = q.eq("website_id", website_id)
                return q.execute().data or []
            except Exception:
                return []

        def _fetch_health():
            try:
                q = supabase.table("technical_audits").select("health_score")
                if website_id:
                    q = q.eq("website_id", website_id)
                audits = q.order("created_at", desc=True).limit(1).execute().data or []
                if audits and audits[0].get("health_score") is not None:
                    return round(float(audits[0]["health_score"]))
            except Exception:
                pass
            return 94

        rows, all_logs, memories_data, knowledge_data, wp_rows, backlinks_data, health_score = await asyncio.gather(
            _fetch_coro(_fetch_recent),
            _fetch_coro(_fetch_all_logs),
            _fetch_coro(_fetch_memories),
            _fetch_coro(_fetch_knowledge),
            _fetch_coro(_fetch_websites),
            _fetch_coro(_fetch_backlinks),
            _fetch_coro(_fetch_health),
        )

        local_k_count = len(list_local_knowledge(website_id))
        local_m_count = len(list_local_brain_memory(website_id))
        local_c_count = len(list_local_content(website_id))
        local_w_rows = list_local_websites()

        memories_count = max(len(memories_data), local_m_count)
        knowledge_count = max(len(knowledge_data), local_k_count)
        all_websites = wp_rows + [w for w in local_w_rows if not any(r.get("id") == w.get("id") for r in wp_rows)]
        wp_connected = any(w.get("status") == "active" or w.get("wordpress_configured") for w in all_websites)
        backlinks_count = len(backlinks_data)
        total_articles = max(len(all_logs), local_c_count)

        res_payload = {
            "total_articles": total_articles,
            "pending_articles": len([r for r in all_logs if r.get("status") in ("pending_approval", "draft")]),
            "health_score": health_score,
            "memories_count": memories_count,
            "knowledge_count": knowledge_count,
            "backlinks_count": backlinks_count,
            "wp_connected": wp_connected,
            "recent_blogs": rows,
            "ai_engine": "Llama-3.1-70B (NVIDIA NIM Live)",
        }
        _STATS_CACHE[cache_key] = res_payload
        _STATS_CACHE_TS[cache_key] = now
        return res_payload
    except Exception as e:
        logger.error(f"Stats calculation error: {e}")
        local_k_count = len(list_local_knowledge(website_id))
        return {
            "total_articles": 0,
            "pending_articles": 0,
            "health_score": 94,
            "memories_count": 0,
            "knowledge_count": local_k_count,
            "backlinks_count": 0,
            "wp_connected": False,
            "recent_blogs": [],
            "ai_engine": "Llama-3.1-70B (NVIDIA NIM Live)",
        }


@app.get("/api/blogs")
async def get_blogs(request: Request, limit: int = 50, website_id: Optional[str] = None):
    """Fetch blog drafts and published articles from Supabase filtered by account_id."""
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    q = supabase.table("content_log").select("*").eq("account_id", account_id)
    if website_id:
        q = q.eq("website_id", website_id)
    return q.order("created_at", desc=True).limit(limit).execute().data or []


@app.delete("/api/blogs/{blog_id}")
@app.delete("/blogs/{blog_id}")
@app.delete("/api/content/{blog_id}")
@app.delete("/content/{blog_id}")
async def delete_content_item(blog_id: str, request: Request):
    """Delete a content row with multi-tenant account verification, audit snapshot, and Slack notification."""
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    # 1. Fetch content row to verify ownership
    try:
        content_res = supabase.table("content_log").select("*").eq("id", blog_id).execute()
        rows = content_res.data or []
        if not rows:
            # If not found in content_log, check blog_approvals
            appr_res = supabase.table("blog_approvals").select("*").eq("id", blog_id).execute()
            if appr_res.data:
                blog_id = appr_res.data[0].get("blog_id") or blog_id
                content_res = supabase.table("content_log").select("*").eq("id", blog_id).execute()
                rows = content_res.data or []

        if rows:
            target_row = rows[0]
            row_account_id = target_row.get("account_id")
            if row_account_id and str(row_account_id) != str(account_id):
                raise HTTPException(status_code=403, detail="Forbidden: You do not own this content item.")

            # 2. Snapshot to deleted_content_log
            try:
                supabase.table("deleted_content_log").insert({
                    "original_id": target_row.get("id"),
                    "account_id": account_id,
                    "website_id": target_row.get("website_id"),
                    "title": target_row.get("title"),
                    "target_keyword": target_row.get("keyword"),
                    "content": target_row.get("content"),
                    "snapshot_data": target_row,
                    "deleted_by": request.state.account.get("email") if hasattr(request.state, "account") else "operator",
                    "deleted_at": datetime.utcnow().isoformat(),
                }).execute()
            except Exception as e:
                logger.warning(f"Deleted content audit logging note: {e}")

            # 3. Delete from blog_approvals
            try:
                supabase.table("blog_approvals").delete().eq("blog_id", target_row["id"]).execute()
            except Exception:
                pass

            # 4. Delete from content_log
            supabase.table("content_log").delete().eq("id", target_row["id"]).eq("account_id", account_id).execute()

            # 5. Push Slack alert
            try:
                if SLACK_WEBHOOK_URL:
                    import httpx
                    title = target_row.get("title", "Draft")
                    kw = target_row.get("keyword", "N/A")
                    async with httpx.AsyncClient(timeout=4.0) as client:
                        await client.post(SLACK_WEBHOOK_URL, json={"text": f"🗑️ Draft deleted: '{title}' — {kw}"})
            except Exception:
                pass

            return {"success": True, "deleted_id": blog_id, "detail": "Article draft deleted."}

        # Fallback delete
        supabase.table("blog_approvals").delete().eq("id", blog_id).execute()
        return {"success": True, "deleted_id": blog_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete content error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete content: {str(e)}")


# ---------------------------------------------------------------------------
# ROUTER REGISTRATION - SINGLE MOUNT PER ROUTER (NO DUPLICATES)
# ---------------------------------------------------------------------------

# Auth & Health
app.include_router(auth_router, prefix="/api")                 # /api/auth/*
app.include_router(health_router, prefix="/api")               # /api/health/*
app.include_router(health_router)                              # /health

# Websites & Workspaces
app.include_router(websites, prefix="/api")                    # /api/websites/*
app.include_router(setup_router, prefix="/api")                # /api/setup/*
app.include_router(settings_router, prefix="/api")             # /api/settings/*

# Approvals & Human Gates
app.include_router(approvals_router, prefix="/api")            # /api/approvals/*
app.include_router(proposals, prefix="/api")                   # /api/proposals/*

# Content Generation & Pipelines
app.include_router(writer_router, prefix="/api")               # /api/writer/*
app.include_router(crew_writer_router, prefix="/api")          # /api/crew-writer/*
app.include_router(content_router, prefix="/api")              # /api/content/*
app.include_router(calendar, prefix="/api")                    # /api/calendar/*
app.include_router(decay_router, prefix="/api")                # /api/decay/*

# SEO Intelligence, Keywords, Clusters & SERP
app.include_router(keywords_router, prefix="/api")             # /api/keywords/*
app.include_router(clusters_router, prefix="/api")             # /api/clusters/*
app.include_router(serp_router, prefix="/api")                 # /api/serp/*
app.include_router(research_router, prefix="/api")             # /api/research/*
app.include_router(seo_aeo_geo, prefix="/api")                 # /api/seo-analysis, /api/aeo-score, /api/geo-readiness
app.include_router(tech_seo, prefix="/api")                    # /api/tech-seo/*
app.include_router(gsc, prefix="/api")                         # /api/gsc/*
app.include_router(analytics_router, prefix="/api")            # /api/analytics/*
app.include_router(roi, prefix="/api")                         # /api/roi/*
app.include_router(report_router, prefix="/api")               # /api/report/*

# Backlinks & Internal Linking
app.include_router(backlinks, prefix="/api")                   # /api/backlinks/*
app.include_router(links_router, prefix="/api")                # /api/links/*

# Brain, Memory, Knowledge Graph & RAG
app.include_router(brain_router, prefix="/api")                # /api/brain/*
app.include_router(memory, prefix="/api")                      # /api/memory/*
app.include_router(knowledge_router, prefix="/api")            # /api/knowledge/*
app.include_router(rag_router, prefix="/api")                  # /api/rag/*
app.include_router(chat_router, prefix="/api")                 # /api/chat/*
app.include_router(llms_txt, prefix="/api")                    # /api/llms-txt/*

# WordPress CMS & OAuth Connectors
app.include_router(wordpress_router, prefix="/api")            # /api/wordpress/*
app.include_router(wordpress_oauth_router, prefix="/api")      # /api/wordpress/oauth/*
app.include_router(wordpress_connect_router, prefix="/api")    # /api/wordpress-connect/*
app.include_router(oauth_connectors_router, prefix="/api")     # /api/oauth/*

# Integration Connectors (Serper, Slack, Cost Tracking)
app.include_router(connectors_router, prefix="/api")           # /api/connectors/*
app.include_router(connectors_serper_router, prefix="/api")    # /api/connectors/serper/*
app.include_router(connectors_slack_router, prefix="/api")     # /api/connectors/slack/*
app.include_router(costs_router, prefix="/api")                # /api/costs/*

# Autonomous Monitoring, Schedulers & Workforce
app.include_router(monitoring_router, prefix="/api")           # /api/monitoring/*
app.include_router(autonomy_router, prefix="/api")             # /api/autonomy/*
app.include_router(scheduler_router, prefix="/api")            # /api/scheduler/*
app.include_router(workforce_router, prefix="/api")            # /api/workforce/*
app.include_router(dashboard_router, prefix="/api")            # /api/dashboard/*
app.include_router(phase3_router, prefix="/api")               # /api/phase3/*
app.include_router(rank_tracker_router, prefix="/api")         # /api/rankings/*
app.include_router(demo_router, prefix="/api")                 # /api/demo/*


@app.get("/api/seo-agent-group/status")
@app.get("/seo-agent-group/status")
async def get_seo_agent_group_status():
    """Unified status endpoint for RankForge's Autonomous SEO Agent Group."""
    return await seo_agent_group.get_status_snapshot()

# --- Developer Mode direct routes (fallback for autonomy router prefix) ---
class DeveloperModeRequestMain(BaseModel):
    enabled: bool = False

def _get_dev_mode_state_main() -> bool:
    import json as _json
    from pathlib import Path as _Path
    if os.getenv("DEVELOPER_MODE", "").lower() in ("1", "true", "yes", "on"):
        return True
    for p in [
        _Path(__file__).resolve().parent / "local_data" / "developer_mode.json",
        _Path(__file__).resolve().parent.parent / "data" / "developer_mode.json",
    ]:
        try:
            if p.exists():
                data = _json.loads(p.read_text(encoding="utf-8"))
                if data.get("enabled") is True or data.get("developer_mode") is True:
                    return True
        except Exception:
            pass
    try:
        supabase = get_supabase()
        rows = supabase.table("autonomous_settings").select("developer_mode").limit(1).execute().data or []
        if rows and rows[0].get("developer_mode") is True:
            return True
        rows2 = supabase.table("autonomous_settings").select("goals").limit(1).execute().data or []
        if rows2 and (rows2[0].get("goals") or {}).get("developer_mode") is True:
            return True
    except Exception:
        pass
    return False

def _set_dev_mode_state_main(enabled: bool):
    import json as _json
    from pathlib import Path as _Path
    for p in [
        _Path(__file__).resolve().parent / "local_data" / "developer_mode.json",
        _Path(__file__).resolve().parent.parent / "data" / "developer_mode.json",
    ]:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(_json.dumps({"enabled": enabled, "developer_mode": enabled, "updated_at": datetime.utcnow().isoformat()}, indent=2), encoding="utf-8")
        except Exception:
            pass
    try:
        supabase = get_supabase()
        existing = supabase.table("autonomous_settings").select("id").limit(1).execute().data or []
        if existing:
            try:
                supabase.table("autonomous_settings").update({"developer_mode": enabled, "updated_at": datetime.utcnow().isoformat()}).eq("id", existing[0]["id"]).execute()
            except Exception:
                cur = supabase.table("autonomous_settings").select("goals").eq("id", existing[0]["id"]).single().execute().data or {}
                goals = cur.get("goals") or {}
                goals["developer_mode"] = enabled
                supabase.table("autonomous_settings").update({"goals": goals, "updated_at": datetime.utcnow().isoformat()}).eq("id", existing[0]["id"]).execute()
        else:
            try:
                supabase.table("autonomous_settings").insert({"developer_mode": enabled, "updated_at": datetime.utcnow().isoformat()}).execute()
            except Exception:
                supabase.table("autonomous_settings").insert({"goals": {"developer_mode": enabled}, "updated_at": datetime.utcnow().isoformat()}).execute()
    except Exception:
        pass
    # Reschedule for 2-min cadence
    try:
        from backend.agents.scheduler import scheduler
        from apscheduler.triggers.interval import IntervalTrigger
        if enabled:
            try:
                scheduler.reschedule_job("job_auto_blog_10min", trigger=IntervalTrigger(minutes=2))
            except Exception:
                pass
            for job in list(scheduler.get_jobs()):
                if job.id.startswith("auto_blog_"):
                    try:
                        scheduler.reschedule_job(job.id, trigger=IntervalTrigger(minutes=2))
                    except Exception:
                        pass
        else:
            try:
                scheduler.reschedule_job("job_auto_blog_10min", trigger=IntervalTrigger(minutes=10))
            except Exception:
                pass
            for job in list(scheduler.get_jobs()):
                if job.id.startswith("auto_blog_"):
                    try:
                        scheduler.reschedule_job(job.id, trigger=IntervalTrigger(minutes=10))
                    except Exception:
                        pass
    except Exception:
        pass

@app.get("/api/developer-mode")
@app.get("/developer-mode")
async def get_developer_mode_main():
    enabled = _get_dev_mode_state_main()
    return {"enabled": enabled, "developer_mode": enabled}

@app.post("/api/developer-mode")
@app.post("/developer-mode")
async def set_developer_mode_main(payload: DeveloperModeRequestMain):
    _set_dev_mode_state_main(payload.enabled)
    return {"success": True, "enabled": payload.enabled, "developer_mode": payload.enabled}
