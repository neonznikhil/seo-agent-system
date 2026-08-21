import asyncio
import logging
import traceback
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import validate_env, REDIS_URL, ALLOWED_CORS_ORIGINS
from .database import get_supabase, NIM_API_KEY
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
from .services.continuous_monitor import start_all_monitors
from .agents.brain_autopilot_agent import run_daily_autopilot
from .agents.backlink_autopilot_agent import run_backlink_daily_jobs
from .routers.setup import router as setup_router
from .api_web_browsing import router as web_browsing_router

validate_env()

logger = logging.getLogger("backend.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[Startup] Starting all monitoring loops...")
    try:
        start_all_monitors()
        logger.info("[Startup] All monitors initialized")
    except Exception as e:
        logger.error(f"[Startup] Monitor init failed (non-fatal): {e}")
    try:
        asyncio.create_task(run_daily_autopilot())
        logger.info("[Startup] Brain autopilot loop started")
    except Exception as e:
        logger.error(f"[Startup] Brain autopilot init failed (non-fatal): {e}")
    try:
        asyncio.create_task(run_backlink_daily_jobs())
        logger.info("[Startup] Backlink autopilot loop started")
    except Exception as e:
        logger.error(f"[Startup] Backlink autopilot init failed (non-fatal): {e}")
    yield
    logger.info("[Shutdown] Shutting down")


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
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
async def health():
    import os
    checks = {}
    degraded_reasons = []

    # SUPABASE_URL check - exact reason
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

    # NVIDIA_API_KEY check - exact reason
    if not os.getenv("NVIDIA_API_KEY"):
        checks["nim"] = "missing: NVIDIA_API_KEY not set"
        degraded_reasons.append("NVIDIA_API_KEY missing")
    else:
        checks["nim"] = "configured"

    # Redis check - exact reason
    if not os.getenv("REDIS_URL") or os.getenv("REDIS_URL") == "redis://localhost:6379/0":
        checks["redis"] = "missing: Redis not configured (default localhost)"
        degraded_reasons.append("Redis missing")
    else:
        try:
            import redis
            r = redis.from_url(REDIS_URL)
            r.ping()
            checks["redis"] = "ok"
            r.close()
        except Exception as e:
            checks["redis"] = f"error: {e}"
            degraded_reasons.append(f"redis error: {e}")

    status = "ok" if not degraded_reasons else "degraded"
    return {
        "status": status,
        "checks": checks,
        "degraded_reasons": degraded_reasons if degraded_reasons else None
    }


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
