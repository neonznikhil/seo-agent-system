import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any

logger = logging.getLogger("backend.services.continuous_monitor")


async def rank_monitor_loop():
    """Monitor keyword rankings every 15 minutes."""
    from .monitors.rank_monitor import RankMonitor
    from .reporting_service import report_problem, log_monitoring
    
    logger.info("[Monitor] Rank monitor started - runs every 15 minutes")
    
    while True:
        start_time = time.time()
        iteration = 0
        last_website_id = "unknown"
        
        try:
            from ..database import get_supabase
            websites = get_supabase().table("websites").select("*").execute().data or []
            
            for website in websites:
                website_id = website["id"]
                last_website_id = website_id
                iteration += 1
                issues_found = 0
                
                try:
                    monitor = RankMonitor(website_id)
                    
                    gsc_data = await monitor.get_gsc_keywords(limit=20)
                    
                    for kw_data in gsc_data:
                        keyword = kw_data.get("keyword", "")
                        if not keyword:
                            continue
                        
                        old_pos = kw_data.get("position")
                        old_pos = old_pos if old_pos and old_pos > 0 else 25
                        
                        for market in ["global", "local", "mobile"]:
                            try:
                                new_pos = await monitor.get_current_position(keyword, market)
                                
                                if new_pos and old_pos:
                                    pos_change = new_pos - old_pos
                                    
                                    if pos_change >= 3 and old_pos <= 20:
                                        issues_found += 1
                                        
                                        if pos_change >= 5:
                                            severity = "critical"
                                        else:
                                            severity = "high"
                                        
                                        await report_problem(
                                            website_id=website_id,
                                            alert_type="rank_drop",
                                            severity=severity,
                                            title=f"Rank Drop: {keyword} {old_pos}→{new_pos} in {market}",
                                            description=f"Keyword dropped from position {old_pos} to {new_pos} in {market} market",
                                            data={
                                                "keyword": keyword,
                                                "old_pos": old_pos,
                                                "new_pos": new_pos,
                                                "market": market,
                                                "url": kw_data.get("url"),
                                                "change": pos_change
                                            },
                                            source_monitor="rank_monitor"
                                        )
                                    
                                    elif pos_change <= -3:
                                        issues_found += 1
                                        await report_problem(
                                            website_id=website_id,
                                            alert_type="rank_opportunity",
                                            severity="high",
                                            title=f"Opportunity: {keyword} jumped {old_pos}→{new_pos}",
                                            description=f"Keyword improved from {old_pos} to {new_pos} - create content cluster",
                                            data={
                                                "keyword": keyword,
                                                "old_pos": old_pos,
                                                "new_pos": new_pos,
                                                "market": market,
                                                "url": kw_data.get("url"),
                                                "change": pos_change
                                            },
                                            source_monitor="rank_monitor"
                                        )
                                
                                elif 11 <= old_pos <= 20 and new_pos > 10:
                                    issues_found += 1
                                    await report_problem(
                                        website_id=website_id,
                                        alert_type="keyword_opportunity",
                                        severity="medium",
                                        title=f"Striking Distance: {keyword} pos {old_pos}",
                                        description=f"Keyword at position {old_pos} needs 1 push to page 1",
                                        data={
                                            "keyword": keyword,
                                            "position": old_pos,
                                            "url": kw_data.get("url"),
                                            "market": market
                                        },
                                        source_monitor="rank_monitor"
                                    )
                            except Exception as e:
                                logger.warning(f"Position check failed for {keyword}/{market}: {e}")
                
                except Exception as e:
                    logger.error(f"Rank monitor failed for website {website_id}: {e}")
                    await report_problem(
                        website_id=website_id,
                        alert_type="monitor_error",
                        severity="high",
                        title=f"Monitor failed: rank_monitor",
                        description=str(e),
                        data={"website_id": website_id},
                        source_monitor="rank_monitor"
                    )
            
            execution_ms = int((time.time() - start_time) * 1000)
            await log_monitoring(website_id=last_website_id, monitor_type="rank_monitor", status="completed", checked_urls=iteration*20, issues_found=issues_found, execution_ms=execution_ms)
            
        except Exception as e:
            logger.error(f"Rank monitor loop crashed: {e}")
        
        await asyncio.sleep(900)  # 15 minutes


async def serp_monitor_loop():
    """Monitor SERP differences between global/local/mobile every 30 minutes."""
    from .monitors.serp_monitor import SERPMonitor
    from .reporting_service import report_problem, log_monitoring
    
    logger.info("[Monitor] SERP monitor started - runs every 30 minutes")
    
    while True:
        start_time = time.time()
        iteration = 0
        last_website_id = "unknown"
        
        try:
            from ..database import get_supabase
            websites = get_supabase().table("websites").select("*").execute().data or []
            
            for website in websites:
                website_id = website["id"]
                last_website_id = website_id
                iteration += 1
                issues_found = 0
                
                try:
                    monitor = SERPMonitor(website_id)
                    top_keywords = await monitor.get_top_keywords(limit=10)
                    
                    for kw in top_keywords:
                        keyword = kw.get("keyword")
                        if not keyword:
                            continue
                        
                        global_pos = await monitor.get_position(keyword, "global")
                        local_pos = await monitor.get_position(keyword, "local")
                        mobile_pos = await monitor.get_position(keyword, "mobile")
                        
                        if global_pos and local_pos and abs(global_pos - local_pos) > 5:
                            issues_found += 1
                            await report_problem(
                                website_id=website_id,
                                alert_type="rank_opportunity",
                                severity="high",
                                title=f"Local SEO Gap: {keyword}",
                                description=f"Global rank #{global_pos} vs Local rank #{local_pos} - optimize for local",
                                data={
                                    "keyword": keyword,
                                    "global_position": global_pos,
                                    "local_position": local_pos,
                                    "market_gap": abs(global_pos - local_pos)
                                },
                                source_monitor="serp_monitor"
                            )
                
                except Exception as e:
                    logger.error(f"SERP monitor failed for website {website_id}: {e}")
                    await report_problem(
                        website_id=website_id,
                        alert_type="monitor_error",
                        severity="high",
                        title="Monitor failed: serp_monitor",
                        description=str(e),
                        data={"website_id": website_id},
                        source_monitor="serp_monitor"
                    )
            
            execution_ms = int((time.time() - start_time) * 1000)
            await log_monitoring(website_id=last_website_id, monitor_type="serp_monitor", status="completed", checked_urls=iteration*10, issues_found=issues_found, execution_ms=execution_ms)
            
        except Exception as e:
            logger.error(f"SERP monitor loop crashed: {e}")
        
        await asyncio.sleep(1800)  # 30 minutes


async def competitor_monitor_loop():
    """Monitor competitors every 60 minutes."""
    from .monitors.competitor_monitor import CompetitorMonitor
    from .reporting_service import report_problem, log_monitoring
    import hashlib
    
    logger.info("[Monitor] Competitor monitor started - runs every 60 minutes")
    
    while True:
        start_time = time.time()
        last_website_id = None
        iteration = 0
        issues_found = 0
        last_website_id = "unknown"
        
        try:
            from ..database import get_supabase
            websites = get_supabase().table("websites").select("*").execute().data or []
            
            for website in websites:
                website_id = website["id"]
                last_website_id = website_id
                iteration += 1
                issues_found = 0
                competitors = []
                
                try:
                    monitor = CompetitorMonitor(website_id)
                    competitors = get_supabase().table("competitors").select("*").eq("website_id", website_id).execute().data or []
                    
                    for comp in competitors:
                        try:
                            changes = await monitor.check_competitor(comp)
                            
                            if changes.get("pricing_changed"):
                                issues_found += 1
                                await report_problem(
                                    website_id=website_id,
                                    alert_type="competitor_price",
                                    severity="high",
                                    title=f"Competitor {comp['competitor_domain']} price change",
                                    description=f"Price changed: {changes.get('old_price')} → {changes.get('new_price')}",
                                    data={
                                        "competitor_domain": comp["competitor_domain"],
                                        "old_pricing": changes.get("old_price"),
                                        "new_pricing": changes.get("new_price")
                                    },
                                    source_monitor="competitor_monitor"
                                )
                            
                            if changes.get("new_content"):
                                issues_found += 1
                                await report_problem(
                                    website_id=website_id,
                                    alert_type="competitor_content",
                                    severity="medium",
                                    title=f"Competitor {comp['competitor_domain']} published new content",
                                    description=f"{changes.get('new_pages', 0)} new pages detected",
                                    data={
                                        "competitor_domain": comp["competitor_domain"],
                                        "new_pages_count": changes.get("new_pages", 0),
                                        "new_urls": changes.get("new_urls", [])
                                    },
                                    source_monitor="competitor_monitor"
                                )
                        
                        except Exception as e:
                            logger.warning(f"Competitor check failed for {comp['competitor_domain']}: {e}")
                
                except Exception as e:
                    logger.error(f"Competitor monitor failed for website {website_id}: {e}")
                    await report_problem(
                        website_id=website_id,
                        alert_type="monitor_error",
                        severity="high",
                        title="Monitor failed: competitor_monitor",
                        description=str(e),
                        data={"website_id": website_id},
                        source_monitor="competitor_monitor"
                    )
            
            execution_ms = int((time.time() - start_time) * 1000)
            await log_monitoring(website_id=last_website_id, monitor_type="competitor_monitor", status="completed", checked_urls=iteration*(len(competitors) if competitors else 1), issues_found=issues_found, execution_ms=execution_ms)
            
        except Exception as e:
            logger.error(f"Competitor monitor loop crashed: {e}")
        
        await asyncio.sleep(3600)  # 60 minutes


async def tech_monitor_loop():
    """Monitor tech issues every 60 minutes."""
    from .monitors.tech_monitor import TechMonitor
    from .reporting_service import report_problem, log_monitoring
    import aiohttp
    
    logger.info("[Monitor] Tech monitor started - runs every 60 minutes")
    
    while True:
        start_time = time.time()
        last_website_id = None
        iteration = 0
        issues_found = 0
        last_website_id = "unknown"
        
        try:
            from ..database import get_supabase
            websites = get_supabase().table("websites").select("*").execute().data or []
            
            for website in websites:
                website_id = website["id"]
                last_website_id = website_id
                iteration += 1
                issues_found = 0
                
                try:
                    monitor = TechMonitor(website_id)
                    pages_to_check = await monitor.get_top_pages(limit=5)
                    
                    for page_url in pages_to_check:
                        try:
                            checks = await monitor.check_page(page_url)
                            
                            if checks.get("broken_links"):
                                for link in checks["broken_links"]:
                                    issues_found += 1
                                    await report_problem(
                                        website_id=website_id,
                                        alert_type="tech_broken_link",
                                        severity="high",
                                        title=f"Broken link on {page_url}",
                                        description=f"Link {link['url']} returns {link['status']}",
                                        data={
                                            "page_url": page_url,
                                            "broken_url": link["url"],
                                            "status": link["status"]
                                        },
                                        source_monitor="tech_monitor"
                                    )
                            
                            if checks.get("speed_degraded"):
                                issues_found += 1
                                await report_problem(
                                    website_id=website_id,
                                    alert_type="tech_speed",
                                    severity="high",
                                    title=f"Speed degraded on {page_url}",
                                    description=f"LCP {checks.get('old_lcp')}s → {checks.get('new_lcp')}s",
                                    data={
                                        "page_url": page_url,
                                        "old_lcp": checks.get("old_lcp"),
                                        "new_lcp": checks.get("new_lcp"),
                                        "lcp_change": checks.get("lcp_change")
                                    },
                                    source_monitor="tech_monitor"
                                )
                            
                            if checks.get("mobile_issues"):
                                issues_found += 1
                                await report_problem(
                                    website_id=website_id,
                                    alert_type="tech_mobile",
                                    severity="medium",
                                    title=f"Mobile issues on {page_url}",
                                    description=checks.get("mobile_issues"),
                                    data={"page_url": page_url, "issues": checks["mobile_issues"]},
                                    source_monitor="tech_monitor"
                                )
                        
                        except Exception as e:
                            logger.warning(f"Page check failed for {page_url}: {e}")
                
                except Exception as e:
                    logger.error(f"Tech monitor failed for website {website_id}: {e}")
                    await report_problem(
                        website_id=website_id,
                        alert_type="monitor_error",
                        severity="high",
                        title="Monitor failed: tech_monitor",
                        description=str(e),
                        data={"website_id": website_id},
                        source_monitor="tech_monitor"
                    )
            
            execution_ms = int((time.time() - start_time) * 1000)
            await log_monitoring(website_id=last_website_id, monitor_type="tech_monitor", status="completed", checked_urls=iteration*5, issues_found=issues_found, execution_ms=execution_ms)
            
        except Exception as e:
            logger.error(f"Tech monitor loop crashed: {e}")
        
        await asyncio.sleep(3600)  # 60 minutes


async def geo_monitor_loop():
    """Monitor local SEO / geo ranking signals every 30 minutes."""
    from .monitors.geo_monitor import GEOMonitor
    from .reporting_service import report_problem, log_monitoring

    logger.info("[Monitor] GEO monitor started - runs every 30 minutes")

    while True:
        start_time = time.time()
        last_website_id = None
        iteration = 0
        issues_found = 0

        try:
            from ..database import get_supabase
            websites = get_supabase().table("websites").select("*").execute().data or []

            for website in websites:
                website_id = website["id"]
                iteration += 1
                issues_found = 0

                try:
                    monitor = GEOMonitor(website_id)
                    keywords = await monitor.get_local_keywords(limit=10)

                    for kw in keywords:
                        keyword = kw.get("keyword")
                        if not keyword:
                            continue

                        city_rank = await monitor.get_geo_rank(keyword, kw.get("city"))
                        gmb_signal = await monitor.get_gmb_signal(keyword)

                        if city_rank and gmb_signal:
                            if city_rank > 20 and gmb_signal.get("rating", 0) >= 4.0:
                                issues_found += 1
                                await report_problem(
                                    website_id=website_id,
                                    alert_type="geo_opportunity",
                                    severity="high",
                                    title=f"Local opportunity: {keyword} in {kw.get('city')}",
                                    description=f"Rank #{city_rank} despite strong GMB rating {gmb_signal.get('rating')}",
                                    data={
                                        "keyword": keyword,
                                        "city": kw.get("city"),
                                        "rank": city_rank,
                                        "gmb_rating": gmb_signal.get("rating"),
                                    },
                                    source_monitor="geo_monitor",
                                )

                            if kw.get("NAP_inconsistent"):
                                issues_found += 1
                                await report_problem(
                                    website_id=website_id,
                                    alert_type="nap_issue",
                                    severity="medium",
                                    title=f"NAP inconsistency for {keyword}",
                                    description="Name/address/phone mismatch detected",
                                    data={"keyword": keyword, "city": kw.get("city")},
                                    source_monitor="geo_monitor",
                                )

                except Exception as e:
                    logger.error(f"GEO monitor failed for website {website_id}: {e}")
                    await report_problem(
                        website_id=website_id,
                        alert_type="monitor_error",
                        severity="high",
                        title="Monitor failed: geo_monitor",
                        description=str(e),
                        data={"website_id": website_id},
                        source_monitor="geo_monitor",
                    )

            execution_ms = int((time.time() - start_time) * 1000)
            await log_monitoring(
                website_id=last_website_id,
                monitor_type="geo_monitor",
                status="completed",
                checked_urls=iteration * 10,
                issues_found=issues_found,
                execution_ms=execution_ms,
            )

        except Exception as e:
            logger.error(f"GEO monitor loop crashed: {e}")

        await asyncio.sleep(1800)  # 30 minutes


async def structure_monitor_loop():
    """Monitor site structure every 6 hours."""
    from .monitors.structure_monitor import StructureMonitor
    from .reporting_service import report_problem, log_monitoring
    
    logger.info("[Monitor] Structure monitor started - runs every 6 hours")
    
    while True:
        start_time = time.time()
        last_website_id = None
        iteration = 0
        issues_found = 0
        last_website_id = "unknown"
        
        try:
            from ..database import get_supabase
            websites = get_supabase().table("websites").select("*").execute().data or []
            
            for website in websites:
                website_id = website["id"]
                last_website_id = website_id
                iteration += 1
                issues_found = 0
                
                try:
                    monitor = StructureMonitor(website_id)
                    issues = await monitor.analyze_structure()
                    
                    for issue in issues:
                        issues_found += 1
                        await report_problem(
                            website_id=website_id,
                            alert_type="tech_crawl",
                            severity="medium" if issue.get("severity") == "medium" else "high",
                            title=issue.get("title", "Structure issue"),
                            description=issue.get("description", ""),
                            data=issue.get("data", {}),
                            source_monitor="structure_monitor"
                        )
                
                except Exception as e:
                    logger.error(f"Structure monitor failed for website {website_id}: {e}")
                    await report_problem(
                        website_id=website_id,
                        alert_type="monitor_error",
                        severity="high",
                        title="Monitor failed: structure_monitor",
                        description=str(e),
                        data={"website_id": website_id},
                        source_monitor="structure_monitor"
                    )
            
            execution_ms = int((time.time() - start_time) * 1000)
            await log_monitoring(website_id=last_website_id, monitor_type="structure_monitor", status="completed", checked_urls=iteration, issues_found=issues_found, execution_ms=execution_ms)
            
        except Exception as e:
            logger.error(f"Structure monitor loop crashed: {e}")
        
        await asyncio.sleep(21600)  # 6 hours


def start_all_monitors():
    """Start all monitoring loops as background tasks."""
    asyncio.create_task(rank_monitor_loop())
    asyncio.create_task(serp_monitor_loop())
    asyncio.create_task(competitor_monitor_loop())
    asyncio.create_task(tech_monitor_loop())
    asyncio.create_task(geo_monitor_loop())
    asyncio.create_task(structure_monitor_loop())
    logger.info("[Monitoring] All 6 monitor loops started")