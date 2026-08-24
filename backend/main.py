"""RankForge Production Server Application.
Complete FastAPI initialization with custom JWT auth middleware, multi-tenant RLS context,
autonomous health service daemon, and full agent routing.
"""

import asyncio
import logging
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

from .config import validate_env, REDIS_URL, ALLOWED_CORS_ORIGINS, FRONTEND_URL, SLACK_WEBHOOK_URL
from .database import get_supabase, set_account_context, call_nim_llm
from .middleware.auth import AuthMiddleware, require_auth, get_current_account_id
from .services.autonomous_health_service import autonomous_health_service

from .routers import (
    websites, proposals, memory, llms_txt, gsc, tech_seo, backlinks, calendar, roi, seo_aeo_geo
)
from .routers.monitoring import router as monitoring_router
from .routers.writer import router as writer_router
from .routers.decay import router as decay_router
from .routers.wordpress import router as wordpress_router
from .routers.wordpress_oauth import router as wordpress_oauth_router
from .routers.wordpress_connect import router as wordpress_connect_router
from .routers.research import router as research_router
from .routers.clusters import router as clusters_router
from .routers.knowledge import router as knowledge_router
from .routers.content import router as content_router
from .routers.settings import router as settings_router
from .routers.connectors import router as connectors_router
from .routers.connectors_slack import router as connectors_slack_router
from .routers.dashboard import router as dashboard_router
from .routers.brain import router as brain_router
from .routers.autonomy import router as autonomy_router
from .routers.approvals import router as approvals_router
from .agents.backlink_autopilot_agent import run_backlink_daily_jobs
from .routers.setup import router as setup_router
from .routers.chat import router as chat_router
from .routers.workforce import router as workforce_router
from .routers.rag import router as rag_router
from .routers.connectors_serper import router as connectors_serper_router
from .routers.health import router as health_router
from .routers.phase3_router import router as phase3_router
from .routers.oauth_connectors import router as oauth_connectors_router
from .routers.keywords import router as keywords_router
from .routers.analytics import router as analytics_router
from .routers.serp import router as serp_router
from .routers.report import router as report_router
from .routers.links import router as links_router
from .routers.auth import router as auth_router
from .scripts.migrate import run_migrations
from .agents.seo_agent_group import seo_agent_group

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
    except Exception as e:
        logger.error(f"[Scheduler] Failed to start: {e}")

    # 5. Backlink autopilot loop
    try:
        asyncio.create_task(run_backlink_daily_jobs())
        logger.info("[Startup] Backlink autopilot loop started")
    except Exception as e:
        logger.error(f"[Startup] Backlink autopilot init failed: {e}")

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
    accept = request.headers.get("accept", "")
    if accept == "application/json":
        return {
            "name": "RankForge API",
            "version": "2.0.0",
            "status": "online",
            "docs_url": "/docs",
            "health_url": "/health",
        }
    
    html_path = Path(__file__).resolve().parent.parent / "rankforge.html"
    if html_path.exists():
        return FileResponse(str(html_path), media_type="text/html")
    return {"name": "RankForge API", "status": "online", "docs": "/docs"}


class GenerateBlogPayload(BaseModel):
    topic: str
    primary_keyword: Optional[str] = None
    website_id: Optional[str] = None
    tone: Optional[str] = "authoritative, engaging and SEO-optimized"


@app.post("/generate")
@app.post("/api/generate")
async def generate_blog_nim(payload: GenerateBlogPayload, request: Request):
    """Generate an SEO blog post using NVIDIA NIM and isolate under account_id."""
    topic = payload.topic.strip()
    keyword = (payload.primary_keyword or topic).strip()
    account_id = get_current_account_id(request)
    
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

    system_prompt = (
        "You are RankForge's Autonomous SEO Content Writer. Write high-ranking, comprehensive, "
        "well-structured articles with clear H2 and H3 sections, actionable bullet points, "
        "and direct answers to user search intent. Avoid generic filler AI buzzwords."
    )
    user_prompt = (
        f"Write an in-depth, production-ready SEO blog post.\n"
        f"Topic: {topic}\n"
        f"Primary Keyword: {keyword}\n"
        f"Tone: {payload.tone}\n\n"
        f"Structure required:\n"
        f"1. Title (H1 format)\n"
        f"2. Executive summary in the first 100 words\n"
        f"3. 4-5 Detailed H2 sections\n"
        f"4. Comparison table or key takeaways\n"
        f"5. Actionable FAQ section (3 questions)\n"
        f"6. Conclusion\n\n"
        f"Return the entire article in Markdown format."
    )

    try:
        content = await call_nim_llm(prompt=user_prompt, system=system_prompt, website_id=website_id)
    except Exception as e:
        logger.error(f"NIM generation failed: {e}")
        raise HTTPException(500, f"NVIDIA NIM Generation failed: {str(e)}")

    title = topic
    lines = [line.strip() for line in content.split("\n") if line.strip()]
    for line in lines[:5]:
        if line.startswith("# "):
            title = line.replace("# ", "").strip()
            break
        elif line.startswith("Title:"):
            title = line.replace("Title:", "").strip()
            break

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


@app.get("/api/stats")
@app.get("/stats")
async def get_dashboard_stats(request: Request, website_id: Optional[str] = None):
    """Fetch live aggregated stats from Supabase filtered strictly by tenant account_id."""
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    if website_id in ("default-website-id", "all", "", "null", "undefined"):
        website_id = None

    try:
        q = supabase.table("content_log").select("id, title, keyword, status, created_at").eq("account_id", account_id)
        if website_id:
            q = q.eq("website_id", website_id)
        rows = q.order("created_at", desc=True).limit(10).execute().data or []

        all_q = supabase.table("content_log").select("id, status").eq("account_id", account_id)
        if website_id:
            all_q = all_q.eq("website_id", website_id)
        all_logs = all_q.execute().data or []

        m_q = supabase.table("brain_memory").select("id").eq("account_id", account_id)
        if website_id:
            m_q = m_q.eq("website_id", website_id)
        memories_count = len(m_q.execute().data or [])

        k_q = supabase.table("knowledge_base").select("id").eq("account_id", account_id)
        if website_id:
            k_q = k_q.eq("website_id", website_id)
        knowledge_count = len(k_q.execute().data or [])

        wp_q = supabase.table("websites").select("id, domain, status").eq("account_id", account_id)
        if website_id:
            wp_q = wp_q.eq("id", website_id)
        wp_rows = wp_q.execute().data or []
        wp_connected = any(w.get("status") == "active" for w in wp_rows)

        b_q = supabase.table("backlink_opportunities").select("id").eq("account_id", account_id)
        if website_id:
            b_q = b_q.eq("website_id", website_id)
        backlinks_count = len(b_q.execute().data or [])

        health_score = 94
        try:
            t_q = supabase.table("technical_audits").select("health_score").eq("account_id", account_id)
            if website_id:
                t_q = t_q.eq("website_id", website_id)
            audits = t_q.order("created_at", desc=True).limit(1).execute().data or []
            if audits and audits[0].get("health_score") is not None:
                health_score = round(float(audits[0]["health_score"]))
        except Exception:
            pass

        return {
            "total_articles": len(all_logs),
            "pending_articles": len([r for r in all_logs if r.get("status") in ("pending_approval", "draft")]),
            "health_score": health_score,
            "memories_count": memories_count,
            "knowledge_count": knowledge_count,
            "backlinks_count": backlinks_count,
            "wp_connected": wp_connected,
            "recent_blogs": rows,
            "ai_engine": "Llama-3.1-70B (NVIDIA NIM Live)",
        }
    except Exception as e:
        logger.error(f"Stats calculation error: {e}")
        return {
            "total_articles": 0,
            "pending_articles": 0,
            "health_score": 100,
            "memories_count": 0,
            "knowledge_count": 0,
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
# ROUTER REGISTRATION (WITH /api AND DIRECT ALIASES)
# ---------------------------------------------------------------------------

app.include_router(auth_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(websites, prefix="/api")
app.include_router(proposals, prefix="/api")
app.include_router(memory, prefix="/api")
app.include_router(llms_txt, prefix="/api")
app.include_router(gsc, prefix="/api")
app.include_router(tech_seo, prefix="/api")
app.include_router(backlinks, prefix="/api")
app.include_router(calendar, prefix="/api")
app.include_router(roi, prefix="/api")
app.include_router(seo_aeo_geo, prefix="/api")
app.include_router(monitoring_router, prefix="/api")
app.include_router(writer_router, prefix="/api")
app.include_router(decay_router, prefix="/api")
app.include_router(wordpress_router, prefix="/api")
app.include_router(wordpress_oauth_router, prefix="/api")
app.include_router(wordpress_connect_router, prefix="/api")
app.include_router(research_router, prefix="/api")
app.include_router(clusters_router, prefix="/api")
app.include_router(knowledge_router, prefix="/api")
app.include_router(content_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(connectors_router, prefix="/api")
app.include_router(connectors_serper_router, prefix="/api")
app.include_router(connectors_slack_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(brain_router, prefix="/api")
app.include_router(setup_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(workforce_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
app.include_router(autonomy_router, prefix="/api")
app.include_router(approvals_router, prefix="/api")
app.include_router(keywords_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(serp_router, prefix="/api")
app.include_router(report_router, prefix="/api")
app.include_router(links_router, prefix="/api")
app.include_router(phase3_router, prefix="/api")
app.include_router(oauth_connectors_router, prefix="/api")

# Direct Aliases
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(websites)
app.include_router(backlinks)
app.include_router(wordpress_router)
app.include_router(writer_router)
app.include_router(settings_router)
app.include_router(brain_router)
app.include_router(proposals)
app.include_router(content_router)
app.include_router(llms_txt)
app.include_router(workforce_router)
app.include_router(connectors_router)
app.include_router(autonomy_router)
app.include_router(approvals_router)


@app.get("/api/seo-agent-group/status")
@app.get("/seo-agent-group/status")
async def get_seo_agent_group_status():
    """Unified status endpoint for RankForge's Autonomous SEO Agent Group."""
    return await seo_agent_group.get_status_snapshot()
