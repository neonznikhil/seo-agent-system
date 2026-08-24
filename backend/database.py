import os
import time
import logging
from typing import Optional

import httpx
import tenacity
from supabase import create_client, Client
from tenacity import stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger("backend.database")

supabase_client: Optional[Client] = None


def get_supabase() -> Client:
    global supabase_client
    if supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return supabase_client


def reset_supabase_client() -> None:
    global supabase_client
    supabase_client = None


async def check_supabase_connection() -> bool:
    try:
        get_supabase().table("websites").select("id").limit(1).execute()
        return True
    except Exception as e:
        logger.error(f"Supabase connection check failed: {e}")
        return False


NIM_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"
NIM_LLM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NIM_EMBED_MODEL = os.getenv("NIM_EMBED_MODEL", "nvidia/nv-embedqa-e5-v5")  # verified live, 1024d
# Strongest Nemotron-class model live on build.nvidia.com as of audit.
# (nemotron-ultra-253b returns 404 on this endpoint - verified 2026-08.)
NIM_LLM_MODEL = os.getenv(
    "NIM_LLM_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1"
)
NIM_API_KEY = os.getenv("NVIDIA_API_KEY", "")


def _log_task_fail(website_id, action, error: str) -> None:
    try:
        get_supabase().table("tasks").insert({
            "website_id": website_id,
            "agent_name": "database",
            "action": action,
            "status": "failed",
            "payload": {"error": error[:500]},
            "real_api_called": "nim" if "nim" in action.lower() or "embed" in action.lower() else "supabase",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }).execute()
    except Exception:
        pass


class NIMEmbeddingError(RuntimeError):
    """Raised when the embedding API fails. Callers must skip vector ops rather
    than persist garbage vectors."""


class NIMLLMError(RuntimeError):
    """Raised when the NVIDIA NIM chat API fails after all retries.
    Callers must surface an error state rather than persist empty/template text."""


async def get_embedding(text: str, website_id: Optional[str] = None) -> list:
    payload = {
        "model": NIM_EMBED_MODEL,
        "input": [text],
        "input_type": "query",
        "encoding_format": "float",
        "truncate": "END",
    }
    headers = {
        "Authorization": f"Bearer {NIM_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(NIM_EMBED_URL, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                vec = data["data"][0]["embedding"]
                if len(vec) == 1024:
                    return vec
            logger.warning(
                f"NIM embedding API returned {resp.status_code}: {resp.text[:200]}"
            )
    except Exception as e:
        logger.warning(f"NIM embedding API failed: {e}")

    raise NIMEmbeddingError(
        f"Real embedding unavailable for text starting '{text[:50]}'. "
        "Refusing to substitute fake vectors."
    )


# Shared async HTTP client for NIM (avoids per-call TCP/TLS setup)
_nim_http_client: Optional[httpx.AsyncClient] = None


def _get_nim_http_client() -> httpx.AsyncClient:
    global _nim_http_client
    if _nim_http_client is None or _nim_http_client.is_closed:
        _nim_http_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))
    return _nim_http_client


async def _nim_chat_request(model_name: str, messages: list, headers: dict,
                            max_tokens: int, temperature: float) -> str:
    """Single NIM chat completion attempt. Returns content or raises."""
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
    wait=wait_exponential(multiplier=2, min=2, max=20),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError, NIMLLMError)),
    reraise=True,
)
async def _nim_chat_with_retry(model_name: str, messages: list, headers: dict,
                               max_tokens: int, temperature: float) -> str:
    return await _nim_chat_request(model_name, messages, headers, max_tokens, temperature)


async def call_nim_llm(prompt: str, system: str = "", website_id: Optional[str] = None,
                       max_tokens: int = 2048, temperature: float = 0.7,
                       fail_silently: bool = True, **kwargs) -> str:
    """Call NVIDIA NIM chat completions.

    Retries each candidate model up to 3 times with exponential backoff.
    When all attempts fail: raises NIMLLMError if fail_silently=False,
    otherwise returns "" (legacy behaviour for non-critical callers).
    """
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
            return await _nim_chat_with_retry(
                model_name, messages, headers, max_tokens, temperature
            )
        except Exception as e:
            last_error = e
            logger.warning(f"NIM LLM model {model_name} failed after retries: {e}")

    logger.error(
        "NIM LLM call failed for all models (prompt starting '%s')",
        prompt[:60].replace("\n", " "),
    )
    if website_id:
        _log_task_fail(website_id, "call_nim_llm", str(last_error)[:500])
    if not fail_silently:
        raise NIMLLMError(f"NVIDIA NIM unavailable after retries: {last_error}")
    return ""
