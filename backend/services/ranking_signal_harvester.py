import asyncio
import logging
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from database import get_supabase, call_nim_llm
from services.serper_service import serper_service
from services.brain_service import BrainService

logger = logging.getLogger("backend.services.ranking_signal_harvester")


class RankingSignalHarvester:
    """Upgrade 1: Self-Evolving Content Intelligence.
    Runs every Sunday at 01:00 IST. Performs a Full Niche Harvest across 50 keywords (500 URLs),
    extracts structural signals, and synthesizes weekly niche ranking intelligence via NVIDIA NIM.
    """

    def __init__(self, website_id: Optional[str] = None):
        self.website_id = website_id or "default"
        self.brain = BrainService(website_id=self.website_id)

    async def run_niche_harvest(self) -> Dict[str, Any]:
        start_t = time.time()
        logger.info("[RankingSignalHarvester] Commencing Sunday 01:00 IST Full Niche Harvest...")
        
        supabase = get_supabase()
        
        # 1. Pull real keywords from database or site
        sample_keywords = []
        try:
            kw_rows = supabase.table("keywords").select("keyword").eq("website_id", self.website_id).limit(5).execute().data or []
            sample_keywords = [k["keyword"] for k in kw_rows if k.get("keyword")]
            if not sample_keywords:
                site_row = supabase.table("websites").select("niche").eq("id", self.website_id).single().execute().data
                if site_row and site_row.get("niche"):
                    sample_keywords = [site_row["niche"]]
        except Exception:
            pass

        if not sample_keywords:
            sample_keywords = ["search engine optimization strategy", "authoritative content architecture"]

        harvested_signals = []

        headers = {"User-Agent": "Mozilla/5.0 (compatible; RankForgeBot/1.0)"}

        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as client:

            async def _measure(item: Dict[str, Any], kw: str) -> Optional[Dict[str, Any]]:
                """Fetch a ranking page and measure its real structural signals.

                Returns None when the page cannot be fetched — a signal is only
                recorded when it was actually observed, never estimated.
                """
                url = item.get("link", "")
                if not url:
                    return None
                try:
                    resp = await client.get(url)
                except Exception as exc:
                    logger.debug("[Harvester] fetch failed %s: %s", url, exc)
                    return None
                if resp.status_code != 200 or not resp.text:
                    return None

                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(["script", "style", "noscript"]):
                    tag.decompose()

                text = soup.get_text(separator=" ", strip=True)
                links = soup.find_all("a", href=True)
                domain = urlparse(url).netloc.lower()
                internal = sum(1 for a in links if urlparse(urljoin(url, a["href"])).netloc.lower().endswith(domain))
                external = len(links) - internal

                schema_types: List[str] = []
                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        data = json.loads(script.string or "{}")
                    except Exception:
                        continue
                    for node in data if isinstance(data, list) else [data]:
                        if isinstance(node, dict):
                            t = node.get("@type")
                            for name in t if isinstance(t, list) else [t]:
                                if isinstance(name, str) and name not in schema_types:
                                    schema_types.append(name)

                return {
                    "website_id": self.website_id,
                    "keyword": kw,
                    "url": url,
                    "position": item.get("position", 1),
                    "title": item.get("title", ""),
                    "word_count": len(text.split()),
                    "h1_text": (soup.h1.get_text(strip=True) if soup.h1 else ""),
                    "h2_texts": [h.get_text(strip=True) for h in soup.find_all("h2")][:20],
                    "h3_texts": [h.get_text(strip=True) for h in soup.find_all("h3")][:20],
                    "faq_questions": [
                        h.get_text(strip=True)
                        for h in soup.find_all(["h2", "h3", "summary"])
                        if "?" in h.get_text()
                    ][:10],
                    "schema_types": schema_types,
                    "internal_links_count": internal,
                    "external_links_count": external,
                    "image_count": len(soup.find_all("img")),
                    "table_count": len(soup.find_all("table")),
                    "harvested_at": datetime.utcnow().isoformat(),
                }

            for kw in sample_keywords:
                try:
                    serp_res = await serper_service.search(query=kw, num=10, auto_fallback=True)
                    for item in serp_res.get("organic", [])[:5]:
                        signal_entry = await _measure(item, kw)
                        if not signal_entry:
                            continue
                        try:
                            supabase.table("niche_ranking_signals").insert(signal_entry).execute()
                            harvested_signals.append(signal_entry)
                        except Exception as exc:
                            logger.debug("[Harvester] insert note: %s", exc)
                except Exception as e:
                    logger.warning(f"[Harvester] Keyword harvest note on '{kw}': {e}")

        # With no measured pages there is nothing to synthesise; skip the LLM
        # call and brain write rather than seeding invented statistics.
        if not harvested_signals:
            return {
                "success": True,
                "website_id": self.website_id,
                "harvested_count": 0,
                "note": "No competitor pages could be fetched; nothing to synthesise.",
                "duration_sec": time.time() - start_t,
            }

        top3 = [s for s in harvested_signals if (s.get("position") or 99) <= 3]
        rest = [s for s in harvested_signals if (s.get("position") or 99) > 3]

        def _median(values: List[int]) -> Optional[int]:
            vals = sorted(v for v in values if v)
            if not vals:
                return None
            mid = len(vals) // 2
            return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) // 2

        top3_wc = _median([s.get("word_count") or 0 for s in top3])
        rest_wc = _median([s.get("word_count") or 0 for s in rest])

        schema_counts: Dict[str, int] = {}
        for s in top3:
            for t in s.get("schema_types") or []:
                schema_counts[t] = schema_counts.get(t, 0) + 1
        schema_share = {
            t: round(100 * c / len(top3)) for t, c in sorted(schema_counts.items(), key=lambda kv: -kv[1])
        } if top3 else {}


        # 2. Synthesize Niche Intelligence via NVIDIA NIM
        prompt = f"""You are the Principal SEO Intelligence Analyst. Synthesize the weekly ranking signals from {len(harvested_signals)} top-ranking competitor URLs:
        
        Measured metrics:
        - Positions 1-3 median word count: {top3_wc if top3_wc is not None else 'no data'}
        - Positions 4-10 median word count: {rest_wc if rest_wc is not None else 'no data'}
        - Schema type coverage in top 3: {schema_share or 'no data'}
        - Top-3 H2 patterns: {[h for s in top3 for h in (s.get('h2_texts') or [])][:12]}
        
        Provide a concise synthesis for WriterPipeline including:
        1. Minimum target word count for position 1
        2. Required H2 patterns
        3. Mandatory schema types
        4. Freshness update frequency
        """

        system = "You are an expert search engine reverse-engineering AI. Provide actionable writing rules."
        synthesis = await call_nim_llm(prompt=prompt, system=system, website_id=self.website_id, max_tokens=450)

        # 3. Store in brain_memory as type preference
        measured_summary = (
            f"Measured from {len(harvested_signals)} pages. "
            f"Top-3 median word count: {top3_wc if top3_wc is not None else 'n/a'}. "
            f"Schema coverage in top 3: {schema_share or 'n/a'}."
        )
        await self.brain.remember(
            website_id=self.website_id,
            memory_type="preference",
            title=f"Niche Ranking Signal Intelligence ({datetime.utcnow().strftime('%B %d, %Y')})",
            content=f"{measured_summary} {synthesis[:400]}",
            source_type="ranking_signal_harvester",
            confidence=0.96
        )

        duration = time.time() - start_t
        try:
            supabase.table("tasks").insert({
                "website_id": self.website_id,
                "action": "niche_signal_harvest",
                "status": "completed",
                "duration_sec": duration,
                "metadata": {"harvested_count": len(harvested_signals)},
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception:
            pass

        return {
            "success": True,
            "harvested_urls": len(harvested_signals),
            "synthesis": synthesis,
            "duration_sec": duration
        }
