"""Regression tests: connector endpoints must never fabricate a "connected" result.

The original bugs were:
  * NVIDIA verification used GET /v1/models, a public catalog endpoint that
    returns HTTP 200 for any (or no) key, so every key looked "Connected".
  * Supabase verification treated a non-empty anon key as proof of connection.
"""

from unittest.mock import AsyncMock, patch

import os

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from routers.connectors import verify_nvidia_key, verify_serper_key
import routers.connectors as connectors_mod


class _Resp:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_verified_supabase_creds_are_adopted_without_restart(monkeypatch):
    """Saving working creds must take effect in the live process immediately.

    Regression: save-all/setup-supabase only wrote .env, so the running app kept
    using the old (or placeholder) client until someone restarted the backend.
    """
    monkeypatch.setenv("SUPABASE_URL", "https://old.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "old-key")

    with patch.object(connectors_mod, "_probe_supabase", new=AsyncMock(return_value=(True, "ok"))), \
         patch.object(connectors_mod, "write_env_file", return_value={"keys_set": []}):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post("/api/connectors/save-all", json={
                "supabase_url": "https://new.supabase.co",
                "supabase_anon_key": "new-anon",
                "supabase_service_key": "new-service",
            })
    assert res.status_code == 200
    assert os.environ["SUPABASE_URL"] == "https://new.supabase.co"
    assert os.environ["SUPABASE_SERVICE_ROLE_KEY"] == "new-service"


@pytest.mark.asyncio
async def test_unverified_supabase_creds_never_poison_live_process(monkeypatch):
    """A credential that fails its live probe must not replace a working one."""
    monkeypatch.setenv("SUPABASE_URL", "https://good.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "good-key")

    with patch.object(connectors_mod, "_probe_supabase", new=AsyncMock(return_value=(False, "401"))), \
         patch.object(connectors_mod, "write_env_file", return_value={"keys_set": []}):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post("/api/connectors/save-all", json={
                "supabase_url": "https://bogus.supabase.co",
                "supabase_service_key": "bogus-key",
            })
    assert res.status_code == 200
    assert os.environ["SUPABASE_URL"] == "https://good.supabase.co"
    assert os.environ["SUPABASE_SERVICE_ROLE_KEY"] == "good-key"


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


@pytest.mark.asyncio
async def test_serper_rejected_key_is_not_connected():
    """A non-empty Serper key that the API rejects must report not-connected."""
    async def fake_post(self, url, headers=None, json=None):
        assert "serper.dev" in url
        return _Resp(403, {"message": "Unauthorized."})

    with patch("httpx.AsyncClient.post", new=fake_post):
        connected, message = await verify_serper_key("bogus-key", use_cache=False)
    assert connected is False
    assert "401/403" in message or "rejected" in message.lower()


@pytest.mark.asyncio
async def test_serper_valid_key_connects():
    async def fake_post(self, url, headers=None, json=None):
        return _Resp(200, {"organic": [{"title": "x", "link": "https://example.com"}]})

    with patch("httpx.AsyncClient.post", new=fake_post):
        connected, message = await verify_serper_key("good-key", use_cache=False)
    assert connected is True


@pytest.mark.asyncio
async def test_serper_empty_key_is_not_connected():
    connected, _ = await verify_serper_key("", use_cache=False)
    assert connected is False
