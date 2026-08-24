import os
import time
import logging
from typing import Optional, List

import httpx
import tenacity
from supabase import create_client, Client
from tenacity import stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import SUPABASE_URL, SUPABASE_KEY, NVIDIA_API_KEY

logger = logging.getLogger("backend.database")

supabase_client: Optional[Client] = None


def get_supabase() -> Client:
    """Retrieve or initialize singleton Supabase client with validation."""
    global supabase_client
    if supabase_client is None:
        url = os.getenv("SUPABASE_URL") or SUPABASE_URL
        key = os.getenv("SUPABASE_KEY") or SUPABASE_KEY
        if not url or not key:
            # In test environment with mocked calls, allow fallback
            if os.getenv("TESTING"):
                url = "https://mock.supabase.co"
                key = "mock-key"
            else:
                raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment")
        supabase_client = create_client(url, key)
    return supabase_client


def reset_supabase_client() -> None:
    global supabase_client
    supabase_client = None


def set_account_context(supabase_client: Optional[Client], account_id: str) -> None:
    """Set the Postgres session variable app.current_account_id for Supabase RLS."""
    if not supabase_client or not account_id:
        return
    try:
        supabase_client.rpc("set_account_context", {"p_account_id": str(account_id)}).execute()
    except Exception as e:
        logger.debug(f"RLS set_account_context note: {e}")


async def check_supabase_connection() -> bool:
    try:
        get_supabase().table("websites").select("id").limit(1).execute()
        return True
    except Exception as e:
        logger.error(f"Supabase connection check failed: {e}")
        return False


NIM_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"
NIM_LLM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NIM_EMBED_MODEL = os.getenv("NIM_EMBED_MODEL", "nvidia/nv-embedqa-e5-v5")  # 1024d embedding model
NIM_LLM_MODEL = os.getenv("NIM_LLM_MODEL", "meta/llama-3.1-70b-instruct")
NIM_API_KEY = os.getenv("NVIDIA_API_KEY", "")

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

    api_key = os.getenv("NVIDIA_API_KEY") or NIM_API_KEY
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
    payload = {
        "model": NIM_LLM_MODEL,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5,
        "temperature": 0,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(NIM_LLM_URL, json=payload, headers=headers)
    except httpx.RequestError as e:
        _nim_state.update({
            "available": False,
            "last_check": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "http_status": None,
            "error": str(e)[:300],
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
    elif status == 401:
        _nim_state.update({
            "available": False, "http_status": 401, "error": "HTTP 401 Unauthorized",
            "diagnostic": "NVIDIA NIM: Invalid API key — update it in Connectors.",
            "last_check": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        logger.error("[NIM] Invalid API key (401).")
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
    state = await validate_nim_connection()
    return bool(state.get("available"))


def get_nim_state() -> dict:
    """Current diagnostic snapshot for the workforce page."""
    return dict(_nim_state)


def _log_task_fail(website_id, action, error: str) -> None:
    try:
        get_supabase().table("tasks").insert({
            "website_id": website_id or "default",
            "agent_name": "database",
            "action": action,
            "status": "failed",
            "payload": {"error": str(error)[:500]},
            "real_api_called": "nim" if "nim" in action.lower() or "embed" in action.lower() else "supabase",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }).execute()
    except Exception:
        pass


class NIMEmbeddingError(RuntimeError):
    """Raised when the embedding API fails after all retries."""


class NIMLLMError(RuntimeError):
    """Raised when the NVIDIA NIM chat API fails after all retries."""


_nim_http_client: Optional[httpx.AsyncClient] = None


def _get_nim_http_client() -> httpx.AsyncClient:
    global _nim_http_client
    if _nim_http_client is None or _nim_http_client.is_closed:
        _nim_http_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))
    return _nim_http_client


@tenacity.retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True,
)
async def _embed_request(payload: dict, headers: dict) -> List[float]:
    client = _get_nim_http_client()
    resp = await client.post(NIM_EMBED_URL, json=payload, headers=headers)
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
    """Generate 1024-dimension dense vector representation using nvidia/nv-embedqa-e5-v5."""
    api_key = os.getenv("NVIDIA_API_KEY") or NIM_API_KEY
    payload = {
        "model": NIM_EMBED_MODEL,
        "input": [text],
        "input_type": "query",
        "encoding_format": "float",
        "truncate": "END",
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        vec = await _embed_request(payload, headers)
        if len(vec) == 1024:
            return vec
        return vec
    except Exception as e:
        logger.warning(f"NIM embedding API failed after retries: {e}")
        if website_id:
            _log_task_fail(website_id, "get_embedding", str(e))
        raise NIMEmbeddingError(
            f"Real embedding unavailable for text starting '{text[:50]}'. Refusing to substitute fake vectors."
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
    resp = await client.post(NIM_LLM_URL, json=payload, headers=headers)
    if resp.status_code == 429:
        raise httpx.HTTPStatusError("rate_limited", request=resp.request, response=resp)
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
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError, NIMLLMError)),
    reraise=True,
)
async def _nim_chat_with_retry(model_name: str, messages: list, headers: dict,
                               max_tokens: int, temperature: float) -> str:
    return await _nim_chat_request(model_name, messages, headers, max_tokens, temperature)


async def call_nim_llm(prompt: str, system: str = "", website_id: Optional[str] = None,
                       max_tokens: int = 2048, temperature: float = 0.7,
                       fail_silently: bool = True, **kwargs) -> str:
    """Call NVIDIA NIM chat completions with 3x retry and model fallbacks."""
    api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("NIM_API_KEY") or NIM_API_KEY
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    candidate_models = []
    env_model = os.getenv("NIM_LLM_MODEL")
    if env_model:
        candidate_models.append(env_model)
    for m in (NIM_LLM_MODEL, "meta/llama-3.1-70b-instruct", "meta/llama-3.1-8b-instruct"):
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
            if "401" in msg:
                _nim_state.update({"available": False, "http_status": 401,
                                   "diagnostic": "NVIDIA NIM: Invalid API key — update it in Connectors.",
                                   "error": msg[:300]})
                break  # Wrong key will never succeed on other models
            if "404" in msg:
                _nim_state.update({"available": False, "http_status": 404,
                                   "diagnostic": f"NVIDIA NIM: Model not found — check model ID '{model_name}'.",
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
