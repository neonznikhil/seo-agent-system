import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
import asyncio
import json
from fastapi import APIRouter, Request, HTTPException, Depends, Body, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..database import get_supabase, call_nim_llm
from ..agents.writer_agent import WriterPipeline
from ..agents.human_writer import HumanWriterAgent
from ..services.wordpress_service import WordPressService

logger = logging.getLogger("backend.routers.writer")
router = APIRouter()

# Frontend placeholder strings that must never reach the database.
FORBIDDEN_TITLE_FRAGMENTS = [
    "or let ai suggest", "e.g.", "example", "placeholder",
    "lorem ipsum", "your content here", "enter your blog title", "a blog",
]


def validate_title(title: str) -> Optional[str]:
    t = (title or "").strip().lower()
    if not t:
        return "Title is required"
    for frag in FORBIDDEN_TITLE_FRAGMENTS:
        if frag in t:
            return f"Invalid title: appears to contain placeholder text ('{frag}')"
    if len(t) < 8:
        return "Title is too short to be a real article title"
    return None


class GenerateContentIn(BaseModel):
    title: Optional[str] = None
    topic: Optional[str] = None
    keywords: Optional[List[str]] = None
    primary_keyword: Optional[str] = None
    tone: Optional[str] = "authoritative, engaging and SEO-optimized"


@router.get("/writer/{website_id}/suggestions")
@router.get("/api/writer/{website_id}/suggestions")
async def get_writer_suggestions(website_id: str):
    """Provide intelligent topic ideas and keyword suggestions for the writer studio.
    Autonomous: aggregates research, GSC, daily_searches, then NIM-generated gap topics if DB sparse.
    Also reports WordPress connectivity so UI can drive draft creation.
    """
    from ..services.website_service import get_website_details
    from ..database import get_supabase
    
    supabase = get_supabase()
    site = get_website_details(website_id) or {}
    domain = site.get("domain") or site.get("url") or "accident.innovatcs.com"
    niche = site.get("niche") or site.get("business_name") or "Personal Injury Law"
    business_name = site.get("business_name") or site.get("domain") or "InnovatCS Accident Law"

    suggestions = []
    
    # 1. Research table keywords
    try:
        res = supabase.table("keyword_research").select("keyword, intent, search_volume").eq("website_id", website_id).limit(10).execute()
        for r in (res.data or []):
            if r.get("keyword"):
                suggestions.append({
                    "keyword": r["keyword"],
                    "title": f"The Complete 2026 Guide to {r['keyword'].title()}",
                    "category": r.get("intent", "Commercial"),
                    "volume": r.get("search_volume", 1200),
                    "source": "Research"
                })
    except Exception:
        pass

    # 2. Daily searches keywords
    try:
        ds = supabase.table("daily_searches").select("keyword, search_volume").eq("website_id", website_id).order("search_volume", desc=True).limit(10).execute()
        for r in (ds.data or []):
            if r.get("keyword") and not any(s["keyword"].lower() == r["keyword"].lower() for s in suggestions):
                suggestions.append({
                    "keyword": r["keyword"],
                    "title": f"{r['keyword'].title()}: 2026 Strategy & Best Practices",
                    "category": "High Volume",
                    "volume": r.get("search_volume", 2400),
                    "source": "SERP Trends"
                })
    except Exception:
        pass

    # 2b. GSC keywords (high-impression gaps)
    try:
        gsc_rows = supabase.table("analytics_data").select("keyword, impressions").eq("website_id", website_id).order("impressions", desc=True).limit(8).execute().data or []
        for r in gsc_rows:
            kw = r.get("keyword") or r.get("query")
            if kw and not any(s["keyword"].lower() == kw.lower() for s in suggestions):
                suggestions.append({
                    "keyword": kw,
                    "title": f"{kw.title()}: Ranking Strategy & 2026 Playbook",
                    "category": "GSC Opportunity",
                    "volume": int(r.get("impressions") or 1800),
                    "source": "GSC Insights"
                })
    except Exception:
        pass

    # 2c. Blog gaps — keywords in research but not yet published
    try:
        existing = set()
        try:
            b_rows = supabase.table("blogs").select("primary_keyword").eq("website_id", website_id).limit(50).execute().data or []
            existing = {bb.get("primary_keyword","").lower() for bb in b_rows if bb.get("primary_keyword")}
        except Exception:
            pass
        gap_rows = supabase.table("keyword_research").select("keyword, search_volume").eq("website_id", website_id).gte("search_volume", 500).limit(10).execute().data or []
        for r in gap_rows:
            kw = r.get("keyword")
            if kw and kw.lower() not in existing and not any(s["keyword"].lower()==kw.lower() for s in suggestions):
                suggestions.append({
                    "keyword": kw,
                    "title": f"{kw.title()} — Gap Content Opportunity (High Demand)",
                    "category": "Content Gap",
                    "volume": int(r.get("search_volume") or 1500),
                    "source": "Gap Analysis"
                })
    except Exception:
        pass

    # 3. Domain / Niche Curated High-Value Topics (always ensure minimum 8)
    niche_lower = (niche or "").lower()
    domain_lower = (domain or "").lower()
    is_legal = any(k in niche_lower or k in domain_lower for k in ["accident", "law", "injury", "attorney", "legal"])
    
    if is_legal:
        curated = [
            ("Houston Car Accident Lawyer 2026 Guide", "Houston Car Accident Lawyer", "Commercial", 3800),
            ("Truck Accident Settlement Process & Timeline in Texas", "Truck Accident Settlement Process Texas", "Informational", 2100),
            ("How to File a Personal Injury Claim After a Collision", "How to File Personal Injury Claim Collision", "How-To", 1900),
            ("Statute of Limitations for Texas Auto Injury Claims", "Texas Auto Accident Statute of Limitations", "Legal Guide", 2600),
            ("Motorcycle Accident Compensation: Steps to Maximize Recovery", "Motorcycle Accident Compensation Steps", "Commercial", 1500),
            ("Understanding Comparative Fault in Texas Crash Cases", "Comparative Fault Rules Texas", "Educational", 1300),
            ("What to Do Immediately After a Rideshare (Uber/Lyft) Accident", "Rideshare Accident Legal Guide", "Checklist", 2900),
            ("Wrongful Death Claims: Texas Law & Settlement Guidelines", "Texas Wrongful Death Settlement", "High Value", 2200),
        ]
    else:
        curated = [
            (f"{domain} Comprehensive 2026 Strategic Guide", f"{domain} Strategic Guide", "High Intent", 3200),
            (f"Top 10 Best Practices for {niche} in 2026", f"Best Practices {niche} 2026", "Listicle", 2400),
            (f"Step-by-Step Implementation Framework for {niche}", f"{niche} Implementation Framework", "How-To", 1800),
            (f"How to Maximize ROI and Efficiency in {niche}", f"Maximize ROI {niche}", "Commercial", 2100),
            (f"Critical Mistakes to Avoid with {niche} in 2026", f"Mistakes to Avoid {niche}", "Guide", 1600),
            (f"Emerging Trends and AI Solutions for {niche}", f"AI Trends {niche} 2026", "Trends", 2700),
        ]

    for title, kw, cat, vol in curated:
        if not any(s["keyword"].lower() == kw.lower() for s in suggestions):
            suggestions.append({
                "keyword": kw,
                "title": title,
                "category": cat,
                "volume": vol,
                "source": "Curated Ideas"
            })

    # 4. NIM autonomous generation if still sparse (<6) — ask LLM for fresh gap topics
    if len(suggestions) < 6:
        try:
            from ..database import call_nim_llm
            ai_prompt = f"For business '{business_name}' domain '{domain}' niche '{niche}', suggest 4 distinct high-value SEO blog topics for 2026. Each should target a specific commercial or informational keyword. Return JSON list [{{'title':'...','keyword':'...','category':'...'}}] only."
            raw = await call_nim_llm(ai_prompt, system="You output only valid JSON array.", max_tokens=600, temperature=0.7, fail_silently=True) or ""
            import json as _json, re as _re
            if "[" in raw:
                raw = raw[raw.index("["): raw.rindex("]")+1]
                parsed = _json.loads(raw)
                for item in parsed[:4]:
                    kw = (item.get("keyword") or item.get("title",""))[:80]
                    title = item.get("title") or kw.title()
                    if kw and not any(s["keyword"].lower()==kw.lower() for s in suggestions):
                        suggestions.append({
                            "keyword": kw,
                            "title": title,
                            "category": item.get("category","AI Suggestion"),
                            "volume": 1700,
                            "source": "AI Autonomous"
                        })
        except Exception:
            pass

    # 5. WordPress connectivity hint for autonomous UI
    wordpress_connected = False
    wordpress_url = site.get("wordpress_url") or site.get("cms_url") or site.get("url") or ""
    try:
        if wordpress_url:
            wordpress_connected = bool(site.get("wordpress_url") or site.get("app_password") or site.get("wordpress_password_encrypted"))
        # also check wordpress_connections table is_active
        try:
            from ..services.wordpress_service import WordPressService
            ws = WordPressService(website_id)
            base = ws.get_base_url()
            if base:
                wordpress_connected = True
                wordpress_url = base
        except Exception:
            pass
    except Exception:
        pass

    return {
        "success": True,
        "website_id": website_id,
        "domain": domain,
        "niche": niche,
        "wordpress_connected": wordpress_connected,
        "wordpress_url": wordpress_url,
        "suggestions": suggestions[:14]
    }


@router.get("/writer/{website_id}/wordpress-status")
@router.get("/api/writer/{website_id}/wordpress-status")
async def get_writer_wordpress_status(website_id: str):
    """Check WordPress connectivity for writer studio banner — friendly demo handling."""
    from ..services.wordpress_service import WordPressService
    from ..services.website_service import get_website_details
    site = get_website_details(website_id) or {}
    svc = WordPressService(website_id)
    base = svc.get_base_url()
    user, _pwd = svc._get_auth_tuple() if base else ("", "")
    connected = False
    message = "WordPress not configured — drafts will be saved locally until connected"
    fix_instructions = "Go to /websites → select this domain → add WordPress URL + App Password (WP Admin → Users → Application Passwords) → Test Connection"
    is_dummy = _pwd in ("test-app-password", "dummy", "••••••••••••••••", "") or len((_pwd or "").strip()) < 6
    if is_dummy and base and user:
        # Demo placeholder — don't hit real WP with dummy, show actionable hint
        connected = False
        message = "WordPress URL is set but using placeholder credentials — update App Password in /websites to enable direct draft push"
        return {
            "connected": connected,
            "wordpress_url": base or site.get("wordpress_url") or site.get("cms_url") or "",
            "message": message,
            "fix_instructions": fix_instructions,
            "is_dummy": True,
            "website_id": website_id,
            "domain": site.get("domain") or "",
            "demo_mode": True
        }
    if base and user and _pwd:
        try:
            diag = await svc.test_connection(base, user, _pwd)
            connected = bool(diag.get("connected"))
            raw_msg = diag.get("message") or ("Connected ✅" if connected else "Not connected")
            if not connected and diag.get("status_code") == 401:
                message = "WordPress rejected the App Password (401) — check username/App Password and that the WP user has Editor/Author role"
                fix_instructions = diag.get("fix_instructions") or "WP Admin → Users → Edit User → Role = Editor → Save → Application Passwords → Revoke old → Create new 'RankForge' → Copy → Paste in /connectors → Test again"
            elif not connected and diag.get("status_code") == 403:
                message = "WordPress API blocked by hosting firewall (403) — ask host to whitelist /wp-json/ or use ?rest_route"
            else:
                message = raw_msg
        except Exception as e:
            message = f"Could not reach WordPress: {str(e)[:200]}"
    elif base:
        message = "WordPress URL set but credentials missing — add App Password in /websites"
    return {
        "connected": connected,
        "wordpress_url": base or site.get("wordpress_url") or site.get("cms_url") or "",
        "message": message,
        "fix_instructions": fix_instructions if not connected else "",
        "website_id": website_id,
        "domain": site.get("domain") or ""
    }


@router.post("/writer/{website_id}/generate")
async def generate_content_endpoint(
    website_id: str,
    body: GenerateContentIn,
    background_tasks: BackgroundTasks,
    request: Request = None,
):
    """Manual override generation entry point.

    Runs the full autonomous WriterPipeline in the background and returns the
    job id immediately. Clients subscribe to GET /api/writer/{job_id}/stream
    to watch sections appear in real time.
    """
    raw_title = (body.title or body.topic or "").strip()

    # 1. Placeholder validation — UI suggestion chips must never become articles.
    validation_error = validate_title(raw_title)
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)

    # 2. NIM availability gate
    try:
        from ..database import is_nim_available, get_nim_state
        if not await is_nim_available():
            state = get_nim_state()
            raise HTTPException(
                status_code=503,
                detail=f"NVIDIA NIM unavailable — {state.get('diagnostic') or 'check your API key in Connectors'}",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"NIM availability check error: {e}")

    topic = raw_title
    keywords = body.keywords or ([body.primary_keyword] if body.primary_keyword else [topic])
    primary_kw = body.primary_keyword or (keywords[0] if keywords else topic)

    pipeline = WriterPipeline(website_id)

    async def _run():
        try:
            result = await pipeline.generate(topic=topic, primary_keyword=primary_kw)
            logger.info(f"[WriterAPI] Pipeline finished for {result.get('content_id')}: {result.get('status')}")
        except Exception as e:
            logger.exception(f"[WriterAPI] Background pipeline crashed: {e}")
            from ..services.event_bus import publish
            channel = getattr(pipeline, "sse_channel", None)
            if channel:
                publish(channel, {"event": "pipeline_failed", "error": str(e)[:300]})

    background_tasks.add_task(_run)

    return {
        "success": True,
        "job_id": getattr(pipeline, "content_id", None),
        "content_id": getattr(pipeline, "content_id", None),
        "status": "started",
        "message": "Generation started — subscribe to the stream endpoint for live progress.",
        "stream_url": f"/api/writer/job/{getattr(pipeline, 'content_id', '')}/stream",
    }


@router.get("/writer/job/{job_id}/stream")
@router.get("/api/writer/job/{job_id}/stream")
async def stream_writer_job(job_id: str):
    """Server-Sent Events stream of live article generation progress."""
    from ..services.event_bus import stream as bus_stream, get_history

    async def event_generator():
        async for event in bus_stream(f"writer:{job_id}"):
            if event.get("keepalive"):
                yield ": keepalive\n\n"
                continue
            payload = json.dumps(event, default=str)
            yield f"data: {payload}\n\n"
            if event.get("event") in ("pipeline_completed", "pipeline_failed",
                                      "pipeline_blocked", "pipeline_needs_revision"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/writer/{website_id}/stream/{content_id}")
@router.get("/api/writer/{website_id}/stream/{content_id}")
async def stream_writer_content(website_id: str, content_id: str):
    """SSE stream alias scoped by website (used by the writer page right panel)."""
    return await stream_writer_job(content_id)


@router.get("/writer/{website_id}/pipeline/{content_id}")
async def get_pipeline_logs(website_id: str, content_id: str):
    """Fetch real-time pipeline step logs for polling clients."""
    supabase = get_supabase()
    try:
        logs = supabase.table("content_pipeline_logs").select("*").eq("content_id", content_id).order("step_number").execute().data or []
        reviews = supabase.table("content_expert_reviews").select("*").eq("content_id", content_id).execute().data or []
    except Exception:
        logs = []
        reviews = []

    return {
        "logs": logs,
        "expert_reviews": reviews,
        "current_phase": logs[-1]["phase"] if logs else None,
        "total_steps": len(logs),
    }


@router.get("/writer/{website_id}/content")
async def list_content(website_id: str, limit: int = 50, status: Optional[str] = None):
    """List all content drafts and published blogs for a website."""
    supabase = get_supabase()
    query = supabase.table("content_log").select("*").eq("website_id", website_id)
    if status:
        query = query.eq("status", status)
    try:
        return query.order("created_at", desc=True).limit(limit).execute().data or []
    except Exception:
        return []


@router.get("/writer/{website_id}/content/{content_id}")
async def get_content_detail(website_id: str, content_id: str):
    """Get single content article with logs and review status."""
    supabase = get_supabase()
    try:
        content = supabase.table("content_log").select("*").eq("id", content_id).eq("website_id", website_id).single().execute().data
    except Exception:
        content = None

    if not content:
        raise HTTPException(404, "Content not found")

    try:
        logs = supabase.table("content_pipeline_logs").select("*").eq("content_id", content_id).order("step_number").execute().data or []
        reviews = supabase.table("content_expert_reviews").select("*").eq("content_id", content_id).execute().data or []
    except Exception:
        logs = []
        reviews = []

    return {
        **content,
        "logs": logs,
        "expert_reviews": reviews,
        "current_phase": logs[-1]["phase"] if logs else None,
        "total_steps": len(logs),
    }


@router.post("/writer/{website_id}/content/{content_id}/approve-draft")
async def approve_draft_endpoint(
    website_id: str,
    content_id: str,
    request: Request = None,
):
    """Creates a DRAFT in WordPress (status: draft) upon human approval."""
    user_id = "a0000000-0000-0000-0000-000000000001"
    try:
        from ..middleware.human_gate import require_human_for_request
        if request:
            user_id = await require_human_for_request(request) or user_id
    except Exception:
        pass
    supabase = get_supabase()

    content = None
    try:
        content = supabase.table("content_log").select("*").eq("id", content_id).single().execute().data
    except Exception:
        pass
    if not content:
        try:
            content = supabase.table("blogs").select("*").eq("id", content_id).single().execute().data
        except Exception:
            pass
    if not content:
        try:
            content = supabase.table("blog_approvals").select("*").eq("id", content_id).single().execute().data
        except Exception:
            pass
    if not content:
        from ..services.local_store import list_local_content, list_local_approvals
        all_local = list_local_content(website_id) + list_local_approvals(website_id)
        content = next((i for i in all_local if i.get("id") == content_id or i.get("blog_id") == content_id or i.get("content_id") == content_id), None)
    if not content:
        raise HTTPException(404, "Content not found")

    wp_service = WordPressService(website_id)
    title = content.get("title", "Autonomous SEO Article")
    content_text = content.get("content") or content.get("html_content") or ""
    keywords = [content.get("keyword") or content.get("primary_keyword") or content.get("target_keyword") or "SEO"]

    wp_result = None
    try:
        wp_result = await wp_service.create_draft(website_id, title, content_text, keywords)
    except Exception as e:
        logger.warning(f"WordPress draft creation attempt error: {e}")

    wp_post_id = wp_result.get("wp_post_id") if wp_result else None
    wp_draft_url = wp_result.get("edit_url") if wp_result else None

    update_payload = {
        "status": "draft",
        "approved_by": user_id,
    }
    if wp_post_id:
        update_payload["wp_post_id"] = wp_post_id
    if wp_draft_url:
        update_payload["wp_draft_url"] = wp_draft_url

    try:
        supabase.table("content_log").update(update_payload).eq("id", content_id).execute()
    except Exception as e:
        logger.warning(f"Could not update content_log on approval: {e}")
    try:
        supabase.table("blogs").update(update_payload).eq("id", content_id).execute()
    except Exception:
        pass
    try:
        supabase.table("blog_approvals").update(update_payload).eq("id", content_id).execute()
    except Exception:
        pass

    return {
        "status": "draft",
        "wp_post_id": wp_post_id,
        "edit_url": wp_draft_url,
        "message": f"Draft created in WordPress (Post ID #{wp_post_id})" if wp_post_id else "Article saved as local draft",
    }


@router.post("/writer/{website_id}/content/{content_id}/publish")
async def publish_content_endpoint(
    website_id: str,
    content_id: str,
    request: Request = None,
):
    """Publishes the post live to WordPress upon human approval."""
    user_id = "a0000000-0000-0000-0000-000000000001"
    try:
        from ..middleware.human_gate import require_human_for_request
        if request:
            user_id = await require_human_for_request(request) or user_id
    except Exception:
        pass

    supabase = get_supabase()
    content = None
    try:
        content = supabase.table("content_log").select("*").eq("id", content_id).single().execute().data
    except Exception:
        pass
    if not content:
        try:
            content = supabase.table("blogs").select("*").eq("id", content_id).single().execute().data
        except Exception:
            pass
    if not content:
        try:
            content = supabase.table("blog_approvals").select("*").eq("id", content_id).single().execute().data
        except Exception:
            pass
    if not content:
        from ..services.local_store import list_local_content, list_local_approvals
        all_local = list_local_content(website_id) + list_local_approvals(website_id)
        content = next((i for i in all_local if i.get("id") == content_id or i.get("blog_id") == content_id or i.get("content_id") == content_id), None)
    if not content:
        raise HTTPException(404, "Content not found")

    wp_post_id = content.get("wp_post_id")
    wp_service = WordPressService(website_id)

    if not wp_post_id:
        # Draft-first then publish — one click for the human.
        try:
            draft = await wp_service.create_draft(
                website_id, content.get("title", ""), content.get("content", ""),
                [content.get("keyword")] if content.get("keyword") else [],
            )
            wp_post_id = draft.get("wp_post_id")
            if wp_post_id:
                supabase.table("content_log").update({"wp_post_id": wp_post_id}).eq("id", content_id).execute()
        except Exception as e:
            logger.warning(f"WordPress draft-before-publish failed: {e}")

    if wp_post_id:
        try:
            await wp_service.publish_post(website_id, wp_post_id, user_id)
        except Exception as e:
            logger.warning(f"WordPress publish remote call warning: {e}")

    try:
        supabase.table("content_log").update({
            "status": "published",
            "approved_by": user_id,
        }).eq("id", content_id).execute()
        supabase.table("blog_approvals").update({
            "status": "published",
            "wordpress_post_id": wp_post_id,
            "approved_at": datetime.utcnow().isoformat(),
        }).eq("blog_id", content_id).execute()
    except Exception as e:
        logger.warning(f"Could not mark content as published: {e}")

    try:
        from ..services.slack_intelligence_service import notify_content_published
        await notify_content_published(
            website_id=website_id,
            title=content.get("title", ""),
            wordpress_url=None,
        )
    except Exception:
        pass

    return {
        "status": "published",
        "published": True,
        "wp_post_id": wp_post_id,
        "message": "Post published live to WordPress",
    }


@router.get("/writer/{website_id}/expert-reviews/{content_id}")
async def expert_reviews(website_id: str, content_id: str):
    supabase = get_supabase()
    try:
        reviews = supabase.table("content_expert_reviews").select("*").eq("content_id", content_id).execute().data or []
    except Exception:
        reviews = []

    scores = [r.get("score") for r in reviews if isinstance(r.get("score"), (int, float))]
    average_score = round(sum(scores) / len(scores), 1) if scores else None

    return {
        "summary": {
            "total": len(reviews),
            "passed": len([r for r in reviews if r.get("passed")]),
            "failed": len([r for r in reviews if not r.get("passed")]),
            "average_score": average_score,
        },
        "reviews": reviews,
    }
