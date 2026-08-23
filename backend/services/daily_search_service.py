import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger("backend.services.daily_search")


async def daily_search_job(website_id: str) -> Dict[str, Any]:
    """Mine GSC for new striking-distance keywords, analyze SERPs, update brain."""
    from ..database import get_supabase, call_nim_llm
    from ..services.gsc_service import GSCService
    from ..services.crawlee_service import CrawleeService, extract_serp_landscape
    from ..services.serper_service import serper_service
    from ..services.brain_service import BrainService
    from ..services.reporting_service import report_problem

    supabase = get_supabase()
    brain = BrainService(website_id)
    result = {
        "new_keywords": 0,
        "new_competitors": 0,
        "suggested_pages": 0,
        "brain_memories_created": 0,
    }

    try:
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
        if not gsc.is_connected():
            job = {
                "website_id": website_id,
                "job_type": "daily_search",
                "status": "failed",
                "error": "GSC not connected",
                "run_at": datetime.utcnow().isoformat(),
            }
            supabase.table("brain_daily_jobs").insert(job).execute()
            return {"error": "GSC not connected"}

        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=28)).strftime("%Y-%m-%d")
        perf = await gsc.get_keyword_performance(
            start_date=start_date, end_date=end_date, row_limit=2000
        )
        keywords = perf.get("keywords", [])
        striking = [
            k
            for k in keywords
            if 11 <= (k.get("position") or 0) <= 20 and (k.get("impressions") or 0) >= 50
        ][:10]

        for kw_data in striking:
            keyword = kw_data.get("keyword", "")
            if not keyword:
                continue
            result["new_keywords"] += 1

            serp = await serper_service.search(keyword, num=10, auto_fallback=True)
            top_pages = [{"url": o.get("link"), "title": o.get("title")} for o in serp.get("organic", [])]

            our_domain = website.get("domain", "").lower()
            known_domains = set()
            try:
                existing = (
                    supabase.table("serp_landscape")
                    .select("top_urls")
                    .eq("website_id", website_id)
                    .execute()
                    .data
                    or []
                )
                for row in existing:
                    urls = row.get("top_urls") or []
                    if isinstance(urls, list):
                        for u in urls:
                            if isinstance(u, dict):
                                known_domains.add(
                                    __import__("urllib.parse").parse.urlparse(u.get("url", "")).netloc.lower()
                                )
            except Exception:
                pass

            new_competitors = []
            for p in top_pages[:5]:
                domain = __import__("urllib.parse").parse.urlparse(p.get("url", "")).netloc.lower()
                if domain and domain != our_domain and domain not in known_domains:
                    new_competitors.append(domain)
                    await brain.remember(
                        website_id=website_id,
                        memory_type="fact",
                        title=f"New competitor {domain} for {keyword}",
                        content=f"Domain {domain} entered top 5 for {keyword}",
                        source_type="serp_landscape",
                        source_id=None,
                        confidence=0.8,
                    )
                    await report_problem(
                        website_id=website_id,
                        alert_type="competitor_new",
                        severity="medium",
                        title=f"New competitor in top 5: {domain}",
                        description=f"New domain detected for keyword: {keyword}",
                        data={"keyword": keyword, "competitor": domain},
                        source_monitor="daily_search",
                    )
                    result["new_competitors"] += 1

            auto = await brain.should_auto_add_page(
                website_id=website_id,
                keyword=keyword,
                reason=f"GSC striking distance pos {kw_data.get('position')} impressions {kw_data.get('impressions', 0)}",
                priority_score=float(kw_data.get("impressions", 0) / max(kw_data.get("position", 1), 1)),
            )
            if auto.get("auto_approve"):
                result["suggested_pages"] += 1

    except Exception as e:
        logger.error(f"daily_search_job failed: {e}")
        result["error"] = str(e)

    job = {
        "website_id": website_id,
        "job_type": "daily_search",
        "status": "completed" if "error" not in result else "failed",
        "result": json.dumps(result),
        "error": result.get("error"),
        "run_at": datetime.utcnow().isoformat(),
    }
    supabase.table("brain_daily_jobs").insert(job).execute()
    return result


async def daily_cluster_build_job(website_id: str) -> Dict[str, Any]:
    """Rebuild topic clusters from latest GSC and detect coverage gaps."""
    from ..database import get_supabase
    from ..services.gsc_miner_service import mine_gsc_keywords
    from ..services.brain_service import BrainService
    from ..services.reporting_service import report_problem

    supabase = get_supabase()
    brain = BrainService(website_id)
    result = {"clusters_updated": 0, "gaps_found": 0, "suggested_pages": 0}

    try:
        mine = await mine_gsc_keywords(website_id, max_clusters=10, row_limit=2000)
        if mine.get("error"):
            return {"error": mine.get("error")}

        clusters = (
            supabase.table("topic_clusters")
            .select("*")
            .eq("website_id", website_id)
            .execute()
            .data
            or []
        )
        old_coverage = {c["pillar_keyword"]: c.get("coverage", 0) for c in clusters}

        new_clusters = mine.get("clusters_created", 0)
        result["clusters_updated"] = new_clusters

        current_clusters = (
            supabase.table("topic_clusters")
            .select("*")
            .eq("website_id", website_id)
            .execute()
            .data
            or []
        )
        for c in current_clusters:
            pillar = c.get("pillar_keyword", "")
            old_cov = old_coverage.get(pillar, 0)
            new_cov = c.get("coverage", 0)
            if old_cov >= 8 and new_cov < 4:
                result["gaps_found"] += 1
                await brain.remember(
                    website_id=website_id,
                    memory_type="failure",
                    title=f"Cluster coverage dropped: {pillar}",
                    content=f"Coverage dropped from {old_cov} to {new_cov}",
                    source_type="topic_clusters",
                    source_id=c["id"],
                    confidence=0.7,
                )
                await report_problem(
                    website_id=website_id,
                    alert_type="cluster_gap",
                    severity="medium",
                    title=f"Coverage drop in cluster: {pillar}",
                    description=f"Coverage fell from {old_cov} to {new_cov}",
                    data={"pillar": pillar, "old": old_cov, "new": new_cov},
                    source_monitor="daily_cluster_build",
                )

    except Exception as e:
        logger.error(f"daily_cluster_build_job failed: {e}")
        result["error"] = str(e)

    job = {
        "website_id": website_id,
        "job_type": "daily_cluster_build",
        "status": "completed" if "error" not in result else "failed",
        "result": json.dumps(result),
        "error": result.get("error"),
        "run_at": datetime.utcnow().isoformat(),
    }
    supabase.table("brain_daily_jobs").insert(job).execute()
    return result


async def daily_geo_check_job(website_id: str) -> Dict[str, Any]:
    """Check GEO visibility for top pillar keywords and update brain."""
    from ..database import get_supabase, call_nim_llm
    from ..services.brain_service import BrainService
    from ..services.reporting_service import report_problem

    supabase = get_supabase()
    brain = BrainService(website_id)
    result = {"checked_keywords": 0, "new_citations": 0, "lost_citations": 0}

    try:
        pillars = (
            supabase.table("topic_clusters")
            .select("pillar_keyword")
            .eq("website_id", website_id)
            .limit(20)
            .execute()
            .data
            or []
        )
        keywords = [c["pillar_keyword"] for c in pillars if c.get("pillar_keyword")]
        if not keywords:
            keywords = (
                supabase.table("gsc_keywords")
                .select("keyword")
                .eq("website_id", website_id)
                .order("impressions", desc=True)
                .limit(10)
                .execute()
                .data
                or []
            )
            keywords = [k["keyword"] for k in keywords if k.get("keyword")]

        for keyword in keywords[:20]:
            result["checked_keywords"] += 1
            prev = (
                supabase.table("geo_visibility_logs")
                .select("was_cited")
                .eq("website_id", website_id)
                .eq("prompt", keyword)
                .order("checked_at", desc=True)
                .limit(1)
                .execute()
                .data
            )
            prev_cited = prev[0].get("was_cited") if prev else None

            prompt = (
                f"Given the keyword '{keyword}', would a helpful summary be cited by an AI search engine? "
                "Respond ONLY with JSON: {\"was_cited\": true/false, \"reason\": \"...\"}"
            )
            raw = await call_nim_llm(prompt, website_id=website_id)
            try:
                import json as _json
                eval_data = _json.loads(raw)
                was_cited = bool(eval_data.get("was_cited"))
            except Exception:
                was_cited = False

            supabase.table("geo_visibility_logs").insert(
                {
                    "id": str(uuid.uuid4()),
                    "website_id": website_id,
                    "prompt": keyword,
                    "ai_engine": "google_ai_overview",
                    "was_cited": was_cited,
                    "citation_text": raw[:500] if raw else "",
                    "checked_at": datetime.utcnow().isoformat(),
                }
            ).execute()

            if was_cited and not prev_cited:
                result["new_citations"] += 1
                await brain.remember(
                    website_id=website_id,
                    memory_type="outcome",
                    title=f"GEO citation gained: {keyword}",
                    content=f"Content for {keyword} is now cited by AI overviews",
                    source_type="geo_visibility_logs",
                    source_id=None,
                    confidence=0.8,
                )
            elif not was_cited and prev_cited is True:
                result["lost_citations"] += 1
                await brain.remember(
                    website_id=website_id,
                    memory_type="failure",
                    title=f"GEO citation lost: {keyword}",
                    content=f"Content for {keyword} stopped being cited",
                    source_type="geo_visibility_logs",
                    source_id=None,
                    confidence=0.75,
                )
                await report_problem(
                    website_id=website_id,
                    alert_type="geo_citation_lost",
                    severity="medium",
                    title=f"Lost GEO citation: {keyword}",
                    description="Content previously cited is no longer cited",
                    data={"keyword": keyword},
                    source_monitor="daily_geo_check",
                )

    except Exception as e:
        logger.error(f"daily_geo_check_job failed: {e}")
        result["error"] = str(e)

    job = {
        "website_id": website_id,
        "job_type": "daily_geo_check",
        "status": "completed" if "error" not in result else "failed",
        "result": json.dumps(result),
        "error": result.get("error"),
        "run_at": datetime.utcnow().isoformat(),
    }
    try:
        supabase.table("brain_daily_jobs").insert(job).execute()
    except Exception:
        pass
    return result


async def daily_refresh_check_job(website_id: str) -> Dict[str, Any]:
    """Detect decayed content and auto-queue refreshes."""
    from ..database import get_supabase
    from ..services.decay_detector_service import DecayDetectorService
    from ..services.brain_service import BrainService

    supabase = get_supabase()
    brain = BrainService(website_id)
    result = {"decayed": 0, "refresh_queued": 0}

    try:
        detector = DecayDetectorService(website_id)
        decay = await detector.detect_decay(website_id, auto_alert=False)
        decayed_pages = decay.get("decayed_pages", [])
        result["decayed"] = len(decayed_pages)

        for page in decayed_pages:
            url = page.get("url", "")
            reason = (
                f"Decay {page.get('decay_percent', 0):.1f}% on {url}. "
                f"Position {page.get('position_change')}, clicks {page.get('clicks_change')}"
            )
            priority = min(100.0, max(50.0, page.get("decay_percent", 0) * 2))
            auto = await brain.should_auto_add_page(
                website_id=website_id,
                keyword=url,
                reason=reason,
                priority_score=priority,
                business_potential=2,
            )
            if auto.get("auto_approve"):
                result["refresh_queued"] += 1
                supabase.table("brain_auto_pages_queue").update(
                    {"status": "queued_for_writing", "source": "daily_refresh"}
                ).eq("id", auto["queue_id"]).execute()

    except Exception as e:
        logger.error(f"daily_refresh_check_job failed: {e}")
        result["error"] = str(e)

    job = {
        "website_id": website_id,
        "job_type": "daily_refresh_check",
        "status": "completed" if "error" not in result else "failed",
        "result": json.dumps(result),
        "error": result.get("error"),
        "run_at": datetime.utcnow().isoformat(),
    }
    try:
        supabase.table("brain_daily_jobs").insert(job).execute()
    except Exception:
        pass
    return result


async def daily_backlink_check_job(website_id: str) -> Dict[str, Any]:
    """Monitor backlinks and learn from gains/losses."""
    from ..database import get_supabase
    from ..services.brain_service import BrainService
    from ..services.reporting_service import report_problem

    supabase = get_supabase()
    brain = BrainService(website_id)
    result = {"checked": 0, "lost": 0, "new": 0}

    try:
        backlinks = (
            supabase.table("backlinks")
            .select("*")
            .eq("website_id", website_id)
            .execute()
            .data
            or []
        )
        result["checked"] = len(backlinks)

        for bl in backlinks:
            if bl.get("status") == "lost":
                result["lost"] += 1
                await brain.remember(
                    website_id=website_id,
                    memory_type="failure",
                    title=f"Backlink lost: {bl.get('source_url')}",
                    content=f"Backlink from {bl.get('source_url')} to {bl.get('target_url')} is lost",
                    source_type="backlink_monitor",
                    source_id=bl["id"],
                    confidence=0.7,
                )
                await report_problem(
                    website_id=website_id,
                    alert_type="backlink_lost",
                    severity="high",
                    title=f"Backlink lost: {bl.get('source_url')}",
                    description=f"Lost backlink to {bl.get('target_url')}",
                    data={"backlink_id": bl["id"], "source_url": bl.get("source_url")},
                    source_monitor="daily_backlink_check",
                )
            elif bl.get("status") == "active":
                result["new"] += 1

    except Exception as e:
        logger.error(f"daily_backlink_check_job failed: {e}")
        result["error"] = str(e)

    job = {
        "website_id": website_id,
        "job_type": "daily_backlink_check",
        "status": "completed" if "error" not in result else "failed",
        "result": json.dumps(result),
        "error": result.get("error"),
        "run_at": datetime.utcnow().isoformat(),
    }
    try:
        supabase.table("brain_daily_jobs").insert(job).execute()
    except Exception:
        pass
    return result


async def daily_new_page_suggestion_job(website_id: str) -> Dict[str, Any]:
    """Auto-queue approved pages for writing."""
    from ..database import get_supabase
    from ..services.brain_service import BrainService
    from ..agents.writer_agent import generate_content
    from ..services.reporting_service import report_problem

    supabase = get_supabase()
    result = {"approved": 0, "writing_started": 0, "failed": 0}

    try:
        approved = (
            supabase.table("brain_auto_pages_queue")
            .select("*")
            .eq("website_id", website_id)
            .eq("auto_approve", True)
            .eq("status", "suggested")
            .order("priority_score", desc=True)
            .limit(2)
            .execute()
            .data
            or []
        )

        for item in approved:
            result["approved"] += 1
            supabase.table("brain_auto_pages_queue").update(
                {"status": "queued_for_writing"}
            ).eq("id", item["id"]).execute()

            try:
                gen = await generate_content(
                    website_id=website_id,
                    topic=item.get("suggested_topic", ""),
                    primary_keyword=item.get("primary_keyword"),
                )
                if gen.get("status") == "completed":
                    supabase.table("brain_auto_pages_queue").update(
                        {"status": "draft_ready"}
                    ).eq("id", item["id"]).execute()
                    result["writing_started"] += 1
                else:
                    result["failed"] += 1
            except Exception as e:
                logger.error(f"Auto-write failed for {item.get('primary_keyword')}: {e}")
                result["failed"] += 1

    except Exception as e:
        logger.error(f"daily_new_page_suggestion_job failed: {e}")
        result["error"] = str(e)

    job = {
        "website_id": website_id,
        "job_type": "daily_new_page_suggestion",
        "status": "completed" if "error" not in result else "failed",
        "result": json.dumps(result),
        "error": result.get("error"),
        "run_at": datetime.utcnow().isoformat(),
    }
    try:
        supabase.table("brain_daily_jobs").insert(job).execute()
    except Exception:
        pass

    if result.get("writing_started", 0) > 0:
        await report_problem(
            website_id=website_id,
            alert_type="content_gap",
            severity="info",
            title=f"Brain auto-added {result['writing_started']} new pages",
            description="New pages drafted by daily autopilot",
            data={"count": result["writing_started"]},
            source_monitor="daily_new_page_suggestion",
        )

    return result
