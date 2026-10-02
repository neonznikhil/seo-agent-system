"""Regression tests: integration endpoints that were hard-broken (500) or lied.

The original bugs, all verified by reading the call sites:
  * SerperService.verify_key was *never defined* — both
    POST /connectors/serper/save-key and POST /connectors/serper/verify raised
    AttributeError, so the primary Serper onboarding endpoint was a hard 500.
  * DELETE /api/wordpress/disconnect did `await disconnect(...)` on a plain
    sync `def`, so it raised TypeError and never deleted the row.
  * GET /api/wordpress/test called the async `test_wp_connection` without await,
    passing a coroutine into a Pydantic `dict` field -> ValidationError -> 500,
    and it hardcoded ok=True before the connection was ever tested.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.serper_service import SerperService, serper_service
import routers.wordpress_connect as wp_connect_mod


# ---------------------------------------------------------------- Serper

def test_serper_verify_key_exists_and_is_async():
    """The method must exist and be awaitable — this was the whole outage."""
    import inspect

    assert hasattr(serper_service, "verify_key"), "verify_key is missing"
    assert inspect.iscoroutinefunction(SerperService.verify_key)


@pytest.mark.asyncio
async def test_verify_key_rejects_blank_without_network():
    svc = SerperService()
    assert await svc.verify_key("") is False
    assert await svc.verify_key("abc") is False


@pytest.mark.asyncio
async def test_verify_key_false_on_401_not_raise():
    svc = SerperService()

    resp = MagicMock()
    resp.status_code = 401
    ctx = AsyncMock()
    ctx.post.return_value = resp
    client = AsyncMock()
    client.__aenter__.return_value = ctx

    with patch("services.serper_service.httpx.AsyncClient", return_value=client):
        assert await svc.verify_key("bad-key-but-long-enough") is False


@pytest.mark.asyncio
async def test_verify_key_true_on_200_and_resets_circuit():
    """A valid key must clear a tripped breaker, else saving it appears to do nothing."""
    svc = SerperService()
    svc._record_circuit_failure()
    svc._record_circuit_failure()
    svc._record_circuit_failure()
    assert svc.is_circuit_open() is True

    resp = MagicMock()
    resp.status_code = 200
    ctx = AsyncMock()
    ctx.post.return_value = resp
    client = AsyncMock()
    client.__aenter__.return_value = ctx

    with patch("services.serper_service.httpx.AsyncClient", return_value=client):
        assert await svc.verify_key("good-key-value-here") is True

    assert svc.is_circuit_open() is False


@pytest.mark.asyncio
async def test_verify_key_reraises_connectivity_so_route_can_503():
    """A network outage must NOT be reported as 'invalid API key'."""
    import httpx

    svc = SerperService()
    client = AsyncMock()
    client.__aenter__.side_effect = httpx.ConnectError("name or service not known")

    with patch("services.serper_service.httpx.AsyncClient", return_value=client):
        with pytest.raises(httpx.ConnectError):
            await svc.verify_key("some-candidate-key")


# ------------------------------------------------------- WordPress connect

@pytest.mark.asyncio
async def test_disconnect_is_not_awaited_on_sync_def(monkeypatch):
    """disconnect is a sync def; awaiting it raised TypeError -> 500."""
    import inspect

    assert not inspect.iscoroutinefunction(wp_connect_mod.disconnect)

    calls = []
    monkeypatch.setattr(
        wp_connect_mod, "disconnect", lambda uid: calls.append(uid)
    )
    monkeypatch.setattr(wp_connect_mod, "_get_user_id", lambda req: "user-1")

    request = MagicMock()
    request.headers = {"X-User-Id": "user-1"}

    result = await wp_connect_mod.disconnect_wp(request)

    assert result == {"disconnected": True}
    assert calls == ["user-1"]


@pytest.mark.asyncio
async def test_wp_test_awaits_connection_check_and_reports_failure(monkeypatch):
    """A failing WordPress check must yield ok=False, not a hardcoded ok=True."""
    monkeypatch.setattr(
        wp_connect_mod,
        "get_connection",
        lambda uid: {"site_url": "https://x.example", "wp_username": "u",
                     "encrypted_password": "enc"},
    )
    monkeypatch.setattr(wp_connect_mod, "decrypt", lambda v: "secret")

    async def _boom(*_a, **_k):
        raise RuntimeError("WordPress connection test failed")

    monkeypatch.setattr(wp_connect_mod, "test_wp_connection", _boom)

    request = MagicMock()
    request.headers = {"X-User-Id": "user-1"}

    res = await wp_connect_mod.test_connection(request)

    assert res.ok is False
    assert "WordPress connection test failed" in (res.error or "")


@pytest.mark.asyncio
async def test_wp_test_returns_real_user_info(monkeypatch):
    """Success path must pass a real dict (awaited), not a coroutine."""
    monkeypatch.setattr(
        wp_connect_mod,
        "get_connection",
        lambda uid: {"site_url": "https://x.example", "wp_username": "u",
                     "encrypted_password": "enc"},
    )
    monkeypatch.setattr(wp_connect_mod, "decrypt", lambda v: "secret")

    async def _ok(*_a, **_k):
        return {"id": 7, "name": "admin", "roles": ["administrator"]}

    monkeypatch.setattr(wp_connect_mod, "test_wp_connection", _ok)

    request = MagicMock()
    request.headers = {"X-User-Id": "user-1"}

    res = await wp_connect_mod.test_connection(request)

    assert res.ok is True
    assert res.user_info == {"id": 7, "name": "admin", "roles": ["administrator"]}
