"""Central LLM client — supports NVIDIA NIM and OpenRouter providers.
Provider selection via LLM_PROVIDER env: "nvidia" (default) or "openrouter".
OpenRouter: https://openrouter.ai/api/v1/chat/completions (OpenAI-compatible)
"""
import asyncio
import os
import logging
import time
import httpx
from typing import List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("backend.services.nim_client")

# Rate limiting: min gap between requests (1.5s = 40 RPM max)
_MIN_REQUEST_GAP = 1.5
_last_request_time = 0.0

async def _rate_limit():
    """Enforce minimum gap between API calls to stay under rate limit."""
    global _last_request_time
    now = time.monotonic()
    elapsed = now - _last_request_time
    if elapsed < _MIN_REQUEST_GAP:
        wait_time = _MIN_REQUEST_GAP - elapsed
        logger.debug(f"[NIM RateLimit] Waiting {wait_time:.1f}s")
        await asyncio.sleep(wait_time)
    _last_request_time = time.monotonic()

logger = logging.getLogger("backend.services.nim_client")

# Provider selection
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "nvidia")  # "nvidia" or "openrouter"

# NVIDIA NIM endpoints
NIM_LLM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NIM_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"

# OpenRouter endpoints (OpenAI-compatible)
OPENROUTER_LLM_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"

# Ordered lists - first 200 wins, EOL 410 triggers fallback
LLM_MODELS: List[str] = [
    os.getenv("NIM_LLM_MODEL", "nvidia/nemotron-3.5-lightning"),
    os.getenv("NIM_LLM_FALLBACK", "openai/gpt-oss-20b"),
    "nvidia/nemotron-3.5-lightning",
    "openai/gpt-oss-20b",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "nvidia/nemotron-3-ultra-550b-a55b",
]
# Add OpenRouter free model as final fallback if key available
_or_key = os.getenv("OPENROUTER_API_KEY", "")
if _or_key and "nvidia/nemotron-3-ultra-550b-a55b:free" not in LLM_MODELS:
    LLM_MODELS.append("nvidia/nemotron-3-ultra-550b-a55b:free")
# Deduplicate preserving order
_seen = set()
LLM_MODELS = [m for m in LLM_MODELS if not (m in _seen or _seen.add(m))]

EMBED_MODELS: List[str] = [
    os.getenv("NIM_EMBED_MODEL", "nvidia/nemotron-3-embed-1b"),
    "nvidia/nvidia-embed-qa-4",
    # EOL last
    "nvidia/nv-embedqa-e5-v5",
]
_seen2 = set()
EMBED_MODELS = [m for m in EMBED_MODELS if not (m in _seen2 or _seen2.add(m))]

# Resolve the correct URL based on provider
def _get_llm_url() -> str:
    if LLM_PROVIDER == "openrouter":
        return OPENROUTER_LLM_URL
    return NIM_LLM_URL

def _get_embed_url() -> str:
    if LLM_PROVIDER == "openrouter":
        return OPENROUTER_EMBED_URL
    return NIM_EMBED_URL

def _get_api_key() -> str:
    if LLM_PROVIDER == "openrouter":
        return os.getenv("OPENROUTER_API_KEY", "")
    return os.getenv("NVIDIA_API_KEY") or os.getenv("NIM_API_KEY", "")

# Cache validated model
_cached_llm_model: str | None = None
_cached_embed_model: str | None = None

def get_llm_models() -> List[str]:
    return LLM_MODELS

def get_embedding_models() -> List[str]:
    return EMBED_MODELS

def get_llm_model() -> str:
    """Return first working LLM model (cached). Tries ordered list, first 200 wins."""
    global _cached_llm_model
    if _cached_llm_model:
        return _cached_llm_model
    # Default to primary without network if not cached - fast path
    return LLM_MODELS[0]

def get_embedding_model() -> str:
    global _cached_embed_model
    if _cached_embed_model:
        return _cached_embed_model
    return EMBED_MODELS[0]

async def _probe_llm_model(model: str, api_key: str) -> bool:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if LLM_PROVIDER == "openrouter":
        headers["HTTP-Referer"] = "https://rankforge.ai"
        headers["X-Title"] = "RankForge"
    payload = {"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5, "temperature": 0}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_get_llm_url(), json=payload, headers=headers)
            if resp.status_code == 200:
                return True
            if resp.status_code == 410:
                logger.warning(f"[NIM Client] Model EOL 410: {model} - switching to fallback")
            return False
    except Exception as e:
        logger.debug(f"[NIM Client] probe {model} failed: {e}")
        return False

async def _probe_embed_model(model: str, api_key: str) -> bool:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if LLM_PROVIDER == "openrouter":
        headers["HTTP-Referer"] = "https://rankforge.ai"
        headers["X-Title"] = "RankForge"
    payload = {"model": model, "input": ["hello world"], "input_type": "query", "encoding_format": "float"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_get_embed_url(), json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("data") and len(data["data"]) > 0:
                    return True
            if resp.status_code == 410:
                logger.warning(f"[NIM Client] Embed Model EOL 410: {model} - switching to fallback")
            return False
    except Exception as e:
        logger.debug(f"[NIM Client] probe embed {model} failed: {e}")
        return False

async def validate_llm_model(force: bool = False) -> str:
    """Probe models in order, return first 200, cache it."""
    global _cached_llm_model
    if _cached_llm_model and not force:
        return _cached_llm_model
    api_key = _get_api_key()
    if not api_key:
        logger.warning("[NIM Client] No API key, returning primary without probe")
        _cached_llm_model = LLM_MODELS[0]
        return _cached_llm_model
    for m in LLM_MODELS:
        if await _probe_llm_model(m, api_key):
            _cached_llm_model = m
            logger.info(f"[NIM Client] Validated LLM model: {m} ✅")
            return m
        else:
            logger.warning(f"[NIM Client] LLM model {m} failed, trying next fallback")
    _cached_llm_model = LLM_MODELS[0]
    return _cached_llm_model

async def validate_embedding_model(force: bool = False) -> str:
    global _cached_embed_model
    if _cached_embed_model and not force:
        return _cached_embed_model
    api_key = _get_api_key()
    if not api_key:
        _cached_embed_model = EMBED_MODELS[0]
        return _cached_embed_model
    for m in EMBED_MODELS:
        if await _probe_embed_model(m, api_key):
            _cached_embed_model = m
            logger.info(f"[NIM Client] Validated Embed model: {m} ✅")
            return m
        else:
            logger.warning(f"[NIM Client] Embed model {m} failed, trying next")
    _cached_embed_model = EMBED_MODELS[0]
    return _cached_embed_model

# Tenacity retry wrappers for 410 handling
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30), retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)), reraise=True)
async def _call_llm_with_retry(model: str, messages: list, headers: dict, max_tokens: int, temperature: float) -> str:
    await _rate_limit()
    async with httpx.AsyncClient(timeout=180.0) as client:
        payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        resp = await client.post(_get_llm_url(), json=payload, headers=headers)
        if resp.status_code == 410:
            logger.warning(f"[NIM Client] Model EOL 410 {model} - switching to fallback (retry)")
            raise httpx.HTTPStatusError(f"Model EOL 410 {model}", request=resp.request, response=resp)
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after", "10")
            wait_secs = int(retry_after) if retry_after.isdigit() else 10
            logger.warning(f"[NIM Client] Rate limited 429 on {model}. Waiting {wait_secs}s (Retry-After: {retry_after})")
            await asyncio.sleep(wait_secs)
            raise httpx.HTTPStatusError("rate_limited", request=resp.request, response=resp)
        if resp.status_code == 503:
            logger.warning(f"[NIM Client] Service overloaded 503 on {model}. Waiting 15s...")
            await asyncio.sleep(15)
            raise httpx.HTTPStatusError("service_overloaded_503", request=resp.request, response=resp)
        if resp.status_code != 200:
            raise httpx.HTTPStatusError(f"NIM returned {resp.status_code}: {resp.text[:200]}", request=resp.request, response=resp)
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        if not content or not content.strip():
            raise RuntimeError("NIM returned empty completion")
        return content.strip()

# Global Circuit Breaker State
_CONSECUTIVE_FAILURES = 0
_CIRCUIT_OPEN_UNTIL = 0.0


def _check_circuit_breaker():
    global _CONSECUTIVE_FAILURES, _CIRCUIT_OPEN_UNTIL
    import time
    if time.time() < _CIRCUIT_OPEN_UNTIL:
        remaining = int(_CIRCUIT_OPEN_UNTIL - time.time())
        raise RuntimeError(f"NVIDIA NIM circuit breaker OPEN — consecutive failures tripped. Pausing for {remaining}s")


def _record_success():
    global _CONSECUTIVE_FAILURES, _CIRCUIT_OPEN_UNTIL
    _CONSECUTIVE_FAILURES = 0
    _CIRCUIT_OPEN_UNTIL = 0.0


def _record_failure():
    global _CONSECUTIVE_FAILURES, _CIRCUIT_OPEN_UNTIL
    import time
    _CONSECUTIVE_FAILURES += 1
    if _CONSECUTIVE_FAILURES >= 3:
        _CIRCUIT_OPEN_UNTIL = time.time() + 60.0
        logger.error(f"[NIM CircuitBreaker] 3 consecutive failures reached. Circuit OPEN for 60s.")


def _log_nim_cost(agent_name: str, tokens: int, cost_usd: float):
    """Log NIM API usage and cost to daily_costs table."""
    try:
        from database import get_supabase
        sb = get_supabase()
        from datetime import datetime
        today = datetime.utcnow().strftime("%Y-%m-%d")
        payload = {
            "date": today,
            "agent_name": agent_name,
            "tokens": tokens,
            "cost_usd": round(cost_usd, 6),
            "created_at": datetime.utcnow().isoformat()
        }
        sb.table("daily_costs").insert(payload).execute()
    except Exception as e:
        logger.debug(f"[NIM Client] Could not log daily cost: {e}")


async def call_llm_central(prompt: str, system: str = "", max_tokens: int = 4096, temperature: float = 0.7) -> str:
    """Call NIM LLM via central client with circuit breaker, 410 fallback and 3 retries."""
    _check_circuit_breaker()
    api_key = _get_api_key()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if LLM_PROVIDER == "openrouter":
        headers["HTTP-Referer"] = "https://rankforge.ai"
        headers["X-Title"] = "RankForge"
    last_error = None
    for model in LLM_MODELS:
        try:
            result = await _call_llm_with_retry(model, messages, headers, max_tokens, temperature)
            _record_success()
            # Estimate tokens: ~4 chars per token
            est_tokens = max(10, (len(prompt) + len(system) + len(result)) // 4)
            est_cost = (est_tokens / 1000) * 0.0002 # ~$0.0002 / 1k tokens
            _log_nim_cost("nim_llm", est_tokens, est_cost)
            # Cache success
            global _cached_llm_model
            _cached_llm_model = model
            return result
        except Exception as e:
            last_error = e
            msg = str(e)
            if "410" in msg or "404" in msg:
                logger.warning(f"[NIM Client] Model {model} EOL/gone, trying fallback")
                continue
            if "401" in msg:
                _record_failure()
                logger.error(f"[NIM Client] 401 Invalid key, aborting")
                break
            logger.warning(f"[NIM Client] Model {model} failed: {e}, trying fallback")
            continue
    # All NVIDIA models failed - try OpenRouter if key available and not already using it
    or_key = os.getenv("OPENROUTER_API_KEY", "")
    if or_key and _get_api_key() != or_key:
        logger.warning(f"[NIM Client] All NVIDIA models failed, trying OpenRouter fallback")
        or_headers = {"Authorization": f"Bearer {or_key}", "Content-Type": "application/json", "HTTP-Referer": "https://rankforge.ai", "X-Title": "RankForge"}
        for model in LLM_MODELS:
            if ":free" not in model:
                continue
            try:
                await _rate_limit()
                async with httpx.AsyncClient(timeout=180.0) as client:
                    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
                    resp = await client.post(OPENROUTER_LLM_URL, json=payload, headers=or_headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        content = data["choices"][0]["message"]["content"]
                        if content and content.strip():
                            logger.info(f"[NIM Client] OpenRouter fallback success with {model}")
                            _record_success()
                            return content.strip()
            except Exception as e:
                logger.warning(f"[NIM Client] OpenRouter {model} failed: {e}")
                continue
    _record_failure()
    raise RuntimeError(f"NVIDIA NIM unavailable after trying {len(LLM_MODELS)} models: {last_error}")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30), retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)), reraise=True)
async def _call_embed_with_retry(model: str, inputs: list, headers: dict) -> list:
    await _rate_limit()
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {"model": model, "input": inputs, "input_type": "query", "encoding_format": "float"}
        resp = await client.post(_get_embed_url(), json=payload, headers=headers)
        if resp.status_code == 410:
            logger.warning(f"[NIM Client] Embed Model EOL 410 {model} - fallback")
            raise httpx.HTTPStatusError(f"Embed EOL 410 {model}", request=resp.request, response=resp)
        if resp.status_code != 200:
            raise httpx.HTTPStatusError(f"NIM Embed {resp.status_code}: {resp.text[:200]}", request=resp.request, response=resp)
        data = resp.json()
        return [item["embedding"] for item in data.get("data", [])]


async def call_embedding_central(texts: list, truncate: str = "END") -> list:
    """Batch embed via central client with circuit breaker, fallback and 410 handling."""
    _check_circuit_breaker()
    api_key = _get_api_key()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if LLM_PROVIDER == "openrouter":
        headers["HTTP-Referer"] = "https://rankforge.ai"
        headers["X-Title"] = "RankForge"
    clean_inputs = [t[:3500] for t in texts]
    last_error = None
    for model in EMBED_MODELS:
        try:
            vecs = await _call_embed_with_retry(model, clean_inputs, headers)
            _record_success()
            total_chars = sum(len(t) for t in clean_inputs)
            est_tokens = max(10, total_chars // 4)
            _log_nim_cost("nim_embed", est_tokens, (est_tokens / 1000) * 0.00005)
            global _cached_embed_model
            _cached_embed_model = model
            return vecs
        except Exception as e:
            last_error = e
            msg = str(e)
            if "410" in msg or "404" in msg:
                logger.warning(f"[NIM Client] Embed model {model} EOL, trying fallback")
                continue
            if "401" in msg:
                _record_failure()
                break
            continue
    _record_failure()
    raise RuntimeError(f"NIM Embed unavailable after {len(EMBED_MODELS)} models: {last_error}")


async def generate(prompt: str, system_prompt: str = "", max_tokens: int = 4096, temperature: float = 0.7) -> str:
    """Standard generate interface for NIM LLM."""
    return await call_llm_central(prompt=prompt, system=system_prompt, max_tokens=max_tokens, temperature=temperature)


async def nim_generate_with_feedback(
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 4096,
    timeout_seconds: int = 120,
    job_label: str = "NIM call"
) -> str:
    """
    Executes NVIDIA NIM LLM call with a hard timeout and mapped diagnostic exceptions:
    - Timeout -> ValueError(f"{job_label} timed out after {timeout_seconds}s...")
    - 401 -> ValueError("NVIDIA NIM API key is invalid or expired. Get a new key at build.nvidia.com/api-keys")
    - 429 -> ValueError("NVIDIA NIM rate limit reached. Wait 60 seconds and try again.")
    - 503 -> ValueError("NVIDIA NIM service is temporarily unavailable. Try again in a few minutes.")
    """
    import asyncio
    try:
        result = await asyncio.wait_for(
            generate(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens
            ),
            timeout=timeout_seconds
        )
        return result
    except asyncio.TimeoutError:
        raise ValueError(
            f"{job_label} timed out after {timeout_seconds}s. "
            f"The NVIDIA NIM API is not responding. "
            f"Check your API key and try again."
        )
    except Exception as e:
        error_str = str(e)
        if "401" in error_str or "unauthorized" in error_str.lower():
            raise ValueError(
                "NVIDIA NIM API key is invalid or expired. "
                "Get a new key at build.nvidia.com/api-keys"
            )
        elif "429" in error_str or "rate limit" in error_str.lower():
            raise ValueError(
                "NVIDIA NIM rate limit reached. "
                "Wait 60 seconds and try again."
            )
        elif "503" in error_str or "service unavailable" in error_str.lower():
            raise ValueError(
                "NVIDIA NIM service is temporarily unavailable. "
                "Try again in a few minutes."
            )
        else:
            raise ValueError(f"{job_label} failed: {error_str}")


async def embed(text: str) -> list:
    """Standard single-item embed interface returning 1536-dim embedding vector."""
    vecs = await call_embedding_central([text])
    return vecs[0] if vecs else []


async def embed_batch(texts: list) -> list:
    """Standard batch embed interface."""
    return await call_embedding_central(texts)


def reset_cache():
    global _cached_llm_model, _cached_embed_model, _CONSECUTIVE_FAILURES, _CIRCUIT_OPEN_UNTIL
    _cached_llm_model = None
    _cached_embed_model = None
    _CONSECUTIVE_FAILURES = 0
    _CIRCUIT_OPEN_UNTIL = 0.0

