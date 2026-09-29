import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from agents.writer_agent import WriterPipeline


@pytest.mark.asyncio
async def test_writer_pipeline_generation():
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
    mock_serp = {"organic": [{"title": "Texas Guide", "link": "https://example.com", "snippet": "Legal text"}]}
    with patch("database.call_nim_llm", new=AsyncMock(return_value=mock_draft)):
        with patch("services.serper_service.serper_service.search", new=AsyncMock(return_value=mock_serp)):
            with patch("agents.writer_agent.WriterPipeline._phase_multi_step_content_writing", new=AsyncMock(return_value={"content": mock_draft, "word_count": 1850})):
                with patch("database.get_supabase") as mock_sup:
                    mock_sup.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(count=5, data=[{"id": "kb_1"}])
                    mock_sup.return_value.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "test_draft_id"}])
                    mock_sup.return_value.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
            
                    pipeline = WriterPipeline(website_id="default")
                    pipeline.supabase = mock_sup.return_value
            
                    # Run test generation
                    res = await pipeline.generate(
                        topic="Texas commercial truck accident lawyer",
                        primary_keyword="Texas commercial truck settlements"
                    )
            
            assert res is not None
            assert res.get("status") in ["draft_saved", "quality_passed", "staged_for_approval", "complete", "completed", "skipped"]
            content = res.get("content", mock_draft)
            assert "[INSERT" not in content
            assert "[TOPIC]" not in content
            assert "[KEYWORD]" not in content



@pytest.mark.asyncio
async def test_onboarding_calls_writer_with_correct_api():
    """Regression: setup_pipeline previously built WriterPipeline(topic=..., primary_keyword=...),
    which raised TypeError and killed first-article generation on every new connection."""
    import inspect
    from agents import setup_pipeline
    source = inspect.getsource(setup_pipeline.run_first_time_setup_pipeline)
    assert "WriterPipeline(website_id=website_id)" in source
    ctor_args = source.split("WriterPipeline(")[1].split(")")[0]
    assert "topic=" not in ctor_args, "topic must be passed to generate(), not the constructor"
    assert ".generate(topic=" in source


@pytest.mark.asyncio
async def test_writer_survives_supabase_outage():
    """A Supabase/network outage must not abort article generation.

    The content_log insert and pipeline-log writes used to be unguarded, so one
    DNS failure discarded a fully-planned article."""
    from unittest.mock import patch, AsyncMock
    from agents.writer_agent import WriterPipeline

    def explode(*a, **k):
        raise RuntimeError("network down")

    mock_draft = "<h1>Title</h1>" + "<p>Grounded paragraph content.</p>" * 60
    with patch("agents.writer_agent.WriterPipeline._phase_multi_step_content_writing",
               new=AsyncMock(return_value={"content": mock_draft, "word_count": 1500})):
        with patch("database.get_supabase") as mock_sup:
            table = mock_sup.return_value.table.return_value
            table.select.return_value.eq.return_value.execute.side_effect = explode
            table.select.return_value.limit.return_value.execute.side_effect = explode
            table.insert.return_value.execute.side_effect = explode
            table.update.return_value.eq.return_value.execute.side_effect = explode

            pipeline = WriterPipeline(website_id="outage-site")
            pipeline.supabase = mock_sup.return_value
            res = await pipeline.generate(topic="Emergency plumbing services guide",
                                          primary_keyword="emergency plumbing services")
    assert res is not None
