import logging
from typing import Optional
import asyncio

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from ...database import get_supabase, get_embedding
from ...config import DUPLICATE_THRESHOLD

logger = logging.getLogger("backend.tools.vector_memory")


class VectorMemoryInput(BaseModel):
    topic: str = Field(description="Topic to check for duplication")


def _check_duplicate(topic: str, website_id: str) -> dict:
    query_emb = asyncio.run(get_embedding(topic, website_id=website_id))
    res = (
        get_supabase()
        .rpc("match_content", {
            "query_embedding": query_emb,
            "match_threshold": DUPLICATE_THRESHOLD,
            "website_id": website_id,
        })
        .execute()
    )
    matches = res.data or []
    score = matches[0]["similarity"] if matches else 0.0
    is_dup = bool(matches) and score > DUPLICATE_THRESHOLD
    logger.info("Duplicate check topic='%s' dup=%s score=%.3f matches=%d", topic, is_dup, score, len(matches))
    return {"is_duplicate": is_dup, "score": score, "matches": len(matches)}


def is_duplicate(topic: str, website_id: Optional[str] = None) -> bool:
    if not website_id:
        return False
    return _check_duplicate(topic, website_id)["is_duplicate"]


def duplicate_score(topic: str, website_id: str) -> float:
    return _check_duplicate(topic, website_id)["score"]


class VectorMemoryTool(BaseTool):
    name: str = "vector_memory"
    description: str = "Checks if a topic is duplicate using NIM embedding + pgvector match_content RPC"
    args_schema: type[BaseModel] = VectorMemoryInput
    _website_id: Optional[str] = None

    def set_website_id(self, website_id: str) -> None:
        self._website_id = website_id

    def _run(self, topic: str) -> str:
        if not self._website_id:
            return "No website_id set"
        try:
            result = _check_duplicate(topic, self._website_id)
            return f"duplicate={result['is_duplicate']} score={result['score']:.3f}"
        except Exception as e:
            logger.error("Duplicate check failed: %s", e)
            return f"Error: {e}"
