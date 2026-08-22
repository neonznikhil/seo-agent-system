from datetime import datetime
import json
import logging
from typing import Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from ...database import get_supabase, get_embedding
from ...config import DUPLICATE_THRESHOLD

logger = logging.getLogger("backend.tools.vector_memory")


class VectorMemoryInput(BaseModel):
    topic: str = Field(description="Topic to check for duplication")


async def _check_duplicate(topic: str, website_id: str) -> dict:
    query_emb = await get_embedding(topic, website_id=website_id)
    res = (
        get_supabase()
        .rpc("match_content", {
            "query_embedding": query_emb,
            "match_threshold": DUPLICATE_THRESHOLD,
            "p_website_id": website_id,
        })
        .execute()
    )
    matches = res.data or []
    score = matches[0]["similarity"] if matches else 0.0
    is_dup = bool(matches) and score > DUPLICATE_THRESHOLD
    logger.info("Duplicate check topic='%s' dup=%s score=%.3f matches=%d", topic, is_dup, score, len(matches))
    return {"is_duplicate": is_dup, "score": score, "matches": len(matches)}


async def is_duplicate(topic: str, website_id: Optional[str] = None) -> bool:
    if not website_id:
        return False
    result = await _check_duplicate(topic, website_id)
    return result["is_duplicate"]


async def duplicate_score(topic: str, website_id: str) -> float:
    result = await _check_duplicate(topic, website_id)
    return result["score"]


class VectorMemoryTool(BaseTool):
    name: str = "vector_memory"
    description: str = "Checks if a topic is duplicate using NIM embedding + pgvector match_content RPC"
    args_schema: type[BaseModel] = VectorMemoryInput
    _website_id: Optional[str] = None

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    async def _run(self, topic: str) -> str:
        if not self._website_id:
            return "No website_id set"
        try:
            result = await _check_duplicate(topic, self._website_id)
            return f"duplicate={result['is_duplicate']} score={result['score']:.3f}"
        except Exception as e:
            logger.error("Duplicate check failed: %s", e)
            return f"Error: {e}"
