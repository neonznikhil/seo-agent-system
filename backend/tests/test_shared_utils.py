import logging
import pytest
from unittest.mock import patch

from agents.tools.shared_utils import is_homepage
from config import validate_env

logger = logging.getLogger("backend.tests.test_shared_utils")


def test_is_homepage_variants():
    assert is_homepage("https://example.com/") is True
    assert is_homepage("https://example.com") is True
    assert is_homepage("https://example.com/index") is True
    assert is_homepage("https://example.com/index.html") is True
    assert is_homepage("https://example.com/about") is False
    assert is_homepage("https://example.com/blog/post") is False
    assert is_homepage("https://example.com/page/2") is False


@pytest.mark.asyncio
async def test_generate_learning_from_rejection():
    from backend.agents.tools.shared_utils import generate_learning_from_rejection
    with patch("backend.database.call_nim_llm") as mock_llm:
        mock_llm.return_value = "Human rejected blog: 'X' reason 'Y' -> Avoid topic X in future."
        learning = await generate_learning_from_rejection("blog", "X", "Y", "wid-1")
        assert learning is not None
        assert len(learning) > 0
