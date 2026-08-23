import asyncio
import json
import logging
import httpx

from backend.main import app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_api_endpoints")


async def main():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        # 1. Health check
        res_health = await client.get("/api/health")
        logger.info(f"/api/health status: {res_health.status_code}, data: {res_health.json()}")
        assert res_health.status_code == 200, "Health check must return 200"

        # 2. SEO Agent Group Status
        res_seo = await client.get("/api/seo-agent-group/status")
        logger.info(f"/api/seo-agent-group/status: {res_seo.status_code}")
        assert res_seo.status_code == 200, "SEO status must return 200"
        seo_data = res_seo.json()
        assert len(seo_data["agent_states"]) == 7, "All 7 agents must be present"

        # 3. Serper Connector Status
        res_serper = await client.get("/connector/serper/status")
        logger.info(f"/connector/serper/status: {res_serper.status_code}, data: {res_serper.json()}")
        assert res_serper.status_code == 200, "Serper status must return 200"

        # 4. Serper Toggle
        res_toggle = await client.post("/connector/serper/toggle", json={"enabled": True})
        logger.info(f"/connector/serper/toggle: {res_toggle.status_code}, data: {res_toggle.json()}")
        assert res_toggle.status_code == 200, "Serper toggle must return 200"

        # 5. Serper Search Endpoint
        res_search = await client.post("/connector/serper/search", json={"query": "Houston car accident attorney"})
        logger.info(f"/connector/serper/search: {res_search.status_code}, source: {res_search.json().get('source')}")
        assert res_search.status_code == 200, "Serper search must return 200"

        # 6. Serper News Endpoint
        res_news = await client.post("/connector/serper/news", json={"query": "Texas legal trends"})
        logger.info(f"/connector/serper/news: {res_news.status_code}, total_results: {res_news.json().get('total_results')}")
        assert res_news.status_code == 200, "Serper news must return 200"

    logger.info("\n✅ ALL PRODUCTION API ENDPOINTS VALIDATED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(main())
