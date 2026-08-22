import asyncio
import logging
import math
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from ..database import get_supabase, get_embedding, call_nim_llm
from ..services.crawlee_service import _is_url_blocked
from ..services.reporting_service import report_problem, log_monitoring
from ..services.brain_service import BrainService

logger = logging.getLogger("backend.services.backlink_prospect")


def _score_prospect(
    domain_rating: float,
    relevance_score: float,
    has_broken_link: bool,
    traffic_estimate: float = 0.0,
) -> float:
    score = 0.0
    if domain_rating > 0:
        score += domain_rating * 0.4
    score += relevance_score * 0.3 * 100
    if has_broken_link:
        score += 100 * 0.2
    score += traffic_estimate * 0.1
    return score


async def find_backlink_prospects(
    website_id: str,
    primary_keyword: str,
    target_page_url: Optional[str] = None,
) -> List[Dict[str, Any]]:
    supabase = get_supabase()
    website = (
        supabase.table("websites")
        .select("domain,cms_url")
        .eq("id", website_id)
        .single()
        .execute()
        .data
        or {}
    )
    our_domain = (website.get("domain") or "").lower()
    cms_url = website.get("cms_url") or f"https://{our_domain}"

    brain = BrainService(website_id)
    failures = (
        supabase.table("brain_memory")
        .select("id,content")
        .eq("website_id", website_id)
        .eq("memory_type", "failure")
        .execute()
        .data
        or []
    )
    fail_count = sum(
        1 for f in failures if primary_keyword.lower() in f.get("content", "").lower()
    )
    if fail_count >= 2:
        logger.info("Skipping %s due to %d past failures", primary_keyword, fail_count)
        return []

    queries = [
        f'"{primary_keyword}" "write for us"',
        f'"{primary_keyword}" inurl:resources',
        f'"{primary_keyword}" "useful links" OR "helpful resources"',
        f'"{primary_keyword}" "inurl:links"',
    ]
    if target_page_url:
        competitor_domain = urlparse(target_page_url).netloc
        queries.append(f"link:{competitor_domain} -site:{competitor_domain}")

    prospect_urls: List[Dict[str, str]] = []
    from crawlee.crawlers import PlaywrightCrawler

    for query in queries:
        search_url = (
            "https://www.google.com/search?q=" + query.replace(" ", "+") + "&num=20"
        )
        if _is_url_blocked(search_url):
            continue
        crawler = PlaywrightCrawler(max_requests_per_crawl=1, headless=True)
        serp_results: List[Dict[str, str]] = []

        @crawler.router.default_handler
        async def handler(context):
            page = context.page
            try:
                items = await page.locator("div.g").all()
                for item in items[:20]:
                    try:
                        title_el = item.locator("h3").first
                        title = (
                            await title_el.inner_text()
                            if await title_el.count()
                            else ""
                        )
                        link_el = item.locator("a").first
                        href = (
                            await link_el.get_attribute("href")
                            if await link_el.count()
                            else ""
                        )
                        snippet_el = item.locator("div.VwiC3b").first
                        snippet = (
                            await snippet_el.inner_text()
                            if await snippet_el.count()
                            else ""
                        )
                        if href and href.startswith("http"):
                            serp_results.append(
                                {"url": href, "title": title, "snippet": snippet}
                            )
                    except Exception:
                        continue
            except Exception as exc:
                logger.warning("SERP parse failed: %s", exc)

        try:
            await crawler.run([search_url])
        except Exception as exc:
            logger.warning("Google search crawl failed: %s", exc)
        prospect_urls.extend(serp_results)

    seen = set()
    unique_prospects: List[Dict[str, str]] = []
    for p in prospect_urls:
        if p["url"] not in seen:
            seen.add(p["url"])
            unique_prospects.append(p)
    unique_prospects = unique_prospects[:50]

    prospects: List[Dict[str, Any]] = []
    for prospect in unique_prospects:
        p_url = prospect["url"]
        if our_domain and urlparse(p_url).netloc.lower() == our_domain:
            continue
        if _is_url_blocked(p_url):
            continue

        page_data: Dict[str, Any] = {}
        try:
            from crawlee.crawlers import BeautifulSoupCrawler as BSCrawler

            crawler = BSCrawler(max_requests_per_crawl=1, headless=True)

            @crawler.router.default_handler
            async def handler(context):
                if _is_url_blocked(context.request.url):
                    return
                soup = context.soup
                page_data["title"] = (
                    soup.title.string.strip()
                    if soup.title and soup.title.string
                    else prospect.get("title", "")
                )
                page_data["text"] = soup.get_text(separator=" ", strip=True)[:5000]
                page_data["links"] = []
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if href.startswith("/"):
                        href = urljoin(p_url, href)
                    if href.startswith("http"):
                        page_data["links"].append(
                            {"href": href, "anchor": a.get_text(strip=True)}
                        )
                page_data["emails"] = re.findall(
                    r"[\w\.-]+@[\w\.-]+\.\w+", page_data.get("text", "")
                )

            await crawler.run([p_url])
        except Exception as exc:
            logger.warning("Prospect crawl failed %s: %s", p_url, exc)
            continue

        if not page_data:
            continue

        broken_link_url = None
        broken_anchor = None
        for link in page_data.get("links", []):
            href = link["href"]
            if href.startswith("http") and urlparse(href).netloc.lower() != urlparse(p_url).netloc.lower():
                try:
                    import httpx

                    async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
                        resp = await client.head(href)
                        if resp.status_code == 404:
                            broken_link_url = href
                            broken_anchor = link["anchor"]
                            break
                except Exception:
                    continue

        rel_score = 0.0
        try:
            target_text = target_page_url or primary_keyword
            target_emb = await get_embedding(target_text, website_id=website_id)
            prospect_emb = await get_embedding(
                page_data.get("text", "")[:4000], website_id=website_id
            )
            dot = sum(a * b for a, b in zip(target_emb, prospect_emb))
            mag_t = math.sqrt(sum(a * a for a in target_emb))
            mag_p = math.sqrt(sum(a * a for a in prospect_emb))
            rel_score = dot / (mag_t * mag_p) if mag_t and mag_p else 0.0
        except Exception:
            rel_score = 0.0

        if rel_score < 0.7:
            continue

        domain_rating = 0.0
        ahrefs_key = os.getenv("AHREFS_API_KEY")
        moz_key = os.getenv("MOZ_API_KEY")
        domain = urlparse(p_url).netloc
        if ahrefs_key:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.get(
                        f"https://apiv2.ahrefs.com/?token={ahrefs_key}&from=domain_rating&target={domain}&mode=domain&output=json"
                    )
                    if r.status_code == 200:
                        domain_rating = float(r.json().get("domain_rating", 0))
            except Exception:
                pass
        elif moz_key:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.get(
                        f"https://lsapi.seomoz.com/v2/url_metrics/{domain}",
                        headers={"Authorization": f"Bearer {moz_key}"},
                    )
                    if r.status_code == 200:
                        domain_rating = float(
                            r.json()
                            .get("root_domain_metrics", {})
                            .get("domain_authority", 0)
                        )
            except Exception:
                pass
        else:
            domain_rating = 0.0

        contact_email = None
        emails = page_data.get("emails", [])
        for em in emails:
            if "noreply" not in em.lower() and "no-reply" not in em.lower():
                contact_email = em
                break
        if not contact_email:
            contact_url = urljoin(p_url, "/contact")
            try:
                from crawlee.crawlers import BeautifulSoupCrawler as BSCrawler2

                cc = BSCrawler2(max_requests_per_crawl=1, headless=True)
                contact_captured: Dict[str, Any] = {}

                @cc.router.default_handler
                async def handler2(context):
                    if _is_url_blocked(context.request.url):
                        return
                    s = context.soup
                    contact_captured["text"] = s.get_text(separator=" ", strip=True)[
                        :3000
                    ]

                await cc.run([contact_url])
                emails2 = re.findall(
                    r"[\w\.-]+@[\w\.-]+\.\w+", contact_captured.get("text", "")
                )
                for em in emails2:
                    if "noreply" not in em.lower() and "no-reply" not in em.lower():
                        contact_email = em
                        break
            except Exception:
                pass

        if broken_link_url:
            strategy = "broken_link"
        elif "resources" in p_url.lower() or "resources" in prospect.get("title", "").lower():
            strategy = "resource_page"
        elif target_page_url and any(
            link.get("href", "").startswith(target_page_url)
            for link in page_data.get("links", [])
        ):
            strategy = "competitor_gap"
        else:
            strategy = "guest_post"

        reason = ""
        try:
            reason_prompt = (
                "Generate reason for outreach: prospect "
                + p_url
                + " strategy "
                + strategy
                + " broken link "
                + str(broken_link_url)
                + " target "
                + (target_page_url or cms_url)
                + " keyword "
                + primary_keyword
                + ", explain why our page better with real pricing table 2026"
            )
            reason = await call_nim_llm(reason_prompt, website_id=website_id)
            reason = reason.strip().strip('"')
        except Exception:
            reason = f"Relevant {strategy} opportunity for {primary_keyword}"

        anchor_suggestion = ""
        try:
            anchor_prompt = (
                "Generate natural anchor for "
                + primary_keyword
                + ", not exact match spam, max 5 words, secondary keyword"
            )
            anchor_suggestion = await call_nim_llm(anchor_prompt, website_id=website_id)
            anchor_suggestion = anchor_suggestion.strip().strip('"')
        except Exception:
            anchor_suggestion = primary_keyword

        score = _score_prospect(domain_rating, rel_score, bool(broken_link_url))

        prospect_record = {
            "website_id": website_id,
            "prospect_url": p_url,
            "domain_rating": domain_rating,
            "contact_email": contact_email,
            "strategy": strategy,
            "reason": reason,
            "broken_link_url": broken_link_url,
            "anchor_suggestion": anchor_suggestion,
            "target_page_url": target_page_url or cms_url,
            "target_keyword": primary_keyword,
            "relevance_score": rel_score,
            "status": "opportunity",
            "created_at": datetime.utcnow().isoformat(),
        }
        try:
            supabase.table("backlink_prospects").insert(prospect_record).execute()
            prospects.append(prospect_record)
        except Exception as exc:
            logger.error("Failed to save prospect: %s", exc)

    high_priority = [
        p
        for p in prospects
        if p.get("domain_rating", 0) > 50
        and p.get("relevance_score", 0) > 0.75
        and p.get("broken_link_url")
    ]
    try:
        await log_monitoring(
            website_id=website_id,
            monitor_type="backlink_prospect",
            status="completed",
            checked_urls=len(unique_prospects),
            issues_found=len(prospects),
            execution_ms=0,
        )
    except Exception:
        pass

    for hp in high_priority[:5]:
        try:
            await report_problem(
                website_id=website_id,
                alert_type="backlink_opportunity",
                severity="minor",
                title=f"High priority backlink opportunity: {hp['prospect_url']}",
                description=hp.get("reason", ""),
                data={
                    "prospect_url": hp["prospect_url"],
                    "strategy": hp["strategy"],
                    "domain_rating": hp["domain_rating"],
                },
                source_monitor="backlink_prospect_service",
            )
        except Exception:
            pass

    prospects.sort(key=lambda x: x.get("score", 0), reverse=True)
    return prospects


async def monitor_backlinks(website_id: str) -> Dict[str, Any]:
    supabase = get_supabase()
    existing = (
        supabase.table("backlink_monitor")
        .select("*")
        .eq("website_id", website_id)
        .execute()
        .data
        or []
    )
    acquired_prospects = (
        supabase.table("backlink_prospects")
        .select("*")
        .eq("website_id", website_id)
        .eq("status", "acquired")
        .execute()
        .data
        or []
    )

    to_check = existing + [
        {
            "id": str(__import__("uuid").uuid4()),
            "website_id": website_id,
            "backlink_url": p.get("target_page_url", ""),
            "source_url": p.get("prospect_url", ""),
            "anchor_text": p.get("anchor_suggestion", ""),
            "domain_rating": p.get("domain_rating", 0),
            "status": "active",
            "first_seen_at": datetime.utcnow().isoformat(),
            "checked_at": datetime.utcnow().isoformat(),
        }
        for p in acquired_prospects
    ]

    website = (
        supabase.table("websites")
        .select("domain,cms_url")
        .eq("id", website_id)
        .single()
        .execute()
        .data
        or {}
    )
    cms_url = website.get("cms_url") or f"https://{website.get('domain', '')}"

    checked = 0
    active = 0
    lost = 0
    broken = 0
    redirected = 0

    for item in to_check:
        source_url = item.get("source_url", "")
        if not source_url or _is_url_blocked(source_url):
            continue
        checked += 1
        status_code = None
        anchor_found = False
        captured_anchor = item.get("anchor_text", "")
        try:
            crawler = BSCrawler(max_requests_per_crawl=1)

            @crawler.router.default_handler
            async def handler(context):
                nonlocal status_code, anchor_found, captured_anchor
                if _is_url_blocked(context.request.url):
                    return
                soup = context.soup
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if href.startswith("/"):
                        href = urljoin(source_url, href)
                    if cms_url and cms_url in href:
                        anchor_found = True
                        captured_anchor = a.get_text(strip=True)
                        break
                import httpx

                async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
                    r = await client.head(source_url)
                    status_code = r.status_code

            await crawler.run([source_url])
        except Exception as exc:
            logger.warning("Monitor crawl failed %s: %s", source_url, exc)
            status_code = item.get("status_code")

        if status_code == 404:
            status = "broken"
            broken += 1
        elif status_code and 300 <= status_code < 400:
            status = "redirected"
            redirected += 1
        elif not anchor_found:
            status = "lost"
            lost += 1
        else:
            status = "active"
            active += 1

        ahrefs_key = os.getenv("AHREFS_API_KEY")
        dr = item.get("domain_rating", 0)
        if ahrefs_key:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.get(
                        f"https://apiv2.ahrefs.com/?token={ahrefs_key}&from=domain_rating&target={urlparse(source_url).netloc}&mode=domain&output=json"
                    )
                    if r.status_code == 200:
                        dr = float(r.json().get("domain_rating", dr))
            except Exception:
                pass

        record = {
            "website_id": website_id,
            "backlink_url": item.get("backlink_url", ""),
            "source_url": source_url,
            "anchor_text": captured_anchor,
            "domain_rating": dr,
            "status_code": status_code,
            "status": status,
            "checked_at": datetime.utcnow().isoformat(),
        }
        if item.get("id"):
            try:
                supabase.table("backlink_monitor").update(record).eq("id", item["id"]).execute()
            except Exception:
                pass
        else:
            try:
                supabase.table("backlink_monitor").insert(
                    {**record, "first_seen_at": datetime.utcnow().isoformat()}
                ).execute()
            except Exception:
                pass

        if status == "lost" and dr > 60:
            try:
                await report_problem(
                    website_id=website_id,
                    alert_type="backlink_lost",
                    severity="critical",
                    title=f"Lost DR {dr} backlink from {source_url} anchor {item.get('anchor_text','')} - was active now {status}",
                    data={"source_url": source_url, "domain_rating": dr, "status": status},
                    source_monitor="backlink_prospect_service",
                )
            except Exception:
                pass

    monitors = (
        supabase.table("backlink_monitor")
        .select("anchor_text,target_keyword")
        .eq("website_id", website_id)
        .execute()
        .data
        or []
    )
    if monitors:
        primary_keyword = monitors[0].get("target_keyword") or ""
        if primary_keyword:
            exact = sum(
                1
                for m in monitors
                if m.get("anchor_text", "").lower() == primary_keyword.lower()
            )
            if len(monitors) > 0 and exact / len(monitors) > 0.6:
                try:
                    await report_problem(
                        website_id=website_id,
                        alert_type="anchor_over_optimized",
                        severity="major",
                        title=f"{int((exact/len(monitors))*100)}% anchors exact match {primary_keyword} risk penalty - diversify",
                        data={"keyword": primary_keyword, "exact_ratio": exact / len(monitors)},
                        source_monitor="backlink_prospect_service",
                    )
                except Exception:
                    pass

    try:
        await report_problem(
            website_id=website_id,
            alert_type="backlink_monitor_completed",
            severity="minor",
            title=f"Monitored {checked} backlinks: {active} active, {lost} lost, {broken} broken, {redirected} redirected",
            source_monitor="backlink_prospect_service",
        )
    except Exception:
        pass

    return {
        "checked": checked,
        "active": active,
        "lost": lost,
        "broken": broken,
        "redirected": redirected,
    }
