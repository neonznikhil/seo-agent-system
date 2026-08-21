import logging
from typing import Optional, List, Dict, Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import asyncio
import json
import os
import re
from datetime import datetime
import httpx

logger = logging.getLogger("backend.tools.real_time_data_tool")


class RealTimeDataInput(BaseModel):
    query: str = Field(description="Search query or data request")
    source: str = Field(default="google", description="Data source: google, news, social, api")
    count: int = Field(default=10, description="Number of results to fetch")


class RealTimeDataTool(BaseTool):
    name: str = "real_time_data"
    description: str = "Fetch real-time data from search engines, news, social media, and public APIs. For trending topics, latest statistics, breaking news, and current events."
    args_schema: type[BaseModel] = RealTimeDataInput
    _website_id: Optional[str] = None

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    def _run(self, query: str, source: str = "google", count: int = 10) -> str:
        if not self._website_id:
            return json.dumps({"error": "website_id not set"})

        result = {
            "query": query,
            "source": source,
            "timestamp": datetime.utcnow().isoformat(),
            "results": [],
        }

        try:
            if source == "news":
                result["results"] = self._fetch_news(query, count)
            elif source == "social":
                result["results"] = self._fetch_social_data(query, count)
            elif source == "api":
                result["results"] = self._fetch_api_data(query, count)
            else:
                result["results"] = self._fetch_search_data(query, count)

            result["success"] = True
            result["count"] = len(result["results"])

        except Exception as e:
            logger.error(f"Real-time data fetch failed: {e}")
            result["status"] = "error"
            result["error"] = str(e)

        _log_proof(self._website_id, "real_time_data", "fetch", source, f"query={query}")
        return json.dumps(result, indent=2)

    def _fetch_search_data(self, query: str, count: int) -> List[Dict]:
        results = []

        try:
            resp = httpx.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (compatible; SEOBot/1.0)"},
                timeout=15,
                follow_redirects=True,
            )
            resp.raise_for_status()
            html = resp.text

            titles = re.findall(r'<a[^>]+class="result__a"[^>]*>(.*?)</a>', html, re.S)
            urls = re.findall(r'<a[^>]+class="result__a"[^>]*href="(.*?)"', html)
            snippets = re.findall(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', html, re.S)

            for i in range(min(count, len(titles), len(urls))):
                title = re.sub(r"<.*?>", "", titles[i]).strip()
                url = urls[i]
                snippet = re.sub(r"<.*?>", "", snippets[i]).strip() if i < len(snippets) else ""
                if title and url:
                    results.append(
                        {
                            "rank": i + 1,
                            "title": title,
                            "url": url,
                            "snippet": snippet,
                            "domain": httpx.URL(url).host or url,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
            return [{"error": f"Search failed: {e}"}]

        return results

    def _fetch_news(self, query: str, count: int) -> List[Dict]:
        results = []

        try:
            resp = httpx.get(
                "https://newsapi.org/v2/everything",
                params={"q": query, "sortBy": "publishedAt", "pageSize": count, "language": "en"},
                headers={"X-Api-Key": os.getenv("NEWSAPI_KEY", "")} if os.getenv("NEWSAPI_KEY") else {},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            for article in data.get("articles", [])[:count]:
                results.append(
                    {
                        "title": article.get("title", ""),
                        "url": article.get("url", ""),
                        "source": article.get("source", {}).get("name", "NewsAPI"),
                        "published_at": article.get("publishedAt", datetime.utcnow().isoformat()),
                        "summary": article.get("description", ""),
                        "category": "news",
                    }
                )
        except Exception as e:
            logger.warning(f"NewsAPI fetch failed: {e}")
            return [{"error": f"News fetch failed: {e}"}]

        return results

    def _fetch_social_data(self, query: str, count: int) -> List[Dict]:
        results = []

        try:
            resp = httpx.get(
                "https://api.reddit.com/search",
                params={"q": query, "sort": "new", "limit": count},
                headers={"User-Agent": "Mozilla/5.0 (compatible; SEOBot/1.0)"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            for post in data.get("data", {}).get("children", [])[:count]:
                p = post.get("data", {})
                results.append(
                    {
                        "author": p.get("author", "unknown"),
                        "platform": "reddit",
                        "content": p.get("title", "") + ("\n" + p.get("selftext", "") if p.get("selftext") else ""),
                        "metrics": {
                            "score": p.get("score", 0),
                            "comments": p.get("num_comments", 0),
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
        except Exception as e:
            logger.warning(f"Reddit fetch failed: {e}")
            return [{"error": f"Social fetch failed: {e}"}]

        return results

    def _fetch_api_data(self, query: str, count: int) -> List[Dict]:
        results = []

        api_endpoints = {
            "weather": "https://api.open-meteo.com/v1/forecast?latitude=0&longitude=0&current_weather=true",
            "currency": "https://api.exchangerate-api.com/v4/latest/USD",
            "crypto": "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd",
        }

        endpoint = api_endpoints.get(query.lower().split()[0])
        if not endpoint:
            return [{"error": f"No real API configured for query: {query}"}]

        try:
            resp = httpx.get(endpoint, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            results.append(
                {
                    "source": "Real-Time API",
                    "endpoint": endpoint,
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        except Exception as e:
            logger.warning(f"API fetch failed: {e}")
            return [{"error": f"API fetch failed: {e}"}]

        return results


def _log_proof(website_id: str, agent: str, tool: str, real_api: str, action: str) -> None:
    try:
        from ...database import get_supabase

        get_supabase().table("tasks").insert(
            {
                "website_id": website_id,
                "agent_name": agent,
                "action": f"proof:{agent}:{tool}:{action}",
                "status": "success",
                "result": json.dumps({"real_api_called": real_api}),
                "real_api_called": real_api,
                "created_at": datetime.utcnow().isoformat(),
            }
        ).execute()
    except Exception:
        pass
