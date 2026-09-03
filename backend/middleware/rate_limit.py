"""Rate limiting middleware for RankForge.

Uses Redis for distributed rate limiting across multiple workers.
Falls back to in-memory storage if Redis is unavailable.
"""

import logging
import os
import time
from typing import Dict, Optional, Tuple
from collections import defaultdict

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("backend.middleware.rate_limit")

# Rate limit configurations
RATE_LIMITS = {
    "/auth/login": {"requests": 5, "window": 60},
    "/api/auth/login": {"requests": 5, "window": 60},
    "/auth/signup": {"requests": 5, "window": 3600},
    "/api/auth/signup": {"requests": 5, "window": 3600},
    "/auth/forgot-password": {"requests": 3, "window": 3600},
    "/api/auth/forgot-password": {"requests": 3, "window": 3600},
    "/auth/reset-password": {"requests": 5, "window": 60},
    "/api/auth/reset-password": {"requests": 5, "window": 60},
    "/api/writer/generate": {"requests": 15, "window": 60},
    "/api/crew/generate": {"requests": 15, "window": 60},
}
ROUTE_LIMITS = RATE_LIMITS

# In-memory fallback storage
_memory_store: Dict[str, list] = defaultdict(list)


def _get_redis_client():
    """Get Redis client if available."""
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return redis.from_url(redis_url, decode_responses=True)
    except Exception:
        return None


def _check_rate_limit(redis_client, key: str, limit: int, window: int) -> Tuple[bool, int]:
    """Check if request is within rate limit.
    
    Returns (is_allowed, remaining_requests).
    """
    now = time.time()
    
    if redis_client:
        try:
            # Use Redis sorted set for sliding window
            redis_key = f"rate_limit:{key}"
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(redis_key, 0, now - window)
            pipe.zadd(redis_key, {str(now): now})
            pipe.zcard(redis_key)
            pipe.expire(redis_key, window)
            results = pipe.execute()
            count = results[2]
            return count <= limit, max(0, limit - count)
        except Exception as e:
            logger.warning(f"Redis rate limit check failed: {e}")
            # Fall through to memory-based limiting
    
    # Memory-based fallback (not distributed-safe but provides basic protection)
    requests = _memory_store[key]
    # Remove old requests outside window
    requests[:] = [req_time for req_time in requests if now - req_time < window]
    requests.append(now)
    count = len(requests)
    return count <= limit, max(0, limit - count)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for authentication endpoints."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path or ""
        method = request.method or ""
        
        # Only apply to configured rate-limited endpoints
        if path not in RATE_LIMITS or method != "POST":
            return await call_next(request)
        
        config = RATE_LIMITS[path]
        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{path}"
        
        redis_client = _get_redis_client()
        is_allowed, remaining = _check_rate_limit(
            redis_client, key, config["requests"], config["window"]
        )
        
        if not is_allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Please try again later.",
                headers={"Retry-After": str(config["window"])},
            )
        
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(config["requests"])
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
