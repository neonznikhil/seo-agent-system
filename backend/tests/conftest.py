import logging
import os
import tempfile

import pytest

logger = logging.getLogger("backend.tests.conftest")

# This MUST run at import time, not in a fixture: pytest imports this conftest
# before collecting test modules, and those modules import the local stores
# (services.local_store, utils.job_queue) which compute DATA_DIR at import time.
# Setting the env here guarantees the throwaway dir is used for the whole run.
os.environ["RANKFORGE_DATA_DIR"] = tempfile.mkdtemp(prefix="rankforge-tests-")
os.environ.setdefault("TESTING", "1")


@pytest.fixture(autouse=True)
def _reset_cached_supabase_client():
    """Drop the cached Supabase singleton between tests.

    `get_supabase()` caches the client it first built. A test that exercises the
    real project would otherwise leave that client cached, so a later test that
    monkeypatches SUPABASE_URL/KEY (e.g. the placeholder-honesty regression) kept
    talking to the real project and saw connected=True.
    """
    try:
        from database import reset_supabase_client
    except Exception:  # pragma: no cover - import path only
        yield
        return
    reset_supabase_client()
    yield
    reset_supabase_client()


# Credential vars the app itself writes into os.environ when a save endpoint
# adopts a verified value. monkeypatch only reverts what it set, so without this
# a single test that exercises a save path leaks a fake project/key into every
# later test in the run.
_CREDENTIAL_ENV_KEYS = (
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_SERVICE_KEY",
    "WORDPRESS_SITE_URL",
    "WORDPRESS_URL",
    "WORDPRESS_USERNAME",
    "WORDPRESS_USER",
    "WORDPRESS_APP_PASSWORD",
    "WORDPRESS_PASSWORD",
    "WP_SITE_URL",
    "WP_USERNAME",
    "WP_APP_PASSWORD",
    "NVIDIA_API_KEY",
    "SERPER_API_KEY",
    # save-all now adopts non-Supabase keys into the live process, so these can
    # leak between tests in the same run and change later connectors' behaviour.
    "GSC_SITE_URL",
    "GSC_PROPERTY",
    "GSC_CREDENTIALS",
    "GSC_CREDENTIALS_JSON",
    "GA4_PROPERTY_ID",
    "GA4_CREDENTIALS",
    "GA4_CREDENTIALS_JSON",
    "OPENAI_API_KEY",
    "PERPLEXITY_API_KEY",
)


@pytest.fixture(autouse=True)
def _isolate_credential_env():
    """Snapshot and restore credential env vars around every test."""
    saved = {k: os.environ.get(k) for k in _CREDENTIAL_ENV_KEYS}
    yield
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def live_nvidia_key() -> str:
    """Return the configured NVIDIA key, or skip when there is none to test with.

    A present-but-rejected key (the common case on a dev box) is NOT a code
    failure: the honest 401 behaviour is asserted with mocks in
    test_connector_honesty.py. Live tests should skip rather than report red, so
    the suite distinguishes "no usable key here" from "the integration broke".
    """
    key = os.getenv("NVIDIA_API_KEY") or os.getenv("NIM_API_KEY")
    if not key or key.strip().lower() in ("dummy", "mock-key", "test-key"):
        pytest.skip("NVIDIA_API_KEY not configured")
    return key


def skip_if_auth_rejected(status_code: int, body: str = "") -> None:
    """Skip a live test when the provider rejects the configured credential."""
    if status_code in (401, 403):
        pytest.skip(f"NVIDIA_API_KEY rejected by provider (HTTP {status_code})")
