import pytest
from unittest.mock import patch, AsyncMock
from backend.services.content_refresh import (
    detect_decaying_articles,
    refresh_decaying_article,
)
from backend.services.local_store import (
    save_local_rank_tracking,
    save_local_approval,
)


@pytest.mark.asyncio
async def test_detect_decaying_articles_queues_refresh():
    # Setup decaying article in rank tracking (dropped from #6 to #22)
    save_local_rank_tracking({
        "id": "trk_decaying_1",
        "website_id": "site_decay_test",
        "blog_id": "b_decay_1",
        "wp_post_id": "99",
        "wp_url": "https://example.com/decaying-post",
        "target_keyword": "texas car accident statute of limitations",
        "status": "tracking",
        "current_position": 22,
        "best_position": 6,
        "position_history": [
            {"date": "2026-08-01T00:00:00", "position": 6},
            {"date": "2026-08-15T00:00:00", "position": 14},
            {"date": "2026-08-29T00:00:00", "position": 22},
        ],
    })

    queued = await detect_decaying_articles("site_decay_test")
    assert len(queued) >= 1
    target = [q for q in queued if q["target_keyword"] == "texas car accident statute of limitations"][0]
    assert "dropped from #6 to #22" in target["reason"]
    assert target["status"] == "pending"


@pytest.mark.asyncio
async def test_refresh_decaying_article_generates_and_stages_approval():
    queue_item = {
        "website_id": "site_refresh_stage",
        "blog_id": "b_ref_stage",
        "wp_post_id": "100",
        "target_keyword": "texas motorcycle accident compensation",
        "reason": "Position dropped from #4 to #18",
    }

    mock_crew_output = {
        "title": "How to Calculate Texas Motorcycle Accident Compensation",
        "final_html": "<h1>How to Calculate Texas Motorcycle Accident Compensation</h1><p>Refreshed content...</p>",
        "seo_score": 90,
        "word_count": 1450,
    }

    with patch("backend.services.serper_service.serper_service.search", new=AsyncMock(return_value={"organic": [{"title": "Texas Guide", "snippet": "Text"}]})):
        with patch("backend.database.call_nim_llm", new=AsyncMock(return_value='{"gaps": ["New laws"], "sections_to_add": ["2026 caps"], "outdated_content": ["Old limits"]}')):
            with patch("backend.agents.crew_blog_writer.run_crew_blog_writer_with_retry", new=AsyncMock(return_value=mock_crew_output)):
                approval = await refresh_decaying_article(queue_item)
                assert approval is not None
                assert approval["approval_type"] == "refresh"
                assert approval["type"] == "refresh_update"
                assert "dropped from #4 to #18" in approval["refresh_reason"]
                assert approval["seo_score"] == 90
