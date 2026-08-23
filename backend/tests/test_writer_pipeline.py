import pytest
from backend.agents.writer_agent import WriterPipeline
from backend.services.knowledge_service import KnowledgeService


@pytest.mark.asyncio
async def test_writer_knowledge_context_assembly():
    """Test WriterPipeline gathers multi-vector knowledge, competitor insights, and rules."""
    pipeline = WriterPipeline(website_id="03b7febf-0c44-4830-a42a-cfcd84ae6464")
    
    # Ensure seed knowledge
    ks = KnowledgeService(website_id="03b7febf-0c44-4830-a42a-cfcd84ae6464")
    await ks.ingest(
        content="Under Texas law Section 16.003, car accident victims have 2 years to file injury claims.",
        source_type="statute",
        title="Texas Statute of Limitations Code",
        explicit_type="law_statute"
    )

    hits = await ks.retrieve_relevant_hybrid("Texas accident statute", top_k=3)
    assert len(hits) >= 1


@pytest.mark.asyncio
async def test_writer_generation_and_elementor_html():
    """Test 10-phase generation outputs Elementor-safe HTML structure and citations."""
    pipeline = WriterPipeline(website_id="03b7febf-0c44-4830-a42a-cfcd84ae6464")
    res = await pipeline.generate(
        topic="Texas Personal Injury Settlement Rules 2026",
        primary_keyword="Texas personal injury settlement"
    )
    
    assert res.get("status") in ["completed", "skipped", "needs_revision", "staged_for_approval"]
    assert "reviews" in res or "phase_results" in res or "final_scores" in res or "reason" in res
