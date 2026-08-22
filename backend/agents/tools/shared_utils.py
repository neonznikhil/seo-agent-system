import json
import logging
from urllib.parse import urlparse

logger = logging.getLogger("backend.tools.shared_utils")


def is_homepage(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return path in ["", "/index", "/index.html"]


async def generate_learning_from_rejection(type_: str, value: str, feedback: str, website_id: str) -> str:
    from ...database import call_nim_llm
    prompt = (
        f"Human rejected {type_}: '{value}' reason '{feedback}' -> 1 sentence learning"
    )
    system = "You are a learning generator. Output one concise sentence."
    try:
        learning = await call_nim_llm(prompt, system, website_id=website_id)
        return learning.strip()
    except Exception as e:
        logger.error("Learning generation failed: %s", e)
        return f"Rejected {type_}: {feedback}"
