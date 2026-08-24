import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock, AsyncMock
from backend.main import app
from backend.routers.oauth_connectors import set_oauth_state, get_and_validate_oauth_state


@pytest.mark.asyncio
async def test_slack_oauth_start():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/connectors/slack/oauth/start?website_id=test_site", follow_redirects=False)
        assert res.status_code == 307
        assert "slack.com/oauth/v2/authorize" in res.headers["location"]
        assert "state=" in res.headers["location"]


@pytest.mark.asyncio
async def test_oauth_state_validation():
    state_id = "test-state-123"
    set_oauth_state(state_id, {"website_id": "test_site"}, ttl_sec=60)
    data = get_and_validate_oauth_state(state_id)
    assert data is not None
    assert data["website_id"] == "test_site"

    # Consuming second time should return None (one-time use)
    assert get_and_validate_oauth_state(state_id) is None


@pytest.mark.asyncio
async def test_wordpress_url_verify():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/connectors/wordpress/verify-url?site_url=https://accident.innovatcs.com")
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") is True
        assert "authorize_deep_link" in data



