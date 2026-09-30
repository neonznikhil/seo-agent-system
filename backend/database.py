import os
import time
import asyncio
import functools
import logging
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()


import httpx
import tenacity
from supabase import create_client, Client
from tenacity import stop_after_attempt, wait_exponential, retry_if_exception_type, retry_if_not_exception_type

try:
    from config import SUPABASE_URL, SUPABASE_KEY, NVIDIA_API_KEY
except (ImportError, ValueError):
    try:
        from .config import SUPABASE_URL, SUPABASE_KEY, NVIDIA_API_KEY
    except (ImportError, ValueError):
        from backend.config import SUPABASE_URL, SUPABASE_KEY, NVIDIA_API_KEY

logger = logging.getLogger("backend.database")

supabase_client: Optional[Client] = None


def get_supabase() -> Client:
    """Retrieve or initialize singleton Supabase client with pooling.

    Uses httpx connection pooling via supabase-py options for production
    stability (Phase 3 pooling fix). Prioritizes service_role key for backend operations.
    """
    global supabase_client
    if supabase_client is None:
        url = os.getenv("SUPABASE_URL") or SUPABASE_URL
        key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_SERVICE_KEY")
            or os.getenv("SUPABASE_KEY")
            or SUPABASE_KEY
        )
        if not url or not key:
            if os.getenv("TESTING"):
                url = "https://mock.supabase.co"
                key = "mock-key"
            else:
                raise ValueError("SUPABASE_URL and SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY must be set in environment")
        # Log which key type is being used
        key_source = "SERVICE_ROLE" if os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") else "ANON"
        # PostgREST defaults to http2=True on a single httpx client. httpcore
        # serialises every request over that one HTTP/2 connection, so a slow
        # query issued by the knowledge crawl (the first crawl of a site can take
        # 30-60s) blocked every other Supabase call — including the tiny
        # `GET /api/websites` that the websites page waits on. The user-visible
        # symptom was "connecting a website breaks the app". An HTTP/1.1 client
        # with a real connection pool gives each concurrent query its own
        # connection, so a slow crawl cannot stall unrelated reads.
        http_client = httpx.Client(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
            follow_redirects=True,
            http2=False,
        )
        try:
            from supabase.lib.client_options import SyncClientOptions
            opts = SyncClientOptions(
                postgrest_client_timeout=30,
                storage_client_timeout=30,
                schema="public",
                httpx_client=http_client,
            )
            supabase_client = create_client(url, key, options=opts)
        except Exception as e:
            # Fallback without options for older supabase-py
            logger.warning(f"[DB] Supabase pooling options unavailable, using default transport: {e}")
            supabase_client = create_client(url, key)
        logger.info(f"[DB] Supabase singleton initialized with pooling (key={key_source})")
    return supabase_client


def reset_supabase_client() -> None:
    global supabase_client
    # Close the pooled transport so its sockets are not leaked across resets.
    try:
        if supabase_client is not None:
            supabase_client.postgrest.session.close()
    except Exception:
        pass
    supabase_client = None


def set_account_context(supabase_client: Optional[Client], account_id: str) -> None:
    """Set the Postgres session variable app.current_account_id for Supabase RLS."""
    if not supabase_client or not account_id:
        return
    try:
        supabase_client.rpc("set_account_context", {"p_account_id": str(account_id)}).execute()
    except Exception as e:
        logger.debug(f"RLS set_account_context note: {e}")


async def to_thread(func, /, *args, **kwargs):
    """Run a blocking callable (e.g. the synchronous Supabase client) off the loop.

    supabase-py is synchronous, so awaiting it from an ``async def`` handler
    blocks the whole event loop: concurrent browser requests (topbar health +
    websites + connectors) then serialize behind each other and behind any
    in-flight crawl, which is what made "connect website" feel broken and time
    out through the Next proxy. Offloading keeps the loop responsive.
    """
    call = functools.partial(func, *args, **kwargs)
    return await asyncio.to_thread(call)


async def execute_db(query):
    """Await a Supabase query builder's blocking ``.execute()`` on a worker thread."""
    return await to_thread(query.execute)


async def check_supabase_connection() -> bool:
    try:
        get_supabase().table("websites").select("id").limit(1).execute()
        return True
    except Exception as e:
        logger.error(f"Supabase connection check failed: {e}")
        return False


NIM_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"
NIM_LLM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
# OpenRouter endpoints
OPENROUTER_LLM_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"
# Updated 2026-08-28: previous nv-embedqa-e5-v5 and llama-3.1-nemotron-ultra-253b-v1.5 EOL 410 -> now via nim_client central
# Central models are defined in backend/services/nim_client.py - keep constants in sync
NIM_EMBED_MODEL = os.getenv("NIM_EMBED_MODEL", "nvidia/nemotron-3-embed-1b")
# Verified live against integrate.api.nvidia.com/v1/models. The previously
# hardcoded llama-3.x / nemotron-3-nano ids all return HTTP 410 Gone, so every
# chat call failed with "NIM unavailable after retries" until these were fixed.
NIM_LLM_MODEL = os.getenv("NIM_LLM_MODEL", "google/gemma-4-31b-it")
NIM_LLM_FALLBACK = os.getenv("NIM_LLM_FALLBACK", "meta/llama-3.2-11b-vision-instruct")
# Provider selection
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "nvidia")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
# Fallback lists for central client (used by call_nim_llm)
_LLM_MODELS = [
    NIM_LLM_MODEL,
    NIM_LLM_FALLBACK,
    "google/gemma-4-31b-it",
    "meta/llama-3.2-11b-vision-instruct",
]
_EMBED_MODELS = [NIM_EMBED_MODEL, "nvidia/nemotron-3-embed-1b"]
NIM_API_KEY = os.getenv("NVIDIA_API_KEY", "")
if LLM_PROVIDER == "openrouter":
    NIM_API_KEY = OPENROUTER_API_KEY or NIM_API_KEY


# ---------------------------------------------------------------------------
# NIM availability tracking (startup validation + live diagnostics)
# ---------------------------------------------------------------------------

_nim_state: dict = {
    "available": None,          # None = not validated yet, True/False after check
    "last_check": None,
    "http_status": None,
    "error": None,
    "diagnostic": None,
}


def reset_nim_availability() -> None:
    """Clear the cached availability flag so the next call re-validates."""
    _nim_state.update({
        "available": None,
        "last_check": None,
        "http_status": None,
        "error": None,
        "diagnostic": None,
    })


async def validate_nim_connection(force: bool = False) -> dict:
    """Make one real NVIDIA NIM call and classify the exact failure.

    401 -> invalid API key. 404 -> wrong model id. 429 -> rate limited.
    Stores a global flag consumed by the workforce page so users cannot
    trigger agents when NIM is down.
    """
    if _nim_state["available"] is not None and not force:
        return dict(_nim_state)

    api_key = NIM_API_KEY
    if not api_key:
        _nim_state.update({
            "available": False,
            "last_check": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "http_status": None,
            "error": "NVIDIA_API_KEY missing",
            "diagnostic": "NVIDIA NIM: API key not configured — add it in Connectors.",
        })
        logger.error("[NIM] NVIDIA_API_KEY is not set. All LLM features disabled until configured.")
        return dict(_nim_state)

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = NIM_LLM_URL
    if LLM_PROVIDER == "openrouter":
        url = OPENROUTER_LLM_URL
        headers["HTTP-Referer"] = "https://rankforge.ai"
        headers["X-Title"] = "RankForge"
    payload = {
        "model": NIM_LLM_MODEL,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5,
        "temperature": 0,
    }
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.RequestError as e:
        _nim_state.update({
            "available": False,
            "last_check": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "http_status": None,
            "error": "NVIDIA NIM unreachable (network error).",
            "diagnostic": "NVIDIA NIM unreachable (network error).",
        })
        logger.error(f"[NIM] Network error during validation: {e}")
        return dict(_nim_state)

    status = resp.status_code
    if status == 200:
        _nim_state.update({
            "available": True,
            "last_check": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "http_status": 200,
            "error": None,
            "diagnostic": f"NVIDIA NIM healthy — model {NIM_LLM_MODEL} responded.",
        })
        logger.info("[NIM] Startup validation passed ✅")
    elif status in (401, 403):
        _nim_state.update({
            "available": False, "http_status": 401, "error": f"HTTP {status} Unauthorized",
            "diagnostic": "NVIDIA NIM: Invalid API key — update it in Connectors.",
            "last_check": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        logger.error(f"[NIM] Invalid API key ({status}).")
    elif status == 404:
        _nim_state.update({
            "available": False, "http_status": 404, "error": "HTTP 404 Not Found",
            "diagnostic": "NVIDIA NIM: Model not found — check model ID "
                          f"'{NIM_LLM_MODEL}'.",
            "last_check": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        logger.error(f"[NIM] Model not found (404): {NIM_LLM_MODEL}")
    elif status == 429:
        # Rate limited but the key WORKS — treat as available with backoff note.
        _nim_state.update({
            "available": True, "http_status": 429, "error": "HTTP 429 rate limited",
            "diagnostic": "NVIDIA NIM rate limited — backing off automatically.",
            "last_check": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        logger.warning("[NIM] Rate limited (429) — backing off.")
    else:
        _nim_state.update({
            "available": False, "http_status": status,
            "error": f"HTTP {status}: {resp.text[:200]}",
            "diagnostic": f"NVIDIA NIM returned unexpected HTTP {status}.",
            "last_check": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        logger.error(f"[NIM] Unexpected status {status}: {resp.text[:200]}")

    return dict(_nim_state)


async def is_nim_available() -> bool:
    """Boolean gate used by routers to refuse agent triggers when NIM is down."""
    if _nim_state.get("available") is True:
        return True
    state = await validate_nim_connection()
    return bool(state.get("available"))


def get_nim_state() -> dict:
    """Current diagnostic snapshot for the workforce page."""
    return dict(_nim_state)


def _log_task_fail(website_id, action, error: str) -> None:
    try:
        try:
            from services.website_service import get_default_website_id
        except (ImportError, ValueError):
            try:
                from .services.website_service import get_default_website_id
            except (ImportError, ValueError):
                from backend.services.website_service import get_default_website_id
        resolved_id = website_id or get_default_website_id()
        payload = {
            "agent_name": "database",
            "action": action,
            "status": "failed",
            "payload": {"error": str(error)[:500]},
            "real_api_called": "nim" if "nim" in action.lower() or "embed" in action.lower() else "supabase",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if resolved_id:
            payload["website_id"] = resolved_id
        get_supabase().table("tasks").insert(payload).execute()
    except Exception as e:
        logger.warning(f"[Database] Failed to log NIM failure: {e}")
        pass


class NIMEmbeddingError(RuntimeError):
    """Raised when the embedding API fails after all retries."""


class NIMLLMError(RuntimeError):
    """Raised when the NVIDIA NIM chat API fails after all retries."""


class NIMAuthError(NIMLLMError):
    """Raised on 401/403 — a rejected key. Never retried and never tried against
    other models, because a bad key fails identically everywhere and retrying it
    only floods the API (and the logs) with guaranteed failures."""


_nim_http_client: Optional[httpx.AsyncClient] = None


def _get_nim_http_client() -> httpx.AsyncClient:
    global _nim_http_client
    if _nim_http_client is None or _nim_http_client.is_closed:
        _nim_http_client = httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=15.0))
    return _nim_http_client


@tenacity.retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=15),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True,
)
async def _embed_request(payload: dict, headers: dict) -> List[float]:
    client = _get_nim_http_client()
    url = NIM_EMBED_URL
    if LLM_PROVIDER == "openrouter":
        url = OPENROUTER_EMBED_URL
        headers["HTTP-Referer"] = "https://rankforge.ai"
        headers["X-Title"] = "RankForge"
    resp = await client.post(url, json=payload, headers=headers)
    if resp.status_code == 410:
        # EOL model - log and let caller try next fallback
        logger.warning(f"[NIM Embed] Model EOL 410 {payload.get('model')} - switching to fallback")
        raise httpx.HTTPStatusError(
            f"NIM Embed EOL 410 model {payload.get('model')}: {resp.text[:200]}",
            request=resp.request,
            response=resp,
        )
    if resp.status_code != 200:
        raise httpx.HTTPStatusError(
            f"NIM Embed returned {resp.status_code}: {resp.text[:200]}",
            request=resp.request,
            response=resp,
        )
    data = resp.json()
    vec = data["data"][0]["embedding"]
    return vec


async def get_embedding(text: str, website_id: Optional[str] = None) -> List[float]:
    """Generate 1536-dimension dense vector via central nim_client with circuit breaker and fallback."""
    try:
        try:
            from services.nim_client import embed
        except (ImportError, ValueError):
            try:
                from .services.nim_client import embed
            except (ImportError, ValueError):
                from backend.services.nim_client import embed
        vec = await embed(text)
        if not vec:
            raise NIMEmbeddingError(f"Embedding API returned empty vector for '{text[:50]}'")
        return vec
    except Exception as e:
        logger.warning(f"NIM embedding failed: {e}")
        if website_id:
            _log_task_fail(website_id, "get_embedding", str(e))
        raise NIMEmbeddingError(
            f"Real embedding unavailable for text starting '{text[:50]}'. Refusing to substitute synthetic vectors."
        )


async def _nim_chat_request(model_name: str, messages: list, headers: dict,
                            max_tokens: int, temperature: float) -> str:
    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    client = _get_nim_http_client()
    url = NIM_LLM_URL
    if LLM_PROVIDER == "openrouter":
        url = OPENROUTER_LLM_URL
        headers["HTTP-Referer"] = "https://rankforge.ai"
        headers["X-Title"] = "RankForge"
    resp = await client.post(url, json=payload, headers=headers)
    if resp.status_code == 429:
        raise httpx.HTTPStatusError("rate_limited", request=resp.request, response=resp)
    if resp.status_code in (401, 403):
        raise NIMAuthError(
            f"NIM returned {resp.status_code}: {resp.text[:200]}"
        )
    if resp.status_code != 200:
        raise httpx.HTTPStatusError(
            f"NIM returned {resp.status_code}: {resp.text[:200]}",
            request=resp.request, response=resp,
        )
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    if not content or not content.strip():
        raise NIMLLMError("NIM returned an empty completion")
    return content.strip()


@tenacity.retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=15),
    retry=(
        retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError, NIMLLMError))
        & retry_if_not_exception_type(NIMAuthError)
    ),
    reraise=True,
)
async def _nim_chat_with_retry(model_name: str, messages: list, headers: dict,
                               max_tokens: int, temperature: float) -> str:
    # Handles 410 EOL specifically: log and let caller fallback
    return await _nim_chat_request(model_name, messages, headers, max_tokens, temperature)


async def call_nim_llm(prompt: str, system: str = "", website_id: Optional[str] = None,
                       max_tokens: int = 8192, temperature: float = 0.7,
                       fail_silently: bool = True, model: Optional[str] = None, **kwargs) -> str:
    """Call NVIDIA NIM chat completions with 3x retry and model fallbacks."""
    # A key already proven invalid cannot recover between scheduler ticks, so
    # short-circuit instead of re-attempting every model on every job. Without
    # this guard a single bad key produced thousands of guaranteed 403s once a
    # website was connected and the scheduler started calling NIM.
    if _nim_state.get("available") is False and _nim_state.get("http_status") == 401:
        msg = _nim_state.get("diagnostic") or "NVIDIA NIM: Invalid API key — update it in Connectors."
        if website_id:
            _log_task_fail(website_id, "call_nim_llm", msg)
        if not fail_silently:
            raise NIMAuthError(msg)
        return ""
    # Rate limiting: min 1.5s gap between requests
    global _last_request_time_db
    try:
        _last_request_time_db
    except NameError:
        _last_request_time_db = 0.0
    import asyncio
    import time
    now = time.monotonic()
    elapsed = now - _last_request_time_db
    if elapsed < 1.5:
        await asyncio.sleep(1.5 - elapsed)
    _last_request_time_db = time.monotonic()
    
    api_key = os.getenv("NVIDIA_API_KEY") or NIM_API_KEY

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if LLM_PROVIDER == "openrouter":
        headers["HTTP-Referer"] = "https://rankforge.ai"
        headers["X-Title"] = "RankForge"

    candidate_models = []
    if model:
        candidate_models.append(model)
    env_model = os.getenv("NIM_LLM_MODEL")
    if env_model and env_model not in candidate_models:
        candidate_models.append(env_model)
    # Use central _LLM_MODELS (primary verified working models)
    for m in _LLM_MODELS:
        if m not in candidate_models:
            candidate_models.append(m)

    last_error: Optional[Exception] = None
    for model_name in candidate_models:
        try:
            result = await _nim_chat_with_retry(
                model_name, messages, headers, max_tokens, temperature
            )
            if not _nim_state.get("available"):
                _nim_state.update({"available": True, "error": None,
                                   "diagnostic": f"NVIDIA NIM healthy — model {model_name} responded."})
            return result
        except Exception as e:
            last_error = e
            msg = str(e)
            logger.warning(f"NIM LLM model {model_name} failed after retries: {e}")
            if isinstance(e, NIMAuthError) or "401" in msg or "403" in msg:
                _nim_state.update({"available": False, "http_status": 401,
                                   "diagnostic": "NVIDIA NIM: Invalid API key — update it in Connectors.",
                                   "error": msg[:300]})
                break  # Wrong key will never succeed on other models
            if "404" in msg or "410" in msg:
                _nim_state.update({"available": False, "http_status": 404 if "404" in msg else 410,
                                   "diagnostic": f"NVIDIA NIM: Model '{model_name}' not found / gone (EOL) — trying fallback.",
                                   "error": msg[:300]})
                continue
            if "500" in msg or "503" in msg or "502" in msg or "504" in msg:
                # Provider-side transient errors are per-model; a healthy model
                # in the candidate list should still be tried.
                _nim_state.update({"available": False, "http_status": 500,
                                   "diagnostic": f"NVIDIA NIM: Model '{model_name}' returned a server error — trying fallback.",
                                   "error": msg[:300]})
                continue

    logger.error(
        "NIM LLM call failed for all models (prompt starting '%s')",
        prompt[:60].replace("\n", " "),
    )
    if _nim_state.get("available") is not False and last_error is not None:
        _nim_state.update({
            "available": False,
            "error": str(last_error)[:300],
            "diagnostic": "NVIDIA NIM unavailable after retries.",
            "last_check": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
    if website_id:
        _log_task_fail(website_id, "call_nim_llm", str(last_error)[:500])
    if not fail_silently:
        raise NIMLLMError(f"NVIDIA NIM unavailable after retries: {last_error}")
    return ""
