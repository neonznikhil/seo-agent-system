import os
import json
import uuid
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

import httpx

from database import get_supabase, call_nim_llm

logger = logging.getLogger("backend.agents.aeo_agent")


class AEOAgent:
    """4-Module Answer Engine Optimization (AEO) & AI Citation Engine.
    
    Architecture Loop:
    [Target Query] -> [1 LLM Tracking Engine] -> [2 Entity Mapping Engine] -> [3 Answer Formatting Engine (BLUF)] -> [4 Live Schema Injector]
    """

    def __init__(self, website_id: Optional[str] = None):
        self.website_id = website_id

    def _resolve_website_id(self) -> Optional[str]:
        """Fall back to the default connected website when none was given."""
        if self.website_id and self.website_id not in ("default", "all", "", "null", "undefined"):
            return self.website_id
        try:
            from services.website_service import get_default_website_id
            default_id = get_default_website_id()
            if default_id:
                self.website_id = default_id
                return default_id
        except Exception as e:
            logger.debug(f"[AEO] default website lookup note: {e}")
        return self.website_id

    def _get_site(self) -> dict:
        """Fetch the websites row (with local-store fallback) or {}.

        NOTE: live websites table has domain/url/niche but NO name or
        business_name columns — select only what exists, derive the rest.
        """
        wid = self._resolve_website_id()
        if not wid:
            return {}
        try:
            supabase = get_supabase()
            site = supabase.table("websites").select("domain, url, niche").eq("id", wid).single().execute().data
            if site:
                domain = (site.get("domain") or site.get("url") or "").replace("https://", "").replace("http://", "").split("/")[0]
                site["name"] = domain.split(".")[0].capitalize() if domain else ""
                site["business_name"] = site["name"]
                return site
        except Exception as e:
            logger.warning(f"[AEO] Failed to fetch site info: {e}")
        try:
            from services.local_store import get_local_website
            return get_local_website(wid) or {}
        except Exception:
            return {}

    # ---------------------------------------------------------
    # Module 1: LLM Citation Tracking & Share of Voice (SoV)
    # ---------------------------------------------------------
    async def track_buyer_intent_queries(self, queries: List[str]) -> Dict[str, Any]:
        """Query the configured LLM buyer-intent engine and measure brand citation rate.

        Each query is run against NVIDIA NIM (the live answer engine backing
        this pipeline) and optionally cross-checked against live SERP answer
        boxes via Serper. The recorded `llm_name` always names the engine
        that actually ran — never a list of engines that didn't.
        """
        supabase = get_supabase()
        site = self._get_site()
        site_name = site.get("business_name") or site.get("name") or site.get("domain")
        site_domain = (site.get("domain") or site.get("url") or "").replace("https://", "").replace("http://", "").split("/")[0]

        if not site_domain:
            logger.error("Website domain not found for website_id=%s; cannot track AEO citations without site data.", self.website_id)
            return {
                "error": "website_domain_missing",
                "fallback_used": True,
                "message": f"No website domain configured for website_id='{self.website_id}'. Set the domain before tracking AEO citations."
            }

        brand_keywords = [k for k in [(site_name or "").lower(), site_domain.lower()] if k]
        competitors: list = []

        citations_recorded = []
        brand_cited_count = 0
        total_checks = 0

        for q in queries:
            prompt = (
                f"You are an objective expert advisory AI. Answer the following search query directly and list "
                f"the top recommended authoritative resources and solutions for this domain.\n"
                f"Query: {q}\n"
                f"Provide concise, top-tier recommendations."
            )

            engine_used = "nim-nemotron"
            try:
                response_text = await call_nim_llm(prompt=prompt, max_tokens=300)
                if not response_text or not response_text.strip():
                    raise ValueError("empty LLM response")
            except Exception as e:
                logger.warning(f"[AEO] buyer-intent LLM call failed for '{q[:60]}': {e}")
                response_text = ""
                engine_used = "none (llm_unavailable)"

            lower_res = (response_text or "").lower()
            is_brand_cited = bool(response_text) and any(b in lower_res for b in brand_keywords)
            is_competitor_cited = any(c in lower_res for c in competitors) if competitors else False

            # Cross-check: does the brand domain appear in the live SERP answer box / PAA?
            serp_confirmed = False
            if response_text:
                try:
                    from services.serper_service import serper_service
                    serp = await serper_service.search(query=q, num=5, auto_fallback=True)
                    answer_link = ((serp.get("answerBox") or {}).get("link") or "")
                    paa_links = [p.get("link") or "" for p in (serp.get("peopleAlsoAsk") or []) if isinstance(p, dict)]
                    serp_confirmed = bool(site_domain and (site_domain in answer_link or any(site_domain in d for d in paa_links)))
                except Exception as e:
                    logger.debug(f"[AEO] SERP cross-check note: {e}")

            if is_brand_cited:
                brand_cited_count += 1
            total_checks += 1

            row = {
                "id": str(uuid.uuid4()),
                "website_id": self.website_id,
                "query": q,
                "llm_name": engine_used,
                "cited": is_brand_cited,
                "competitor_cited": is_competitor_cited,
                "citation_snippet": ((response_text[:280] + "...") if response_text else "LLM unavailable — SERP cross-check only."),
                "schema_markup": {"serp_confirmed": serp_confirmed},
                "created_at": datetime.now(timezone.utc).isoformat()
            }

            try:
                supabase.table("aeo_citations").insert(row).execute()
                citations_recorded.append(row)
            except Exception as e:
                logger.warning(f"Could not record aeo_citation: {e}")
                citations_recorded.append(row)

        sov_percentage = round((brand_cited_count / max(1, total_checks)) * 100, 1) if total_checks > 0 else 0.0

        return {
            "queries_tracked": total_checks,
            "brand_cited_count": brand_cited_count,
            "sov_percentage": sov_percentage,
            "citations": citations_recorded
        }

    # ---------------------------------------------------------
    # Module 2: Entity Mapping Engine
    # ---------------------------------------------------------
    async def generate_entity_graph(self) -> Dict[str, Any]:
        """Build Organization + WebSite entity graph from the REAL site record.

        Only includes facts read from the websites row / knowledge base —
        no invented addresses, phone numbers, or sameAs links.
        """
        site = self._get_site()
        site_domain = (site.get("domain") or site.get("url") or "").replace("https://", "").replace("http://", "").split("/")[0]

        if not site_domain:
            logger.error("Website domain not found for website_id=%s; cannot track AEO citations without site data.", self.website_id)
            return {
                "error": "website_domain_missing",
                "fallback_used": True,
                "message": f"No website domain configured for website_id='{self.website_id}'. Set the domain before tracking AEO citations."
            }

        site_name = site.get("business_name") or site.get("name") or site_domain
        raw_url = site.get("url") or f"https://{site_domain}"
        site_url = raw_url.rstrip("/")
        niche = site.get("niche") or "professional services"

        # Real secondary facts from the knowledge base (services offered)
        kb_titles: list = []
        try:
            supabase = get_supabase()
            kb_rows = supabase.table("knowledge_base").select("title").eq("website_id", self.website_id).limit(10).execute().data or []
            kb_titles = [r.get("title") for r in kb_rows if r.get("title")][:10]
        except Exception as e:
            logger.debug(f"[AEO] entity KB lookup note: {e}")

        entity_map = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": site_name,
            "url": site_url,
            "description": f"{site_name} — {niche}.",
            "sameAs": [],
        }
        if kb_titles:
            entity_map["knowsAbout"] = kb_titles
        return entity_map

    # ---------------------------------------------------------
    # Module 3: Answer Formatting Engine (BLUF & Conclusion-First)
    # ---------------------------------------------------------
    async def format_bluf_answer(self, raw_content: str, topic: str) -> Dict[str, str]:
        """Rewrite content into conclusion-first, bite-sized direct answers that LLMs love to quote."""
        prompt = (
            f"Rewrite this content into the BLUF (Bottom Line Up Front) format for AI Search engines (Perplexity/ChatGPT).\n"
            f"Topic: {topic}\n\n"
            f"Content: {raw_content[:2000]}\n\n"
            f"Format strictly required:\n"
            f"1. Direct Answer (under 40 words, definitive)\n"
            f"2. Core Key Facts (3 bullet points with statutory numbers)\n"
            f"3. 2-Column Comparison / Eligibility Criteria\n"
            f"4. Actionable Next Step"
        )
        bluf_output = await call_nim_llm(prompt=prompt, max_tokens=600)
        return {
            "topic": topic,
            "bluf_formatted": bluf_output,
            "format": "BLUF-Conclusion-First"
        }

    # ---------------------------------------------------------
    # Module 4: Live Schema Injector
    # ---------------------------------------------------------
    async def generate_and_inject_schema(self, blog_id: Optional[str], schema_type: str = "FAQPage") -> Dict[str, Any]:
        """Generate structured JSON-LD from the REAL article content and stage it.

        Reads the content_log article (by id, or the latest published one),
        extracts genuine reader questions via NIM, and returns FAQPage JSON-LD
        built strictly from that article — never a hardcoded template.
        Also flags content_log.schema_injected so the pipeline stays honest.
        """
        import json as _json
        supabase = get_supabase()

        row = None
        try:
            if blog_id:
                row = supabase.table("content_log").select("id, title, content, keyword, website_id").eq("id", blog_id).maybe_single().execute().data
            else:
                # Prefer latest published article; fall back to the latest
                # substantial draft (schema is generated FROM content —
                # publish state only gates injection, not generation).
                q = supabase.table("content_log").select("id, title, content, keyword, website_id").eq("status", "published")
                if self.website_id:
                    q = q.eq("website_id", self.website_id)
                rows = q.order("created_at", desc=True).limit(1).execute().data or []
                row = rows[0] if rows else None
                if not row or not (row.get("content") or "").strip():
                    q2 = supabase.table("content_log").select("id, title, content, keyword, website_id")
                    if self.website_id:
                        q2 = q2.eq("website_id", self.website_id)
                    for cand in (q2.order("created_at", desc=True).limit(10).execute().data or []):
                        if cand.get("content") and len(cand["content"]) > 500 and "draft:" not in (cand.get("title") or "").lower():
                            row = cand
                            break
                    else:
                        row = None
                # Local-store fallback: this deployment keeps the article
                # corpus in local JSON (data/content_log.json) — use the
                # latest substantial article the same way.
                if not row or not (row.get("content") or "").strip():
                    try:
                        from services.local_store import list_local_content, list_local_approvals
                        for cand in (list_local_content(self.website_id) or []) + (list_local_approvals(self.website_id) or []):
                            text = cand.get("content") or cand.get("final_html") or cand.get("html") or ""
                            title = (cand.get("title") or "")
                            if text and len(text) > 500 and "draft:" not in title.lower():
                                row = {"id": cand.get("id"), "title": title,
                                       "content": text, "keyword": cand.get("keyword") or cand.get("topic") or "",
                                       "website_id": self.website_id, "_local": True}
                                break
                    except Exception as e:
                        logger.debug(f"[AEO] local article fallback note: {e}")
        except Exception as e:
            logger.warning(f"[AEO] article lookup failed: {e}")

        if not row or not (row.get("content") or "").strip():
            return {"error": "article_missing", "fallback_used": True,
                    "message": "No article content found to generate schema from."}

        from bs4 import BeautifulSoup as _Soup
        article_text = _Soup(row["content"], "html.parser").get_text()[:4000]
        prompt = (
            "Read this article and extract 4-6 REAL questions a reader would ask, each answered "
            "in 40-60 words using facts strictly from the article.\n\nARTICLE:\n" + article_text + "\n\n"
            'Return ONLY valid JSON: {"mainEntity": [{"name": "Question?", "acceptedAnswer": {"text": "Answer"}}]}'
        )
        try:
            raw = await call_nim_llm(prompt, system="Return only valid JSON.", max_tokens=1200,
                                     temperature=0.4, fail_silently=False)
        except Exception as e:
            return {"error": "llm_failed", "fallback_used": True,
                    "message": f"FAQ extraction LLM call failed: {e}"}
        cleaned = (raw or "").strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0]
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0]
        # Narrow to the outermost JSON object (drops chatty pre/postamble)
        try:
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                cleaned = cleaned[start:end + 1]
        except Exception:
            pass
        entities: list = []
        try:
            parsed = _json.loads(cleaned.strip())
            if isinstance(parsed, dict):
                entities = parsed.get("mainEntity", []) or []
            if not entities:
                raise ValueError("empty mainEntity")
        except Exception:
            # Tolerant fallback: pull "name"/"text" pairs straight out of
            # the (slightly malformed) model output instead of failing.
            import re as _re2
            names = _re2.findall(r'"name"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
            texts = _re2.findall(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
            for n, t in zip(names, texts):
                try:
                    q = _json.loads(f'"{n}"')
                    a = _json.loads(f'"{t}"')
                except Exception:
                    q, a = n, t
                if q and a:
                    entities.append({"name": q, "acceptedAnswer": {"text": a}})
            if not entities:
                return {"error": "invalid_llm_json", "fallback_used": True,
                        "message": "Model returned invalid FAQ JSON and no Q/A pairs could be recovered."}

        schema_json = {
            "@context": "https://schema.org",
            "@type": schema_type,
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": q.get("name", ""),
                    "acceptedAnswer": {"@type": "Answer", "text": q.get("acceptedAnswer", {}).get("text", "")},
                }
                for q in entities
                if q.get("name") and q.get("acceptedAnswer", {}).get("text")
            ],
        }
        if not schema_json["mainEntity"]:
            return {"error": "empty_schema", "fallback_used": True,
                    "message": "No valid Q/A pairs extracted from the article."}

        # Stage the flag on the real content row (best-effort; column comes from the AEO migration)
        try:
            supabase.table("content_log").update({"schema_injected": True}).eq("id", row["id"]).execute()
        except Exception as e:
            logger.debug(f"[AEO] schema_injected flag note: {e}")
        # Sync a reader-facing description onto the blogs row when present (best-effort)
        try:
            supabase.table("blogs").update({
                "meta_description": f"{(row.get('title') or '')[:90]} — FAQ schema ready"
            }).eq("website_id", row.get("website_id") or self.website_id).eq("title", row.get("title") or "").execute()
        except Exception as e:
            logger.debug(f"[AEO] blogs meta sync note: {e}")

        return {
            "success": True,
            "blog_id": row["id"],
            "article_title": row.get("title"),
            "schema_type": schema_type,
            "schema_json": schema_json,
            "injected_into": "content_log.schema_injected flag + returned JSON-LD (inject via /api/aeo/inject-schema)",
            "message": f"Generated {schema_type} JSON-LD from '{(row.get('title') or '')[:60]}' ({len(schema_json['mainEntity'])} questions).",
        }
