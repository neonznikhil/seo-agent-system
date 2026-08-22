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
NIM_EMBED_MODEL = "nvidia/nv-embed-qa-4"
NIM_LLM_MODEL = "meta/llama-3.1-70b-instruct"
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


async def get_embedding(text: str, website_id: Optional[str] = None) -> list:
    payload = {
        "model": NIM_EMBED_MODEL,
        "input": [text],
    }
    headers = {
        "Authorization": f"Bearer {NIM_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(NIM_EMBED_URL, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                vec = data["data"][0]["embedding"]
                if len(vec) == 1024:
                    return vec
    except Exception as e:
        logger.warning(f"NIM embedding API failed, using fallback embedding: {e}")
    
    # Deterministic 1024-dim normalized vector fallback
    import hashlib
    import math
    import random
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    rng = random.Random(int(h[:8], 16))
    vec = [rng.gauss(0, 1) for _ in range(1024)]
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [round(x / norm, 6) for x in vec]


@tenacity.retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
async def call_nim_llm(prompt: str, system: str = "", website_id: Optional[str] = None) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": NIM_LLM_MODEL,
        "messages": messages,
        "max_tokens": 1024,
    }
    headers = {
        "Authorization": f"Bearer {NIM_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(NIM_LLM_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        _log_task_fail(website_id, "call_nim_llm", str(e))
        raise
