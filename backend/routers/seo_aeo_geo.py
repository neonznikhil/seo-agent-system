"""AEO (Answer Engine Optimization) — real schema auditing and SERP-based
citation simulation. No fabricated 'CITED #1' data ever leaves this module.

What actually happens here:
1. Published articles are pulled from content_log (and their live WordPress
   copies when reachable) and parsed for JSON-LD schema types.
2. An AI Readiness Score is computed from measurable on-page signals:
   schema coverage (40), BLUF answer presence (20), internal links (20),
   FAQ question count (10), LLMs.txt inclusion (10).
3. Serper.dev searches each top article's keyword and checks whether OUR domain
   appears in featured snippets / PAA / knowledge panels. Results persist to
   geo_visibility_logs.
4. The schema generator produces FAQPage JSON-LD from REAL article content via
   NVIDIA NIM and can inject it into WordPress through the REST API.
"""

import json
import logging
import re
from datetime import datetime
from typing import Optional, List, Dict, Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..database import get_supabase, call_nim_llm
from ..services.serper_service import serper_service

logger = logging.getLogger("backend.routers.seo_aeo_geo")
router = APIRouter(tags=["aeo", "geo", "seo"])

SCHEMA_POINTS = {"schema_coverage": 40, "bluf": 20, "internal_links": 20, "faq": 10, "llms_txt": 10}


class TrackQueryRequest(BaseModel):
    query: Optional[str] = None
    queries: Optional[List[str]] = None
    website_id: Optional[str] = None


class InjectSchemaRequest(BaseModel):
    blog_id: Optional[str] = None
    page_url: Optional[str] = None
    schema_type: Optional[str] = "FAQPage"
    website_id: Optional[str] = None
    schema_data: Optional[dict] = Field(default=None, alias="schema_json")

    @property
    def schema_json(self) -> Optional[dict]:
        return self.schema_data


class FormatBlufRequest(BaseModel):
    content: str
    topic: str
    website_id: Optional[str] = None


class AeoBoostRequest(BaseModel):
    website_id: Optional[str] = None
    blog_id: Optional[str] = None
    page_url: Optional[str] = None
    target_keyword: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_website(website_id: Optional[str]) -> dict:
    if not website_id or website_id in ("default", "all"):
        return {}
    try:
        return (
            get_supabase().table("websites").select("*").eq("id", website_id).single().execute().data or {}
        )
    except Exception:
        return {}


def _extract_schema_types(html: str) -> List[str]:
    types: List[str] = []
    for match in re.finditer(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html or "", re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(match.group(1).strip())
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        graph_items: List[Any] = []
        for item in items:
            if isinstance(item, dict) and "@graph" in item:
                graph_items.extend(item["@graph"])
            else:
                graph_items.append(item)
        for item in graph_items:
            if isinstance(item, dict) and "@type" in item:
                t = item["@type"]
                types.extend(t if isinstance(t, list) else [t])
    return list({str(t) for t in types})


async def _fetch_wp_post_html(website_id: str, wp_post_id) -> Optional[str]:
    """Fetch rendered/RAW post HTML from the connected WordPress site."""
    try:
        from ..routers.websites import get_decrypted_wordpress_credentials
        base_url, user, password = get_decrypted_wordpress_credentials(website_id)
        if not base_url:
            return None
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            kwargs: Dict[str, Any] = {}
            if user and password:
                kwargs["auth"] = (user, password)
            resp = await client.get(f"{base_url.rstrip('/')}/wp-json/wp/v2/posts/{wp_post_id}", **kwargs)
            if resp.status_code == 200:
                return resp.json().get("content", {}).get("rendered", "")
    except Exception as e:
        logger.debug(f"[AEO] WP fetch failed: {e}")
    return None


def _score_article(html_content: str, markdown_content: str, keyword: str,
                   has_faq_schema: bool) -> Dict[str, Any]:
    """AI Readiness scoring from measurable signals only."""
    text = html_content or markdown_content or ""
    lower = text.lower()
    combined = f" {html_content or ''} {markdown_content or ''} "

    schema_types = _extract_schema_types(html_content)
    has_faq_page = has_faq_schema or "faqpage" in [t.lower() for t in schema_types]

    # BLUF: first paragraph contains a direct answer mentioning the keyword
    paragraphs = [p.strip() for p in _strip_tags(html_content).split("\n") if p.strip()] or \
                 [p.strip() for p in (markdown_content or "").split("\n\n") if p.strip()]
    bluf_present = bool(paragraphs) and len(paragraphs[0]) > 40 and \
        (keyword.lower()[:20] in lower[:600])

    # Internal links present in body
    internal_links = len(re.findall(r'<a\s+href=["\'](?:https?://[^"\']*?)?/', html_content or ""))
    if not internal_links and markdown_content:
        internal_links = len(re.findall(r'\]\((/|https?://)', markdown_content))

    # FAQ question count
    faq_questions = len(re.findall(r'<h3[^>]*>.{0,150}\?</h3>', html_content or "")) + \
                    len(re.findall(r'^\s*\*\*Q\d?:', markdown_content or "", re.MULTILINE))
    if has_faq_page and faq_questions == 0:
        faq_questions = 1

    score = 0
    score += SCHEMA_POINTS["schema_coverage"] * (2 if has_faq_page and ("article" in [t.lower() for t in schema_types]) else 1 if has_faq_page else 0)
    score = min(score, SCHEMA_POINTS["schema_coverage"])
    score += SCHEMA_POINTS["bluf"] if bluf_present else 0
    score += min(SCHEMA_POINTS["internal_links"], internal_links * 5)
    score += min(SCHEMA_POINTS["faq"], faq_questions * 2)

    return {
        "ai_readiness_score": min(score, 100),
        "has_faqpage": has_faq_page,
        "schema_types": schema_types,
        "bluf_present": bluf_present,
        "internal_link_count": internal_links,
        "faq_question_count": faq_questions,
        "breakdown": {
            "schema_coverage": min(SCHEMA_POINTS["schema_coverage"],
                                   SCHEMA_POINTS["schema_coverage"] if has_faq_page else 0),
            "bluf": SCHEMA_POINTS["bluf"] if bluf_present else 0,
            "internal_links": min(SCHEMA_POINTS["internal_links"], internal_links * 5),
            "faq": min(SCHEMA_POINTS["faq"], faq_questions * 2),
            "llms_txt": 0,  # filled by caller when LLMs.txt is checked
        },
    }


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "\n", html or "")


# ---------------------------------------------------------------------------
# Section 1+2: Schema coverage audit & AI readiness
# ---------------------------------------------------------------------------

@router.get("/api/aeo/status")
@router.get("/aeo/status")
@router.get("/api/aeo")
@router.get("/aeo")
async def get_aeo_overview(website_id: Optional[str] = None):
    """Real schema coverage audit + AI readiness across published articles."""
    supabase = get_supabase()

    site = await _get_website(website_id)
    wid = website_id

    pages_audit = []
    try:
        q = supabase.table("content_log").select(
            "id, title, keyword, wp_post_id, status, pipeline_status, content"
        ).in_("status", ["published", "draft", "approved"])
        if wid and wid not in ("default", "all"):
            q = q.eq("website_id", wid)
        published = q.order("created_at", desc=True).limit(30).execute().data or []
    except Exception:
        published = []

    # LLMs.txt inclusion check (10 pts): does generated llms.txt reference these?
    llms_includes = set()
    try:
        from .llms_txt import generate_llms_txt_content
        llms_content = await generate_llms_txt_content(wid) or ""
        for p in published:
            title = (p.get("title") or "").strip()[:40]
            if title and title.lower() in llms_content.lower():
                llms_includes.add(p["id"])
    except Exception:
        pass

    for p in published:
        title = p.get("title") or "Untitled"
        wp_html = await _fetch_wp_post_html(p.get("website_id") or wid or "", p.get("wp_post_id")) \
            if p.get("wp_post_id") else None
        source_html = wp_html or ""
        audit = _score_article(source_html, p.get("content") or "", p.get("keyword") or title,
                               has_faq_schema=False)
        if p["id"] in llms_includes:
            audit["breakdown"]["llms_txt"] = SCHEMA_POINTS["llms_txt"]
            audit["ai_readiness_score"] = min(100, audit["ai_readiness_score"] + SCHEMA_POINTS["llms_txt"])
            audit["llms_txt_included"] = True
        else:
            audit["llms_txt_included"] = False
        pages_audit.append({
            "content_id": p["id"],
            "title": title,
            "url": f"/articles/{p['id']}",
            "keyword": p.get("keyword"),
            "source_checked": "wordpress" if wp_html else "stored_content",
            **audit,
        })

    total_pages = len(pages_audit)
    covered_pages = sum(1 for p in pages_audit if p["has_faqpage"])
    avg_score = round(sum(p["ai_readiness_score"] for p in pages_audit) / total_pages, 1) if total_pages else None

    # Missing-schema work queue: posts without FAQPage get queued for generation
    missing_faq = [p for p in pages_audit if not p["has_faqpage"]]

    return {
        "success": True,
        "data": {
            "pages": pages_audit,
            "total_published": total_pages,
            "pages_with_faq_schema": covered_pages,
            "coverage_percent": round(covered_pages / total_pages * 100, 1) if total_pages else 0.0,
            "average_ai_readiness": avg_score,
            "missing_schema_queue": [
                {"content_id": p["content_id"], "title": p["title"]} for p in missing_faq
            ],
            "scoring_rubric": {**SCHEMA_POINTS, "_note": "LLMs.txt points awarded per-article when included"},
        }
    }


# ---------------------------------------------------------------------------
# Section 3: Serper-based citation simulation
# ---------------------------------------------------------------------------

@router.get("/api/aeo/sov")
@router.get("/aeo/sov")
async def get_aeo_share_of_voice(website_id: Optional[str] = None):
    """Share-of-voice derived ONLY from stored geo_visibility_logs rows."""
    supabase = get_supabase()
    total_audited = 0
    brand_citations = 0
    try:
        q = supabase.table("geo_visibility_logs").select("id, cited")
        if website_id and website_id not in ("default", "all"):
            q = q.eq("website_id", website_id)
        rows = q.execute().data or []
        total_audited = len(rows)
        brand_citations = sum(1 for r in rows if r.get("cited"))
    except Exception:
        pass

    sov_pct = round((brand_citations / total_audited) * 100, 1) if total_audited else 0.0
    return {
        "success": True,
        "website_id": website_id or "default",
        "share_of_voice_percentage": sov_pct,
        "total_queries_audited": total_audited,
        "brand_citations": brand_citations,
        "note": (
            "Share of voice is estimated from Serper featured-snippet/PAA checks "
            "run against your target keywords."
        ) if total_audited else (
            "No citation checks have run yet. Click 'Run Citation Check' to query "
            "Serper for your top keywords."
        ),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/api/aeo/check-citations")
@router.post("/aeo/check-citations")
async def check_citations_serper(body: TrackQueryRequest):
    """Real Serper.dev citation simulation.

    For each queried keyword we check whether our domain appears in the
    featured snippet, People Also Ask answers, or top organic results, then
    persist an honest geo_visibility_logs row. No direct ChatGPT/Perplexity
    API exists, so this SERP proximity is our best available signal.
    """
    supabase = get_supabase()
    wid = body.website_id or "default"
    site = await _get_website(wid)
    domain = (site.get("domain") or "").replace("https://", "").replace("http://", "").split("/")[0]

    queries: List[str] = []
    if body.queries:
        queries = [q.strip() for q in body.queries if q and q.strip()]
    elif body.query and body.query.strip():
        queries = [body.query.strip()]
    else:
        # Default: keywords of the top 3 recent articles
        try:
            q = supabase.table("content_log").select("keyword").eq("status", "published")
            if wid != "default":
                q = q.eq("website_id", wid)
            rows = q.order("created_at", desc=True).limit(3).execute().data or []
            queries = [r["keyword"] for r in rows if r.get("keyword")]
        except Exception:
            pass

    if not queries:
        raise HTTPException(400, "No queries provided and no published article keywords found")

    results = []
    for query in queries[:10]:
        serp = await serper_service.search(query=query, num=10, auto_fallback=True)
        organic = serp.get("organic") or []
        if not organic:
            results.append({
                "query": query, "checked": False,
                "error": serp.get("error", "No SERP data available"),
            })
            continue

        answer_box_domain = ((serp.get("answerBox") or {}).get("link") or "")
        paa_domains = [p.get("link") or "" for p in (serp.get("peopleAlsoAsk") or []) if isinstance(p, dict)]
        organic_positions = [
            idx + 1 for idx, o in enumerate(organic)
            if domain and domain in (o.get("link") or "")
        ]

        in_answer_box = bool(domain and domain in answer_box_domain)
        in_paa = any(domain and domain in d for d in paa_domains)
        best_position = min(organic_positions) if organic_positions else None

        row = {
            "website_id": wid,
            "platform": "serper_serp_simulation",
            "query": query,
            "cited": bool(in_answer_box or in_paa),
            "citation_position": best_position,
            "response_snippet": json.dumps({
                "featured_snippet": in_answer_box,
                "people_also_ask": in_paa,
                "organic_position": best_position,
            }),
            "created_at": datetime.utcnow().isoformat(),
        }
        try:
            supabase.table("geo_visibility_logs").insert(row).execute()
        except Exception as e:
            logger.debug(f"[AEO] geo_visibility_logs insert failed: {e}")

        results.append({
            "query": query,
            "checked": True,
            "appears_featured_snippet": in_answer_box,
            "appears_people_also_ask": in_paa,
            "organic_position": best_position,
            "citation_probability": (
                "High" if (in_answer_box or in_paa or (best_position and best_position <= 3))
                else "Medium" if (best_position and best_position <= 10)
                else "Low"
            ),
        })

    return {
        "success": True,
        "domain_checked": domain or "(no domain configured)",
        "queries_checked": len(results),
        "results": results,
    }


# ---------------------------------------------------------------------------
# Section 4: Real schema generator + one-click WordPress injection
# ---------------------------------------------------------------------------

@router.post("/api/aeo/generate-faq-schema")
@router.post("/aeo/generate-faq-schema")
async def generate_faq_schema(body: dict):
    """Extract REAL questions/answers from the latest article via NIM -> FAQPage JSON-LD."""
    supabase = get_supabase()
    website_id = body.get("website_id")
    content_id = body.get("blog_id") or body.get("content_id")

    if content_id:
        row = (
            supabase.table("content_log").select("id, title, content, keyword")
            .eq("id", content_id).maybe_single().execute().data
        )
    else:
        q = supabase.table("content_log").select("id, title, content, keyword").eq("status", "published")
        if website_id and website_id != "default":
            q = q.eq("website_id", website_id)
        row = (q.order("created_at", desc=True).limit(1).execute().data or [None])[0]

    if not row or not (row.get("content") or "").strip():
        raise HTTPException(404, "No published article found to generate schema from")

    content_text = row["content"][:4000]
    prompt = (
        f"Read this article and extract 4-6 REAL questions a reader would ask, each answered "
        f"in 40-60 words using facts strictly from the article.\n\nARTICLE:\n{content_text}\n\n"
        'Return ONLY valid JSON matching schema.org FAQPage mainEntity format: '
        '{"mainEntity": [{"name": "Question?", "acceptedAnswer": {"text": "Answer"}}]}'
    )
    raw = await call_nim_llm(prompt, system="Return only valid JSON.", max_tokens=1200,
                             temperature=0.4, fail_silently=False)
    cleaned = raw.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0]
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0]
    try:
        parsed = json.loads(cleaned.strip())
    except Exception as e:
        raise HTTPException(502, f"Model returned invalid FAQ JSON: {e}")

    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q.get("name", ""),
                "acceptedAnswer": {"@type": "Answer", "text": q.get("acceptedAnswer", {}).get("text", "")},
            }
            for q in parsed.get("mainEntity", [])
        ],
    }

    return {
        "success": True,
        "article_title": row.get("title"),
        "article_id": row["id"],
        "schema": schema,
    }


@router.post("/api/aeo/inject-schema")
@router.post("/aeo/inject-schema")
async def inject_schema(body: InjectSchemaRequest):
    """Inject JSON-LD schema into a WordPress post through the REST API."""
    supabase = get_supabase()
    website_id = body.website_id
    content_id = body.blog_id

    if not content_id:
        raise HTTPException(400, "blog_id (content_log id) is required")

    row = (
        supabase.table("content_log").select("*").eq("id", content_id).maybe_single().execute().data
    )
    if not row:
        raise HTTPException(404, "Article not found")

    wp_post_id = row.get("wp_post_id")
    if not wp_post_id:
        raise HTTPException(400, "This article has no WordPress post yet — approve & publish it first")

    # Build or reuse the schema payload
    schema_payload = body.schema_json
    if not schema_payload:
        gen = await generate_faq_schema({"website_id": website_id, "blog_id": content_id})
        schema_payload = gen["schema"]

    script_tag = (
        '<script type="application/ld+json">'
        + json.dumps(schema_payload, ensure_ascii=False)
        + "</script>"
    )

    # Fetch current WP content and append schema block idempotently
    from ..routers.websites import get_decrypted_wordpress_credentials
    base_url, user, password = get_decrypted_wordpress_credentials(website_id)
    if not base_url or not user or not password:
        raise HTTPException(400, "WordPress not connected for this website")

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        get_resp = await client.get(
            f"{base_url.rstrip('/')}/wp-json/wp/v2/posts/{wp_post_id}", auth=(user, password)
        )
        if get_resp.status_code != 200:
            raise HTTPException(502, f"Could not read WordPress post ({get_resp.status_code})")
        existing_content = get_resp.json().get("content", {}).get("raw", "") or ""

        marker = "<!-- rankforge:schema -->"
        if marker in existing_content:
            import re
            new_content = re.sub(
                r"<!-- rankforge:schema -->.*?<!-- /rankforge:schema -->",
                marker + script_tag + "<!-- /rankforge:schema -->",
                existing_content, flags=re.DOTALL,
            )
        else:
            new_content = existing_content + "\n" + marker + script_tag + "<!-- /rankforge:schema -->"

        update_resp = await client.post(
            f"{base_url.rstrip('/')}/wp-json/wp/v2/posts/{wp_post_id}",
            auth=(user, password),
            json={"content": new_content},
        )
        if update_resp.status_code not in (200, 201):
            raise HTTPException(502, f"WordPress update failed ({update_resp.status_code}): {update_resp.text[:200]}")

    # Queue the action in pending_fixes for human visibility
    try:
        supabase.table("pending_fixes").insert({
            "website_id": website_id,
            "fix_type": "schema_injection",
            "description": f"Injected {schema_payload.get('@type')} schema into WP post {wp_post_id}",
            "status": "applied",
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Injected {schema_payload.get('@type')} schema into WordPress post {wp_post_id}",
        "schema": schema_payload,
    }


# ---------------------------------------------------------------------------
# GEO expansion intelligence (real Serper local search)
# ---------------------------------------------------------------------------

@router.get("/api/geo/gap")
@router.get("/geo/gap")
async def get_geo_gap_analysis(website_id: Optional[str] = "default", city: str = "Houston"):
    serp_res = await serper_service.search(query=f"personal injury lawyer in {city}", location=f"{city}, TX", num=5, auto_fallback=True)
    organic = serp_res.get("organic", [])

    if not organic:
        return {
            "success": False,
            "city": city,
            "error": serp_res.get("error", "No local SERP data available — configure Serper API key"),
            "competitor_local_rankings": [],
        }

    return {
        "success": True,
        "city": city,
        "data_source": serp_res.get("source"),
        "competitor_local_rankings": [
            {"rank": idx, "name": item.get("title"), "url": item.get("link")}
            for idx, item in enumerate(organic[:4], start=1)
        ],
    }


@router.post("/api/aeo/boost")
@router.post("/aeo/boost")
async def execute_aeo_boost(body: AeoBoostRequest):
    """Generate a real BLUF answer + FAQ schema for the given keyword/article."""
    supabase = get_supabase()
    kw = body.target_keyword

    if not kw and body.blog_id:
        row = supabase.table("content_log").select("keyword, title").eq("id", body.blog_id).maybe_single().execute().data
        kw = (row or {}).get("keyword")
    if not kw:
        raise HTTPException(400, "target_keyword or blog_id required")

    # 1. Real BLUF answer via NIM
    bluf_prompt = (
        f"Write a direct, factual 50-word BLUF (Bottom Line Up Front) answer for '{kw}' "
        "optimized for Google AI Overviews and Perplexity answer cards. Return ONLY the answer text."
    )
    bluf_answer = await call_nim_llm(bluf_prompt, system="You are an AEO answer engine architect.",
                                     website_id=body.website_id, fail_silently=False)
    if not bluf_answer or not bluf_answer.strip():
        raise HTTPException(502, "BLUF generation returned empty output")

    # 2. Real FAQ schema from the article when available
    schema_payload = None
    if body.blog_id:
        try:
            gen = await generate_faq_schema({"website_id": body.website_id, "blog_id": body.blog_id})
            schema_payload = gen["schema"]
        except Exception as e:
            logger.warning(f"[AEO] Boost schema generation note: {e}")

    try:
        supabase.table("tasks").insert({
            "agent_name": "aeo_agent",
            "website_id": body.website_id,
            "action": "aeo_boost_pipeline",
            "status": "completed",
            "payload": {"keyword": kw, "blog_id": body.blog_id},
            "result": {"bluf_chars": len(bluf_answer), "schema_generated": bool(schema_payload)},
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass

    return {
        "success": True,
        "message": f"AEO boost generated for '{kw}'. Review the schema before injecting.",
        "bluf_block": bluf_answer.strip(),
        "schema_generated": schema_payload,
    }
