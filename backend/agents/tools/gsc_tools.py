import logging
from typing import List, Dict
import json

from ...database import get_supabase

logger = logging.getLogger("backend.tools.gsc")


def _log_proof(website_id: str, agent: str, tool: str, real_api: str, action: str) -> None:
    try:
        get_supabase().table("tasks").insert({
            "website_id": website_id,
            "action": f"proof:{agent}:{tool}:{action}",
            "status": "success",
            "error": json.dumps({"real_api_called": real_api}),
            "created_at": __import__("datetime").datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass


def fetch_active_keywords(website_id: str, limit: int = 20) -> List[Dict]:
    try:
        from googleapiclient.discovery import build
        from google.oauth2 import service_account
        import os
        from datetime import datetime, timedelta
        from ...config import GSC_CREDENTIALS_PATH
        creds = service_account.Credentials.from_service_account_file(
            GSC_CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
        )
        service = build("searchconsole", "v1", credentials=creds)
        site = get_supabase().table("websites").select("gsc_property").eq("id", website_id).single().execute().data
        property_url = site.get("gsc_property") if site else None
        if not property_url:
            raise ValueError("GSC property not set")
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")
        request = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["query"],
            "rowLimit": limit,
        }
        response = service.searchanalytics().query(siteUrl=property_url, body=request).execute()
        rows = response.get("rows", [])
        keywords = []
        for row in rows:
            kw = row["keys"][0]
            clicks = row.get("clicks", 0)
            impressions = row.get("impressions", 0)
            ctr = row.get("ctr", 0)
            keywords.append({
                "query": kw,
                "impressions": impressions,
                "ctr": ctr,
                "clicks": clicks,
            })
        _log_proof(website_id, "gsc_agent", "fetch_active_keywords", "gsc", "query")
        logger.info("Fetched %d active keywords from GSC", len(keywords))
        return keywords
    except Exception as e:
        logger.error("GSC fetch failed: %s", e)
        _log_proof(website_id, "gsc_agent", "fetch_active_keywords", "error", str(e))
        return []
