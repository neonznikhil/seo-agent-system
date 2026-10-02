"""Tests for Google Analytics 4 (GA4) and Google Search Console (GSC) connector flows.

Covers:
- Dynamic credential payload parsing and validation (rejecting malformed JSON with 400).
- Honest failure reporting when live credentials fail (connected: False without 500 crashes).
- Normalizing GA4 property IDs by stripping 'properties/' prefixes.
- Dual-writing credential keys (GA4_CREDENTIALS + GA4_CREDENTIALS_JSON,
  GSC_CREDENTIALS + GSC_SERVICE_ACCOUNT_JSON) for cross-service compatibility.
"""

from unittest.mock import patch, MagicMock
import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
async def test_test_ga4_invalid_json_returns_400():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/connectors/test-ga4",
            json={
                "property_id": "12345678",
                "credentials_json": "this is not valid json",
            },
        )
    assert res.status_code == 400
    assert "Invalid Service Account JSON format" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_test_ga4_strips_properties_prefix_and_handles_bad_creds():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/connectors/test-ga4",
            json={
                "property_id": "properties/987654321",
                "credentials_json": '{"type": "service_account", "project_id": "dummy"}',
            },
        )
    assert res.status_code == 200
    data = res.json()
    assert data["connected"] is False
    assert "error" in data or "message" in data


@pytest.mark.asyncio
async def test_test_gsc_invalid_json_returns_400():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/connectors/test-gsc",
            json={
                "property_url": "https://example.com",
                "credentials_json": "{not valid json}",
            },
        )
    assert res.status_code == 400
    assert "Invalid Service Account JSON format" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_test_gsc_bad_creds_returns_not_connected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/connectors/test-gsc",
            json={
                "property_url": "https://example.com",
                "credentials_json": '{"type": "service_account", "project_id": "dummy"}',
            },
        )
    assert res.status_code == 200
    data = res.json()
    assert data["connected"] is False
    assert "message" in data


@pytest.mark.asyncio
async def test_save_generic_connector_ga4_dual_write_and_strip_prefix():
    captured_keys = {}

    def fake_write_env_file(custom_keys=None):
        if custom_keys:
            captured_keys.update(custom_keys)

    transport = ASGITransport(app=app)
    with patch("routers.connectors.write_env_file", side_effect=fake_write_env_file):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/connectors/save/ga4",
                json={
                    "property_id": "properties/5551234",
                    "secret": '{"client_email": "ga4-service@test.com"}',
                },
            )
    assert res.status_code == 200
    assert captured_keys.get("GA4_PROPERTY_ID") == "5551234"
    assert captured_keys.get("GA4_CREDENTIALS") == '{"client_email": "ga4-service@test.com"}'
    assert captured_keys.get("GA4_CREDENTIALS_JSON") == '{"client_email": "ga4-service@test.com"}'


@pytest.mark.asyncio
async def test_save_generic_connector_gsc_dual_write():
    captured_keys = {}

    def fake_write_env_file(custom_keys=None):
        if custom_keys:
            captured_keys.update(custom_keys)

    transport = ASGITransport(app=app)
    with patch("routers.connectors.write_env_file", side_effect=fake_write_env_file):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/connectors/save/gsc",
                json={
                    "url": "https://mysite.com",
                    "secret": '{"client_email": "gsc-service@test.com"}',
                },
            )
    assert res.status_code == 200
    assert captured_keys.get("GSC_SITE_URL") == "https://mysite.com"
    assert captured_keys.get("GSC_CREDENTIALS") == '{"client_email": "gsc-service@test.com"}'
    assert captured_keys.get("GSC_SERVICE_ACCOUNT_JSON") == '{"client_email": "gsc-service@test.com"}'


@pytest.mark.asyncio
async def test_save_all_ga4_and_gsc_dual_write_and_strip_prefix():
    captured_keys = {}

    def fake_write_env_file(custom_keys=None):
        if custom_keys:
            captured_keys.update(custom_keys)

    transport = ASGITransport(app=app)
    with patch("routers.connectors.write_env_file", side_effect=fake_write_env_file):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/connectors/save-all",
                json={
                    "ga4_property_id": "properties/777888999",
                    "ga4_credentials_json": '{"client_email": "ga4@example.com"}',
                    "gsc_property_url": "https://example.org",
                    "gsc_credentials_json": '{"client_email": "gsc@example.org"}',
                },
            )
    assert res.status_code == 200
    assert captured_keys.get("GA4_PROPERTY_ID") == "777888999"
    assert captured_keys.get("GA4_CREDENTIALS") == '{"client_email": "ga4@example.com"}'
    assert captured_keys.get("GA4_CREDENTIALS_JSON") == '{"client_email": "ga4@example.com"}'
    assert captured_keys.get("GSC_SITE_URL") == "https://example.org"
    assert captured_keys.get("GSC_CREDENTIALS") == '{"client_email": "gsc@example.org"}'
    assert captured_keys.get("GSC_SERVICE_ACCOUNT_JSON") == '{"client_email": "gsc@example.org"}'
