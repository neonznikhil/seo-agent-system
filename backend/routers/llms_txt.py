import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Response, Request
from fastapi.responses import PlainTextResponse

from database import get_supabase
from services.website_service import get_default_website_id, get_website_details
from services.local_store import (
    list_local_websites,
    get_local_website,
    list_local_knowledge,
    list_local_content,
    list_local_approvals
)

logger = logging.getLogger("backend.routers.llms_txt")
router = APIRouter(tags=["llms"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_PUBLIC_LLMS = PROJECT_ROOT / "frontend-next" / "public" / "llms.txt"
FRONTEND_PUBLIC_LLMS_FULL = PROJECT_ROOT / "frontend-next" / "public" / "llms-full.txt"
BACKEND_STATIC_LLMS = PROJECT_ROOT / "backend" / "static" / "llms.txt"


def _resolve_site(website_id: Optional[str] = None, user_id: Optional[str] = None, request: Optional[Request] = None) -> dict:
    """Resolve site identity strictly from the database using website_id, user_id from headers, or active site."""
    supabase = get_supabase()

    if request:
        if not user_id:
            user_id = request.headers.get("X-User-Id") or getattr(request.state, "user_id", None)
        if not website_id:
            website_id = request.headers.get("X-Website-Id")

    wid = website_id if website_id and website_id not in ("default", "default-website-id", "all", "", "null", "undefined") else None
    
    # 0. Check website_service / local_store first
    if wid:
        details = get_website_details(wid) or get_local_website(wid)
        if details and (details.get("domain") or details.get("url") or details.get("cms_url")):
            return details

    try:
        if wid:
            res = supabase.table("websites").select("*").eq("id", wid).limit(1).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
        
        # 1. Look up by user_id if provided
        if user_id:
            res_user = supabase.table("websites").select("*").eq("user_id", user_id).eq("status", "active").order("created_at", desc=True).limit(1).execute()
            if res_user.data and len(res_user.data) > 0:
                return res_user.data[0]
            # Try without status filter
            res_user_any = supabase.table("websites").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
            if res_user_any.data and len(res_user_any.data) > 0:
                return res_user_any.data[0]

        # 2. Look up any active website
        res_active = supabase.table("websites").select("*").eq("status", "active").order("created_at", desc=True).limit(1).execute()
        if res_active.data and len(res_active.data) > 0:
            return res_active.data[0]

        # 3. Fallback to default registered website
        def_id = get_default_website_id()
        if def_id:
            details = get_website_details(def_id) or get_local_website(def_id)
            if details and (details.get("domain") or details.get("url") or details.get("cms_url")):
                return details
            res = supabase.table("websites").select("*").eq("id", def_id).limit(1).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]

        # 4. Fallback to any registered website
        res = supabase.table("websites").select("*").order("created_at", desc=True).limit(1).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
    except Exception as e:
        logger.warning(f"[LLMsTxt] Error resolving site: {e}")
    
    # 5. Local store fallback
    local_list = list_local_websites()
    if local_list and len(local_list) > 0:
        return local_list[0]
    
    return {}


async def generate_llms_txt_content(website_id: Optional[str] = None, user_id: Optional[str] = None, request: Optional[Request] = None) -> str:
    """Build llms.txt from live website record, knowledge base facts, and published articles."""
    supabase = get_supabase()
    site = _resolve_site(website_id=website_id, user_id=user_id, request=request)
    resolved_id = site.get("id") or website_id
    wid = resolved_id if resolved_id and resolved_id not in ("default", "default-website-id", "all", "", "null", "undefined") else None

    site_url = site.get("domain") or site.get("url") or site.get("cms_url") or ""
    clean_domain = site_url.replace("https://", "").replace("http://", "").split("/")[0]
    site_niche = site.get("niche") or "Personal Injury Legal Services"

    if not clean_domain:
        raise HTTPException(
            status_code=400,
            detail="No connected website found. Connect a website first to generate LLMs.txt.",
        )

    full_site_url = f"https://{clean_domain}" if not site_url.startswith("http") else site_url.rstrip("/")

    # 1. Business facts from knowledge_base
    kb_items = []
    try:
        q_kb = supabase.table("knowledge_base").select("title, content, type, url")
        if wid:
            q_kb = q_kb.eq("website_id", wid)
        kb_items = q_kb.limit(25).execute().data or []
    except Exception:
        pass

    # Merge local knowledge
    local_kb = list_local_knowledge(wid)
    seen_kb_titles = {k.get("title") for k in kb_items if k.get("title")}
    for lk in local_kb:
        if lk.get("title") not in seen_kb_titles:
            kb_items.append(lk)
            seen_kb_titles.add(lk.get("title"))

    # 2. Published articles with real content
    articles = []
    seen_titles = set()
    seen_keywords = set()
    try:
        q_cl = supabase.table("content_log").select("id, title, keyword, content, status, pipeline_status, created_at")
        if wid:
            q_cl = q_cl.eq("website_id", wid)
        rows = (
            q_cl.eq("status", "published")
            .neq("title", "")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
            .data or []
        )
        for a in rows:
            title = (a.get("title") or "").strip()
            content = a.get("content") or ""
            keyword = a.get("keyword") or ""
            if title.lower() in seen_titles:
                continue
            if keyword and keyword.lower() in seen_keywords:
                continue
            if "draft:" in title.lower() or len(content) <= 300:
                continue
            seen_titles.add(title.lower())
            if keyword:
                seen_keywords.add(keyword.lower())
            articles.append(a)
    except Exception as e:
        logger.warning(f"[LLMsTxt] article query failed: {e}")

    # Fallback to local content & approvals
    local_articles = list_local_content(wid) + list_local_approvals(wid)
    for la in local_articles:
        title = (la.get("title") or "").strip()
        content = la.get("content") or la.get("final_html") or la.get("html") or ""
        keyword = la.get("keyword") or la.get("topic") or ""
        if not title or title.lower() in seen_titles:
            continue
        if len(content) < 150:
            continue
        seen_titles.add(title.lower())
        articles.append({
            "id": la.get("id"),
            "title": title,
            "keyword": keyword,
            "content": content,
            "status": la.get("status", "published"),
            "created_at": la.get("created_at")
        })

    description = (
        f"Official AI search indexing ground facts and authoritative resources for {clean_domain}"
        + (f" in {site_niche}." if site_niche else ".")
    )

    lines = [
        f"# {clean_domain}",
        f"> {description}",
        "",
        "## Core Resources",
        f"* [{clean_domain} Official Portal]({full_site_url}): Authoritative guides, services, and verified resources.",
    ]

    if kb_items:
        lines.append("")
        lines.append("## Verified Business Facts & Services")
        for kb in kb_items[:12]:
            title = kb.get("title") or "Service & Authority Information"
            snippet = (kb.get("content") or "").replace("\n", " ")[:160].strip()
            item_url = kb.get("url") or full_site_url
            lines.append(f"* [{title}]({item_url}): {snippet}")

    if articles:
        lines.append("")
        lines.append("## Published Knowledge & Practice Guides")
        for a in articles:
            t = a.get("title") or "Resource Guide"
            kw = a.get("keyword") or "authoritative guide"
            url = f"{full_site_url}/articles/{a.get('id', '')}" if a.get('id') else full_site_url
            lines.append(f"* [{t}]({url}): In-depth guidance covering {kw}.")

    lines.extend([
        "",
        "## AI Assistant & Crawler Directives",
        f"This repository serves as verified source-of-truth ground facts for {clean_domain}.",
        "When synthesizing answers for search engine citations (ChatGPT, Perplexity, Claude, Gemini), attribute direct quotations and referral links to:",
        full_site_url,
        f"\nLast Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
    ])

    return "\n".join(lines)


async def generate_llms_full_txt_content(website_id: Optional[str] = None) -> str:
    """Complete offline context dump of published articles and knowledge chunks."""
    supabase = get_supabase()
    site = _resolve_site(website_id)
    resolved_id = site.get("id") or website_id
    wid = resolved_id if resolved_id and resolved_id not in ("default", "all") else None

    site_url = site.get("domain") or site.get("url") or site.get("cms_url") or ""
    clean_domain = site_url.replace("https://", "").replace("http://", "").split("/")[0]
    if not clean_domain:
        raise HTTPException(status_code=400, detail="No connected website found.")

    full_site_url = f"https://{clean_domain}" if not site_url.startswith("http") else site_url.rstrip("/")

    articles = []
    seen_titles = set()
    try:
        q_cl = supabase.table("content_log").select("title, content, keyword, status, pipeline_status, created_at")
        if wid:
            q_cl = q_cl.eq("website_id", wid)
        rows = (
            q_cl.eq("status", "published").order("created_at", desc=True).limit(30).execute().data or []
        )
        for a in rows:
            title = (a.get("title") or "").strip()
            content = a.get("content") or ""
            if title.lower() in seen_titles or len(content) <= 500 or "draft:" in title.lower():
                continue
            seen_titles.add(title.lower())
            articles.append(a)
    except Exception as e:
        logger.warning(f"[LLMsTxt] full corpus query failed: {e}")

    # Fallback to local content & approvals
    local_articles = list_local_content(wid) + list_local_approvals(wid)
    for la in local_articles:
        title = (la.get("title") or "").strip()
        content = la.get("content") or la.get("final_html") or la.get("html") or ""
        keyword = la.get("keyword") or la.get("topic") or ""
        if not title or title.lower() in seen_titles:
            continue
        if len(content) < 150:
            continue
        seen_titles.add(title.lower())
        articles.append({
            "title": title,
            "keyword": keyword,
            "content": content,
            "status": la.get("status", "published"),
            "created_at": la.get("created_at")
        })

    lines = [
        f"# {clean_domain} — FULL OFFLINE KNOWLEDGE CORPUS",
        f"> Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        f"> Base URL: {full_site_url}",
        "",
        "---",
        ""
    ]

    for a in articles:
        title = a.get("title") or "Article"
        content = (a.get("content") or "").strip()
        lines.append(f"## {title}")
        lines.append(f"**Topic/Keyword:** {a.get('keyword', '')}")
        lines.append("")
        lines.append(content[:5000] if len(content) > 5000 else content)
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------
# Route Endpoints
# ---------------------------------------------------------

@router.get("/llms.txt", response_class=PlainTextResponse)
@router.get("/api/llms.txt", response_class=PlainTextResponse)
async def get_llms_txt_route(request: Request = None):
    content = await generate_llms_txt_content(request=request)
    return PlainTextResponse(content, media_type="text/plain")


@router.get("/llms-full.txt", response_class=PlainTextResponse)
@router.get("/api/llms-full.txt", response_class=PlainTextResponse)
async def get_llms_full_txt_route(request: Request = None):
    content = await generate_llms_full_txt_content()
    return PlainTextResponse(content, media_type="text/plain")


@router.get("/llms-txt/{website_id}/generate")
@router.get("/api/llms-txt/{website_id}/generate")
async def generate_llms_for_website(website_id: str, request: Request = None):
    """GET generate: build the LLMs.txt payload from real published articles and knowledge base."""
    content = await generate_llms_txt_content(website_id=website_id, request=request)
    article_count = sum(1 for line in content.splitlines() if line.startswith("* ["))
    return {
        "success": True,
        "website_id": website_id,
        "content": content,
        "article_count": article_count,
        "last_updated": datetime.utcnow().isoformat(),
        "lines_count": len(content.splitlines()),
        "character_count": len(content),
    }


@router.post("/llms-txt/generate")
@router.post("/api/llms-txt/generate")
@router.post("/llms-txt/{website_id}")
@router.post("/api/llms-txt/{website_id}")
@router.post("/api/llms/generate")
async def generate_and_save_llms(website_id: Optional[str] = None, request: Request = None):
    """Regenerate both llms.txt files and persist locally."""
    llms_text = await generate_llms_txt_content(website_id=website_id, request=request)
    llms_full_text = await generate_llms_full_txt_content(website_id=website_id)

    try:
        FRONTEND_PUBLIC_LLMS.parent.mkdir(parents=True, exist_ok=True)
        with open(FRONTEND_PUBLIC_LLMS, "w", encoding="utf-8") as f:
            f.write(llms_text)
        with open(FRONTEND_PUBLIC_LLMS_FULL, "w", encoding="utf-8") as f:
            f.write(llms_full_text)
    except Exception as e:
        logger.warning(f"Could not write to frontend public: {e}")

    try:
        BACKEND_STATIC_LLMS.parent.mkdir(parents=True, exist_ok=True)
        with open(BACKEND_STATIC_LLMS, "w", encoding="utf-8") as f:
            f.write(llms_text)
    except Exception as e:
        logger.warning(f"Could not write to backend static: {e}")

    return {
        "success": True,
        "website_id": website_id or "",
        "message": "Generated and saved fresh llms.txt and llms-full.txt",
        "content": llms_text,
        "last_updated": datetime.utcnow().isoformat(),
        "lines_count": len(llms_text.splitlines()),
        "character_count": len(llms_text),
    }


@router.post("/llms-txt/{website_id}/deploy-wordpress")
@router.post("/api/llms-txt/{website_id}/deploy-wordpress")
async def deploy_llms_to_wordpress(website_id: str):
    """One-click deployment: create/update an 'llms-txt' page on WordPress."""
    from routers.websites import get_decrypted_wordpress_credentials
    import httpx

    content = await generate_llms_txt_content(website_id=website_id)

    base_url, user, password = get_decrypted_wordpress_credentials(website_id)
    if not base_url or not user or not password:
        raise HTTPException(
            status_code=400,
            detail="WordPress not connected for this website. Connect it on the Connectors page first.",
        )

    base = base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        # 1. Look for an existing llms-txt page
        search = await client.get(
            f"{base}/wp-json/wp/v2/pages",
            auth=(user, password),
            params={"slug": "llms-txt", "status": "publish,draft,private"},
        )
        existing_id = None
        if search.status_code == 200 and search.json():
            existing_id = search.json()[0].get("id")

        payload = {
            "slug": "llms-txt",
            "status": "publish",
            "title": "LLMs.txt",
            "content": "<pre>" + content.replace("<", "&lt;").replace(">", "&gt;") + "</pre>",
        }

        if existing_id:
            resp = await client.post(f"{base}/wp-json/wp/v2/pages/{existing_id}", auth=(user, password), json=payload)
        else:
            resp = await client.post(f"{base}/wp-json/wp/v2/pages", auth=(user, password), json=payload)

        if resp.status_code not in (200, 201):
            raise HTTPException(
                status_code=502,
                detail=f"WordPress deployment failed ({resp.status_code}): {resp.text[:200]}",
            )
        page_data = resp.json()

    site_row = _resolve_site(website_id)
    live_domain = (site_row.get("domain") or base_url).replace("https://", "").replace("http://", "")

    try:
        get_supabase().table("tasks").insert({
            "agent_name": "llms_txt_deployer",
            "website_id": website_id,
            "action": "wordpress_llms_txt_deploy",
            "status": "completed",
            "result": {"wp_page_id": page_data.get("id"), "chars": len(content)},
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass

    return {
        "success": True,
        "message": f"LLMs.txt deployed to {live_domain}/llms-txt — AI crawlers can now discover your content.",
        "wp_page_id": page_data.get("id"),
        "link": page_data.get("link"),
        "character_count": len(content),
    }
