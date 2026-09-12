import sys
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_demo_flow_endpoint_execution():
    mock_blog_res = {
        "title": "How to Calculate Car Accident Pain and Suffering",
        "seo_score": 92,
        "word_count": 1250,
        "final_html": "<h1>How to Calculate Car Accident Pain and Suffering</h1><p>Content</p>",
    }

    # Patch both module namespaces so mocks bind whether main.py imports via 'routers.demo' or 'backend.routers.demo'
    patch_modules = [m for m in ["routers.demo", "backend.routers.demo"] if m in sys.modules]
    if not patch_modules:
        patch_modules = ["routers.demo"]

    async_pick = AsyncMock(return_value="how to calculate car accident compensation for pain and suffering")
    async_writer = AsyncMock(return_value=mock_blog_res)

    patches = []
    for mod_name in patch_modules:
        patches.append(patch(f"{mod_name}.ai_pick_best_keyword", new=async_pick))
        patches.append(patch(f"{mod_name}.run_crew_blog_writer_with_retry", new=async_writer))

    for p in patches:
        p.start()

    try:
        res = client.post("/api/demo/run-full-flow?website_id=default")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "demo_complete"
        assert data["article_in_approvals"] is True
        assert "/approvals" in data["approvals_url"]
        steps = data.get("steps", [])
        assert len(steps) >= 3
        assert any(s["step"] == "article_generation" and s["status"] == "done" for s in steps)
    finally:
        for p in patches:
            p.stop()

