import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from backend.services.brain_service import BrainService


@pytest.mark.asyncio
async def test_brain_memory_recall_and_write():
    brain = BrainService(website_id="default")
    
    mock_memories = [
        {"id": "m1", "title": "Topical Authority in Texas Litigation", "content": "Statistics guides perform best.", "memory_type": "preference"}
    ]
    
    with patch("backend.services.brain_service.BrainService.recall_preferences", new=AsyncMock(return_value=mock_memories)):
        with patch("backend.services.brain_service.BrainService.remember", new=AsyncMock(return_value="mem_123")):
            # Recall First
            recalled = await brain.recall_preferences("default", "Texas personal injury", top_k=1)
            assert len(recalled) == 1
            assert recalled[0]["memory_type"] == "preference"

            # Write Back After
            saved_id = await brain.remember(
                website_id="default",
                memory_type="outcome",
                title="Backlink Verified",
                content="Verified 2 new backlinks from DR 58 domain",
                source_type="test_agent",
                confidence=0.95
            )
            assert saved_id == "mem_123"
