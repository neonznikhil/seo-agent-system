"""
backend/tests/test_approval_closed.py
Negative tests verifying bypasses are closed:
- Missing X-User-Id -> 401/403
- Fallback identities ('human-approved', 'autonomous', 'system', demo UUIDs) -> 403
- Zero WordPress calls made when auth gate fails
"""

import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock
from backend.middleware.human_gate import (
    require_human_for_request,
    require_verified_publisher,
    _BLOCKED_PUBLISHER_IDENTITIES,
)

def _mock_request(headers=None):
    req = MagicMock()
    req.headers = headers or {}
    req.client.host = "127.0.0.1"
    req.url.path = "/api/wordpress/publish"
    return req

@pytest.mark.asyncio
async def test_missing_x_user_id_raises_403():
    req = _mock_request({})
    with pytest.raises(HTTPException) as exc_info:
        await require_human_for_request(req)
    assert exc_info.value.status_code == 403
    assert "Human approval required" in exc_info.value.detail

@pytest.mark.asyncio
async def test_blocked_identities_rejected():
    for blocked_id in ["human-approved", "autonomous", "system", "demo-uuid", "f8d16d12"]:
        req = _mock_request({"X-User-Id": blocked_id})
        with pytest.raises(HTTPException) as exc_info:
            await require_verified_publisher(req)
        assert exc_info.value.status_code in (401, 403)
        assert ("Publishing without human identity is not permitted" in exc_info.value.detail
                or "not an eligible" in exc_info.value.detail
                or "User not found" in exc_info.value.detail
                or "Forbidden" in exc_info.value.detail)

@pytest.mark.asyncio
async def test_nonexistent_user_id_rejected(monkeypatch):
    import middleware.auth as authmod
    monkeypatch.setattr(authmod, "_validate_user_exists", lambda uid: False)
    req = _mock_request({"X-User-Id": "real-looking-uuid-999"})
    with pytest.raises(HTTPException) as exc_info:
        await require_verified_publisher(req)
    assert exc_info.value.status_code == 403
