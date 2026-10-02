"""Regression tests: authentication and credential-handling security fixes.

Original bugs, all verified by reading the call sites:
  * middleware/auth.py::_validate_user_exists returned `user_id == DEFAULT_ACCOUNT_ID`
    from its `except` block. During a Supabase outage EVERY request carrying
    `X-User-Id: a0000000-0000-0000-0000-000000000001` was admitted as the admin
    account (fail-open), while a valid non-default user got a permanent 403
    "Account not found".
  * WordPress + Google OAuth tokens were written to the DB in PLAINTEXT and echoed
    back in API responses, so any DB read, backup, dump, or proxy/CDN log yielded
    live credentials.
  * The WordPress Application-Password callback had NO CSRF/state validation,
    accepted credentials via GET query parameters, swallowed the write failure, and
    reported success unconditionally.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

import middleware.auth as authmod
import middleware.human_gate as gate
import routers.oauth_connectors as oauth
from services.wordpress_service import (
    decrypt_token_field,
    encrypt_token_field,
    _looks_encrypted,
)


ADMIN = "a0000000-0000-0000-0000-000000000001"
OTHER = "11111111-2222-3333-4444-555555555555"


def _supabase_returning(*payloads):
    """Supabase double whose queries return the given .data payloads in order."""
    results = list(payloads)

    class _T:
        def select(self, *a, **k):
            return self

        def eq(self, *a, **k):
            return self

        def limit(self, *a, **k):
            return self

        def update(self, *a, **k):
            return self

        def upsert(self, *a, **k):
            return self

        def insert(self, *a, **k):
            return self

        def execute(self):
            data = results.pop(0) if results else []
            r = MagicMock()
            r.data = data
            return r

    sup = MagicMock()
    sup.table = lambda *a, **k: _T()
    return sup


# --------------------------------------------------- auth fails closed

def test_outage_does_not_admit_the_default_admin_id():
    """The core vulnerability: fail-open admitted the admin id."""
    with patch.object(authmod, "get_supabase", side_effect=httpx.ConnectError(
            "name or service not known")):
        with pytest.raises(httpx.ConnectError):
            authmod._validate_user_exists(ADMIN)


def test_genuine_not_found_returns_false_in_production(monkeypatch):
    """A real lookup miss must be False — it used to be True for the admin id."""
    monkeypatch.setattr(authmod, "IS_PRODUCTION", True)
    with patch.object(authmod, "get_supabase", return_value=_supabase_returning([], [], [])):
        assert authmod._validate_user_exists(ADMIN) is False


def test_found_user_returns_true():
    with patch.object(authmod, "get_supabase", return_value=_supabase_returning([{"id": OTHER}])):
        assert authmod._validate_user_exists(OTHER) is True


def test_non_connectivity_error_fails_closed_in_production(monkeypatch):
    """A missing table must not become an admin grant in production."""
    monkeypatch.setattr(authmod, "IS_PRODUCTION", True)
    sup = _supabase_returning()
    sup.table = MagicMock(side_effect=RuntimeError("relation does not exist"))
    with patch.object(authmod, "get_supabase", return_value=sup):
        assert authmod._validate_user_exists(ADMIN) is False


def test_human_gate_denies_with_403_when_store_unreachable():
    """Gates must fail closed with a denial, not crash with a 500 or admit."""
    with patch.object(authmod, "_validate_user_exists",
                      side_effect=httpx.ConnectError("name or service not known")):
        with pytest.raises(HTTPException) as exc:
            gate._identity_exists(ADMIN)
    assert exc.value.status_code == 403


def test_human_gate_allows_a_verified_identity():
    with patch.object(authmod, "_validate_user_exists", return_value=True):
        assert gate._identity_exists(OTHER) is True


# --------------------------------------------------- token encryption

def test_oauth_token_is_never_stored_in_plaintext():
    token = "wp-live-token-abc123"
    enc = encrypt_token_field(token)
    assert enc != token
    assert token not in enc
    assert _looks_encrypted(enc)


def test_token_decrypt_roundtrip():
    token = "wp-live-token-abc123"
    assert decrypt_token_field(encrypt_token_field(token)) == token


def test_legacy_plaintext_rows_still_readable():
    """Upgrading must not silently disconnect every existing WordPress site."""
    assert decrypt_token_field("legacy-plaintext-token") == "legacy-plaintext-token"


def test_none_and_double_encrypt_are_safe():
    assert encrypt_token_field(None) is None
    assert decrypt_token_field(None) is None
    once = encrypt_token_field("t")
    assert encrypt_token_field(once) == once


# --------------------------------------------------- WP CSRF state

def test_wp_state_roundtrip():
    state = oauth._wp_state(OTHER)
    assert oauth._verify_wp_state(state) == OTHER


@pytest.mark.parametrize("state", [
    None,                     # missing
    "",                        # empty
    "garbage",                 # malformed
    "a.b.c",                   # malformed parts
    "x",                       # single segment
])
def test_wp_state_rejects_missing_or_malformed(state):
    assert oauth._verify_wp_state(state) is None


def test_wp_state_rejects_swapped_website_id():
    """An attacker must not be able to retarget the state at another site."""
    state = oauth._wp_state(OTHER)
    _, ts, sig = state.split(".")
    forged = f"{ADMIN}.{ts}.{sig}"
    assert oauth._verify_wp_state(forged) is None


def test_wp_state_rejects_forged_signature():
    state = oauth._wp_state(OTHER)
    _, ts, _ = state.split(".")
    assert oauth._verify_wp_state(f"{OTHER}.{ts}.deadbeefdeadbeef") is None


def test_wp_state_expires():
    assert oauth._verify_wp_state(oauth._wp_state(OTHER, issued_at=0)) is None


@pytest.mark.asyncio
async def test_wp_callback_rejects_missing_state():
    """No state => no CSRF protection => must not store or report success."""
    out = await oauth.wp_app_password_callback(
        user_login="attacker", password="hunter2", website_id=OTHER, state=None
    )
    body = out if isinstance(out, str) else getattr(out, "body", b"")
    assert b"success" in body.lower() or b"state" in body.lower()
    assert b"Application Password authorized and stored encrypted" not in body


@pytest.mark.asyncio
async def test_wp_callback_reports_failure_when_write_fails():
    """A swallowed write previously produced a green popup for nothing stored."""
    sup = _supabase_returning(None)
    sup.table = MagicMock(side_effect=RuntimeError("PGRST204 unknown column"))
    state = oauth._wp_state(OTHER)
    with patch.object(oauth, "get_supabase", return_value=sup):
        out = await oauth.wp_app_password_callback(
            user_login="u", password="p", website_id=OTHER, state=state
        )
    body = out if isinstance(out, str) else getattr(out, "body", b"")
    assert b"Application Password authorized and stored encrypted" not in body
