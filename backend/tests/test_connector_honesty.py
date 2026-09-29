"""Regression tests: connector endpoints must never fabricate a "connected" result.

The original bugs were:
  * NVIDIA verification used GET /v1/models, a public catalog endpoint that
    returns HTTP 200 for any (or no) key, so every key looked "Connected".
  * Supabase verification treated a non-empty anon key as proof of connection.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from routers.connectors import verify_nvidia_key


class _Resp:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_nvidia_bogus_key_is_rejected():
    async def fake_post(self, url, headers=None, json=None):
        assert "chat/completions" in url
        return _Resp(403)

    with patch("httpx.AsyncClient.post", new=fake_post):
        connected, message, models = await verify_nvidia_key("nvapi-bogus")
    assert connected is False
    assert models == 0
    assert "Invalid" in message


@pytest.mark.asyncio
async def test_nvidia_valid_key_connects():
    calls = {"post": 0, "get": 0}

    async def fake_post(self, url, headers=None, json=None):
        calls["post"] += 1
        return _Resp(200)

    async def fake_get(self, url, headers=None):
        calls["get"] += 1
        return _Resp(200, {"data": [{"id": "m1"}, {"id": "m2"}]})

    with patch("httpx.AsyncClient.post", new=fake_post), patch("httpx.AsyncClient.get", new=fake_get):
        connected, message, models = await verify_nvidia_key("nvapi-real")
    assert connected is True
    assert models == 2
    assert calls["post"] == 1


@pytest.mark.asyncio
async def test_nvidia_empty_key_is_not_connected():
    connected, _, models = await verify_nvidia_key("")
    assert connected is False
    assert models == 0


@pytest.mark.asyncio
async def test_supabase_bogus_url_reports_not_connected():
    """A non-empty anon key must not be treated as a working connection."""
    async def unreachable(self, *args, **kwargs):
        raise OSError("Name or service not known")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("httpx.AsyncClient.get", new=unreachable):
            res = await client.post(
                "/api/connectors/test-supabase",
                json={"supabase_url": "https://bogus.supabase.co", "anon_key": "bogus"},
            )
    assert res.status_code == 200
    data = res.json()
    assert data["connected"] is False
    assert data["status"] == "failed"
