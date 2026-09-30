"""Regression tests for GA4 / Search Console credential handling.

The original bugs:
  * The Connectors UI saved the pasted service-account JSON as
    ``GA4_CREDENTIALS_JSON`` / ``GSC_SERVICE_ACCOUNT_JSON``, but the services
    only read ``*_CREDENTIALS_PATH`` (a file path). A successful save was
    therefore never used and the connector always reported "not configured".
  * ``sync-gsc`` imported ``sync_gsc_data`` from ``services.gsc_service`` while
    it actually lives in ``services.analytics_service`` (ImportError at runtime).
  * ``test-ga4-stream`` read ``data["sessions"]`` but the service returns
    ``total_sessions``, so it always reported 0 active visitors.
  * ``/connectors/status`` reported GSC/GA4 as "Connected" merely because an env
    var was non-empty.
"""

import json
import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from services import google_credentials
from services.google_credentials import (
    GoogleCredentialsError,
    has_service_account_credentials,
    load_service_account_credentials,
)

import routers.connectors as connectors_mod


def _fake_service_account(private_key: str = "-----BEGIN PRIVATE KEY-----\nMIIE\n-----END PRIVATE KEY-----\n") -> dict:
    return {
        "type": "service_account",
        "project_id": "rankforge-test",
        "private_key_id": "abc123",
        "private_key": private_key,
        "client_email": "svc@rankforge-test.iam.gserviceaccount.com",
        "client_id": "1234567890",
        "token_uri": "https://oauth2.googleapis.com/token",
    }


# --------------------------------------------------------------------------
# Credential resolution
# --------------------------------------------------------------------------

def test_json_content_is_accepted_as_credentials():
    """A pasted JSON blob (the UI's format) must resolve to usable credentials."""
    info = _fake_service_account()
    assert has_service_account_credentials(candidates=[json.dumps(info)]) is True
    assert has_service_account_credentials(candidates=[info]) is True


def test_escaped_newlines_in_private_key_are_unescaped():
    """Form-pasted JSON carries ``\\n`` literals; the client lib needs real newlines."""
    escaped = json.dumps(_fake_service_account(private_key="-----BEGIN PRIVATE KEY-----\\nMIIE\\n-----END PRIVATE KEY-----\\n"))
    resolved = google_credentials._as_info(escaped)
    assert "\n" in resolved["private_key"]
    assert "\\n" not in resolved["private_key"]


def test_path_only_configuration_no_longer_counts_as_configured(monkeypatch, tmp_path):
    """A nonexistent *_CREDENTIALS_PATH must not read as configured."""
    monkeypatch.delenv("GA4_CREDENTIALS_JSON", raising=False)
    assert has_service_account_credentials(
        candidates=["/no/such/file.json"],
        path_env_keys=["GA4_CREDENTIALS_PATH"],
    ) is False


def test_loading_credentials_raises_actionable_error_when_missing(monkeypatch):
    # The loader also reads env-var sources, so clear them: otherwise a developer
    # with GA4_CREDENTIALS_JSON in .env would never exercise the missing-creds path.
    for var in ("GA4_CREDENTIALS_JSON", "GSC_SERVICE_ACCOUNT_JSON",
                "GA4_CREDENTIALS_PATH", "GSC_CREDENTIALS_PATH"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(GoogleCredentialsError) as exc:
        load_service_account_credentials(
            scopes=["https://www.googleapis.com/auth/analytics.readonly"],
            candidates=[None],
            json_env_keys=["GA4_CREDENTIALS_JSON"],
            path_env_keys=["GA4_CREDENTIALS_PATH"],
        )
    assert "service-account" in str(exc.value).lower()


def test_ga4_service_reads_json_env(monkeypatch):
    from services.ga4_service import GA4Service

    monkeypatch.setenv("GA4_PROPERTY_ID", "123456789")
    monkeypatch.setenv("GA4_CREDENTIALS_JSON", json.dumps(_fake_service_account()))
    monkeypatch.delenv("GA4_CREDENTIALS_PATH", raising=False)
    assert GA4Service().is_connected() is True


def test_gsc_service_reads_json_env(monkeypatch):
    from services.gsc_service import GSCService

    monkeypatch.setenv("GSC_SERVICE_ACCOUNT_JSON", json.dumps(_fake_service_account()))
    monkeypatch.delenv("GSC_CREDENTIALS_PATH", raising=False)
    assert GSCService().is_connected() is True


# --------------------------------------------------------------------------
# Endpoint behaviour
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_test_ga4_rejects_invalid_json():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/connectors/test-ga4", json={
            "property_id": "123",
            "credentials_json": "{not json",
        })
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_test_gsc_rejects_invalid_json():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/connectors/test-gsc", json={
            "property_url": "https://example.com",
            "credentials_json": "definitely-not-json",
        })
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_test_ga4_no_creds_is_honest_and_not_saved(monkeypatch):
    """No credentials -> not_configured, saved=False. Never a fake success."""
    monkeypatch.delenv("GA4_PROPERTY_ID", raising=False)
    monkeypatch.delenv("GA4_CREDENTIALS_JSON", raising=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/connectors/test-ga4", json={})
    body = res.json()
    assert res.status_code == 200
    assert body["connected"] is False
    assert body["saved"] is False


@pytest.mark.asyncio
async def test_test_ga4_persists_verified_credentials(monkeypatch):
    """A live-verified GA4 credential must be written to .env + local store."""
    monkeypatch.delenv("GA4_PROPERTY_ID", raising=False)
    monkeypatch.delenv("GA4_CREDENTIALS_JSON", raising=False)
    creds = json.dumps(_fake_service_account())

    async def fake_verify(prop_id, cred_json):
        return {"connected": True, "status": "success", "sessions_last_7_days": 42,
                "message": "Successfully connected to Google Analytics 4"}

    written = {}

    def fake_write_env_file(custom_keys=None, **kwargs):
        written.update(custom_keys or {})
        return {"keys_set": list((custom_keys or {}).keys())}

    with patch.object(connectors_mod, "_verify_ga4_live", new=fake_verify), \
         patch.object(connectors_mod, "write_env_file", side_effect=fake_write_env_file):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post("/api/connectors/test-ga4", json={
                "property_id": "999888777",
                "credentials_json": creds,
            })

    body = res.json()
    assert res.status_code == 200
    assert body["connected"] is True
    assert body["saved"] is True
    assert written["GA4_PROPERTY_ID"] == "999888777"
    assert written["GA4_CREDENTIALS_JSON"] == creds
    # Promoted into the running process so no restart is needed.
    assert os.environ["GA4_PROPERTY_ID"] == "999888777"


@pytest.mark.asyncio
async def test_test_gsc_persists_verified_credentials(monkeypatch):
    monkeypatch.delenv("GSC_SERVICE_ACCOUNT_JSON", raising=False)
    creds = json.dumps(_fake_service_account())

    async def fake_verify(cred_json, prop_url):
        return {"connected": True, "status": "success", "properties": ["https://example.com/"],
                "message": "GSC credentials active"}

    written = {}

    def fake_write_env_file(custom_keys=None, **kwargs):
        written.update(custom_keys or {})
        return {"keys_set": list((custom_keys or {}).keys())}

    with patch.object(connectors_mod, "_verify_gsc_live", new=fake_verify), \
         patch.object(connectors_mod, "write_env_file", side_effect=fake_write_env_file):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post("/api/connectors/test-gsc", json={
                "property_url": "https://example.com/",
                "credentials_json": creds,
            })

    body = res.json()
    assert body["connected"] is True
    assert body["saved"] is True
    assert written["GSC_SERVICE_ACCOUNT_JSON"] == creds
    assert written["GSC_SITE_URL"] == "https://example.com/"


@pytest.mark.asyncio
async def test_test_ga4_live_failure_is_not_saved(monkeypatch):
    """A failing live check must never be reported as saved."""
    async def fake_verify(prop_id, cred_json):
        return {"connected": False, "status": "error", "sessions_last_7_days": None,
                "message": "GA4 connection failed: invalid_grant"}

    with patch.object(connectors_mod, "_verify_ga4_live", new=fake_verify):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post("/api/connectors/test-ga4", json={
                "property_id": "1", "credentials_json": json.dumps(_fake_service_account()),
            })
    body = res.json()
    assert body["connected"] is False
    assert body["saved"] is False


@pytest.mark.asyncio
async def test_ga4_service_uses_properties_run_report(monkeypatch):
    """Regression: the Data API client has no top-level `runReport`.

    The call must be `service.properties().runReport(property=..., body=...)`
    followed by `.execute()`. The original code called `service.runReport(...)`
    directly, which raised AttributeError for every real credential.
    """
    from services.ga4_service import GA4Service

    captured = {}

    class _Request:
        def execute(self):
            return {"rows": [{"metricValues": [{"value": "5"}]}]}

    class _Properties:
        def runReport(self, property=None, body=None):
            captured["property"] = property
            captured["body"] = body
            return _Request()

    class _FakeClient:
        def properties(self):
            return _Properties()

    svc = GA4Service(property_id="777", credentials_path=json.dumps(_fake_service_account()))
    svc._initialized = True
    svc._service = _FakeClient()

    result = await svc.get_page_traffic(start_date="2026-01-01", end_date="2026-01-07")
    assert captured["property"] == "properties/777"
    assert "dateRanges" in captured["body"]
    assert result["total_sessions"] == 5


@pytest.mark.asyncio
async def test_sync_gsc_uses_analytics_service(monkeypatch):
    """sync-gsc must import sync_gsc_data from analytics_service (the real home)."""
    called = {}

    async def fake_sync(website_id=None):
        called["website_id"] = website_id
        return {"success": True, "records_synced": 5}

    import services.analytics_service as analytics

    with patch.object(analytics.AnalyticsService, "sync_gsc_data", new=fake_sync):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post("/api/connectors/sync-gsc", json={"website_id": "site-1"})
    body = res.json()
    assert res.status_code == 200
    assert body["synced"] is True
    assert called["website_id"] == "site-1"


@pytest.mark.asyncio
async def test_sync_gsc_not_configured_is_honest(monkeypatch):
    """Unconfigured GSC sync reports failure with the real reason, not success."""
    monkeypatch.delenv("GSC_CREDENTIALS_PATH", raising=False)
    monkeypatch.delenv("GSC_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    import services.analytics_service as analytics

    async def fake_sync(website_id=None):
        return {"success": False, "source": "not_configured", "records_synced": 0,
                "message": "GSC credentials not configured — add service JSON in /connectors"}

    with patch.object(analytics.AnalyticsService, "sync_gsc_data", new=fake_sync):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post("/api/connectors/sync-gsc", json={})
    body = res.json()
    assert body["synced"] is False
    assert body["records_synced"] == 0
    assert "not configured" in body["message"].lower()


@pytest.mark.asyncio
async def test_ga4_stream_reports_total_sessions(monkeypatch):
    """Regression: stream read `sessions` and always showed 0 active visitors."""
    monkeypatch.setenv("GA4_PROPERTY_ID", "123")
    monkeypatch.setenv("GA4_CREDENTIALS_JSON", json.dumps(_fake_service_account()))

    from services.ga4_service import GA4Service

    async def fake_traffic(self, start_date=None, end_date=None, limit=25000):
        return {"pages": [], "top_pages": [], "total_sessions": 77, "connected": True}

    with patch.object(GA4Service, "get_page_traffic", new=fake_traffic):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post("/api/connectors/test-ga4-stream", json={"property_id": "123"})
    body = res.json()
    assert res.status_code == 200
    assert body["connected"] is True
    assert body["active_visitors"] == 77


@pytest.mark.asyncio
async def test_ga4_stream_unconfigured_is_honest(monkeypatch):
    monkeypatch.delenv("GA4_PROPERTY_ID", raising=False)
    monkeypatch.delenv("GA4_CREDENTIALS_JSON", raising=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/connectors/test-ga4-stream", json={})
    body = res.json()
    assert body["connected"] is False
    assert body["stream_status"] == "not_configured"


@pytest.mark.asyncio
async def test_status_does_not_claim_connected_without_credentials(monkeypatch):
    """An unconfigured GA4/GSC must not read 'Connected' in /connectors/status."""
    monkeypatch.delenv("GA4_PROPERTY_ID", raising=False)
    monkeypatch.delenv("GA4_CREDENTIALS_JSON", raising=False)
    monkeypatch.delenv("GSC_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("GSC_SITE_URL", raising=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/connectors/status")
    body = res.json()
    assert body["ga4"]["connected"] is False
    assert body["ga4"]["status_label"] == "Not Configured"
    assert body["gsc"]["connected"] is False
    assert body["gsc"]["status_label"] == "Not Configured"


@pytest.mark.asyncio
async def test_status_verifies_google_live_before_claiming_connected(monkeypatch):
    """Configured-but-invalid Google creds must not show as Connected."""
    monkeypatch.setenv("GA4_PROPERTY_ID", "123")
    monkeypatch.setenv("GA4_CREDENTIALS_JSON", json.dumps(_fake_service_account()))
    connectors_mod._GOOGLE_STATUS_CACHE.clear()

    async def fake_verify(prop_id, cred_json):
        return {"connected": False, "status": "error",
                "message": "GA4 connection failed: invalid_grant"}

    with patch.object(connectors_mod, "_verify_ga4_live", new=fake_verify):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/connectors/status")
    body = res.json()
    assert body["ga4"]["is_configured"] is True
    assert body["ga4"]["connected"] is False
    assert body["ga4"]["status_label"] == "Configured (unverified)"
    connectors_mod._GOOGLE_STATUS_CACHE.clear()
