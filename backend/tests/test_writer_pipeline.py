import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from backend.agents.writer_agent import WriterPipeline


@pytest.mark.asyncio
async def test_writer_pipeline_generation():
    pipeline = WriterPipeline(website_id="default")
    
    mock_draft = """# Complete Guide to Texas Commercial Vehicle Settlements

This authoritative analysis explains statutory recovery frameworks under Texas law.

## Texas Comparative Fault Statutory Breakdown
Under Texas Civil Practice and Remedies Code section 33.001, claimants can recover damages if fault does not exceed 50 percent.

## Average Settlement Calculation Matrix
Settlement amounts vary based on medical damages and commercial insurance limits.

## Frequently Asked Questions
### How long do I have to file a claim?
Under Texas statute of limitations, claims must be filed within 2 years.
"""
    with patch("backend.database.call_nim_llm", new=AsyncMock(return_value=mock_draft)):
        with patch("backend.database.get_supabase") as mock_sup:
            mock_sup.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "kb_1"}])
            mock_sup.return_value.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "test_draft_id"}])
            
            # Run test generation
            res = await pipeline.generate(
                topic="Texas commercial truck accident lawyer",
                primary_keyword="Texas commercial truck settlements"
            )
            
            assert res is not None
            assert res.get("status") in ["draft_saved", "quality_passed", "staged_for_approval", "complete"]
            content = res.get("content", mock_draft)
            assert "[INSERT" not in content
            assert "[TOPIC]" not in content
            assert "[KEYWORD]" not in content

