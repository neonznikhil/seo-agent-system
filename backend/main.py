import asyncio
import logging
import traceback
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from pathlib import Path

from .config import validate_env, REDIS_URL, ALLOWED_CORS_ORIGINS
from .database import get_supabase
from .routers import websites, proposals, memory, llms_txt, gsc, tech_seo, backlinks, calendar, roi, seo_aeo_geo
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
from .routers.brain import router as brain_router
from .routers.autonomy import router as autonomy_router
from .routers.approvals import router as approvals_router
from .services.continuous_monitor import start_all_monitors  # noqa: F401 (kept for manual runs)
from .agents.backlink_autopilot_agent import run_backlink_daily_jobs
from .routers.setup import router as setup_router
from .api_web_browsing import router as web_browsing_router
from .routers.chat import router as chat_router
from .routers.workforce import router as workforce_router

validate_env()

logger = logging.getLogger("backend.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("RANKFORGE starting up...")
    
    # Single scheduling authority: agents/scheduler.py (Asia/Kolkata)
    # 09:00 research | 10:00 refresh | 10:30 auto-publish | hourly monitors
    # plus a boot catch-up for any stale daily job.
    try:
        from .agents.scheduler import setup_scheduler
        sched = setup_scheduler()
        if not sched.running:
            sched.start()
        logger.info("[Scheduler] Started ✅ (Asia/Kolkata)")
    except Exception as e:
        logger.error(f"[Scheduler] Failed to start: {e}")

    # Backlink autopilot keeps its own independent daily cadence.
    try:
        asyncio.create_task(run_backlink_daily_jobs())
        logger.info("[Startup] Backlink autopilot loop started ✅")
    except Exception as e:
        logger.error(f"[Startup] Backlink autopilot init failed (non-fatal): {e}")
    
    yield
    
    # Shutdown
    logger.info("RANKFORGE shutting down...")
    try:
        from .agents.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass


app = FastAPI(title="RankForge API", lifespan=lifespan)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)
        logger.info(
            f"{request.method} {request.url.path} {response.status_code} {process_time:.3f}s [{request_id}]"
        )
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(
            f"{request.method} {request.url.path} 500 {process_time:.3f}s [{request_id}] {str(e)}"
        )
        raise


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "https://*.cloudworkstations.dev", "https://*.app.github.dev", "*"],
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


@app.get("/health")
@app.get("/api/health")
async def health():
    import os
    checks = {}
    degraded_reasons = []

    # SUPABASE_URL check
    if not os.getenv("SUPABASE_URL"):
        checks["supabase"] = "missing: SUPABASE_URL not set"
        degraded_reasons.append("SUPABASE_URL missing")
    else:
        try:
            get_supabase().table("websites").select("id").limit(1).execute()
            checks["supabase"] = "ok"
        except Exception as e:
            checks["supabase"] = f"error: {e}"
            degraded_reasons.append(f"supabase error: {e}")

    # NVIDIA_API_KEY check
    if not os.getenv("NVIDIA_API_KEY"):
        checks["nim"] = "missing: NVIDIA_API_KEY not set"
        degraded_reasons.append("NVIDIA_API_KEY missing")
    else:
        checks["nim"] = "configured"

    # Redis check
    if not os.getenv("REDIS_URL") or os.getenv("REDIS_URL") == "redis://localhost:6379/0":
        checks["redis"] = "missing: Redis not configured (default localhost)"
    else:
        try:
            import redis
            r = redis.from_url(REDIS_URL)
            r.ping()
            checks["redis"] = "ok"
            r.close()
        except Exception as e:
            checks["redis"] = f"error: {e}"

    # WordPress check
    try:
        conn = get_supabase().table("wordpress_connections").select("*").limit(1).execute().data
        checks["wordpress"] = "connected" if conn else "not_configured"
    except Exception:
        checks["wordpress"] = "table_check_failed"

    status = "ok" if checks.get("supabase") == "ok" else "degraded"
    return {
        "status": status,
        "checks": checks,
        "degraded_reasons": degraded_reasons if degraded_reasons else None
    }


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
            "ui_url": "http://localhost:8000/"
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
async def generate_blog_nim(payload: GenerateBlogPayload):
    """Generate a real SEO-optimized blog post using NVIDIA NIM Llama 3.1 70B and save to Supabase."""
    from .database import call_nim_llm, get_supabase
    
    topic = payload.topic.strip()
    keyword = (payload.primary_keyword or topic).strip()
    
    # 1. Resolve active website
    website_id = payload.website_id
    supabase = get_supabase()
    if not website_id:
        try:
            sites = supabase.table("websites").select("id").limit(1).execute().data
            if sites:
                website_id = sites[0]["id"]
        except Exception as e:
            logger.warning(f"Could not fetch website id: {e}")

    # 2. Call NVIDIA NIM LLM
    system_prompt = (
        "You are RankForge's Autonomous SEO Content Writer. Write high-ranking, comprehensive, "
        "well-structured articles with clear H2 and H3 sections, actionable bullet points, "
        "and direct answers to user search intent. Avoid generic filler AI buzzwords (delve, elevate, revolutionize, tapestry)."
    )
    user_prompt = (
        f"Write an in-depth, production-ready SEO blog post.\n"
        f"Topic: {topic}\n"
        f"Primary Keyword: {keyword}\n"
        f"Tone: {payload.tone}\n\n"
        f"Structure required:\n"
        f"1. Title (compelling, click-worthy H1 format)\n"
        f"2. Direct answer/Executive summary in the first 100 words\n"
        f"3. 4-5 Detailed H2 sections explaining core concepts, strategy, and step-by-step implementation\n"
        f"4. A structured comparison table or key takeaways list\n"
        f"5. Actionable FAQ section (3 questions and concise answers)\n"
        f"6. Conclusion\n\n"
        f"Return the entire article in Markdown format."
    )

    try:
        content = await call_nim_llm(prompt=user_prompt, system=system_prompt, website_id=website_id)
    except Exception as e:
        logger.error(f"NIM generation failed: {e}")
        raise HTTPException(500, f"NVIDIA NIM Generation failed: {str(e)}")

    # Extract title
    title = topic
    lines = [line.strip() for line in content.split("\n") if line.strip()]
    for line in lines[:5]:
        if line.startswith("# "):
            title = line.replace("# ", "").strip()
            break
        elif line.startswith("Title:"):
            title = line.replace("Title:", "").strip()
            break

    # 3. Save to Supabase content_log
    saved_row = None
    try:
        insert_data = {
            "title": title,
            "content": content,
            "keyword": keyword,
            "status": "pending_approval",
            "use_case": "blog_post",
        }
        if website_id:
            insert_data["website_id"] = website_id

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
async def get_dashboard_stats(website_id: Optional[str] = None):
    """Fetch live aggregated stats from Supabase for the frontend dashboard."""
    from .database import get_supabase
    
    supabase = get_supabase()
    
    # Ignore placeholder IDs
    if website_id in ("default-website-id", "all", "", "null", "undefined"):
        website_id = None
    
    # 1. Total Articles & Pending
    total_articles = 0
    pending_articles = 0
    recent_blogs = []
    try:
        q = supabase.table("content_log").select("id, title, keyword, status, created_at")
        if website_id:
            q = q.eq("website_id", website_id)
        rows = q.order("created_at", desc=True).limit(10).execute().data or []
        recent_blogs = rows
        
        # Counts
        all_q = supabase.table("content_log").select("id, status")
        if website_id:
            all_q = all_q.eq("website_id", website_id)
        all_logs = all_q.execute().data or []
        total_articles = len(all_logs)
        pending_articles = len([r for r in all_logs if r.get("status") in ("pending_approval", "draft")])
    except Exception as e:
        logger.warning(f"Stats content_log query error: {e}")

    # 2. Memories Count
    memories_count = 0
    try:
        m_q = supabase.table("brain_memory").select("id")
        if website_id:
            m_q = m_q.eq("website_id", website_id)
        memories = m_q.execute().data or []
        memories_count = len(memories)
    except Exception:
        pass
    except Exception:
        pass

    # 3. Knowledge Items Count
    knowledge_count = 0
    try:
        k_q = supabase.table("knowledge_base").select("id")
        if website_id:
            k_q = k_q.eq("website_id", website_id)
        knowledge = k_q.execute().data or []
        knowledge_count = len(knowledge)
    except Exception:
        pass

    # 4. WordPress Connected
    wp_connected = False
    try:
        wp_rows = supabase.table("wordpress_connections").select("id, site_url").execute().data or []
        wp_connected = len(wp_rows) > 0
    except Exception:
        pass

    # 5. Backlinks Monitored
    backlinks_count = 0
    try:
        bl_rows = supabase.table("backlink_monitor").select("id").execute().data or []
        backlinks_count = len(bl_rows)
    except Exception:
        pass

    # 6. Real Health Score from technical audits
    health_score = None
    try:
        t_q = supabase.table("technical_audits").select("health_score")
        if website_id:
            t_q = t_q.eq("website_id", website_id)
        audits = t_q.order("created_at", desc=True).limit(1).execute().data or []
        if audits and audits[0].get("health_score") is not None:
            health_score = round(float(audits[0]["health_score"]))
    except Exception:
        pass

    return {
        "total_articles": total_articles,
        "pending_articles": pending_articles,
        "health_score": health_score,
        "memories_count": memories_count,
        "knowledge_count": knowledge_count,
        "backlinks_count": backlinks_count,
        "wp_connected": wp_connected,
        "recent_blogs": recent_blogs,
        "ai_engine": "Llama-3.1-70B (NVIDIA NIM Live)",
        "active_agents": [
            {"name": "writer_agent", "role": "10-phase autonomous writer & SERP analyzer", "status": "Ready"},
            {"name": "brain_autopilot", "role": "Daily clustering, pattern learning, and decay monitoring", "status": "Running"},
            {"name": "backlink_autopilot", "role": "Continuous backlink verification and prospect crawler", "status": "Running"},
            {"name": "continuous_monitor", "role": "Real-time rank movement, SERP shifts, and tech SEO audits", "status": "Running"},
        ]
    }


@app.get("/api/blogs")
async def get_blogs(limit: int = 50, website_id: Optional[str] = None):
    """Fetch blog drafts and published articles from Supabase."""
    from .database import get_supabase
    
    q = get_supabase().table("content_log").select("*")
    if website_id:
        q = q.eq("website_id", website_id)
    return q.order("created_at", desc=True).limit(limit).execute().data or []


# Mount all routers with /api prefix
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
app.include_router(brain_router, prefix="/api")
app.include_router(setup_router, prefix="/api")
app.include_router(web_browsing_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(workforce_router, prefix="/api")
app.include_router(autonomy_router, prefix="")
app.include_router(approvals_router, prefix="")

# Also mount on root without prefix for direct fetch compatibility
app.include_router(websites)
app.include_router(gsc)
app.include_router(tech_seo)
app.include_router(wordpress_router)
app.include_router(writer_router)
app.include_router(settings_router)
app.include_router(brain_router)
app.include_router(proposals)
app.include_router(content_router)
app.include_router(llms_txt)
app.include_router(workforce_router)
app.include_router(connectors_router)


