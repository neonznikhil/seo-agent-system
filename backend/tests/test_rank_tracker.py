import pytest
from unittest.mock import patch, AsyncMock
from backend.services.rank_tracker import (
    track_published_post,
    check_keyword_rankings,
    get_tracked_rankings,
    create_rank_alert,
    _normalize_url,
)
from backend.services.local_store import save_local_rank_tracking


@pytest.mark.asyncio
async def test_track_published_post_creation():
    rec = await track_published_post(
        website_id="test_site_1",
        wp_post_id="101",
        wp_url="https://example.com/car-accident-compensation",
        target_keyword="car accident compensation pain and suffering",
        blog_id="b_1",
        title="How to Calculate Car Accident Compensation",
    )
    assert rec["website_id"] == "test_site_1"
    assert rec["wp_post_id"] == "101"
    assert rec["target_keyword"] == "car accident compensation pain and suffering"
    assert rec["status"] == "tracking"
    assert rec["current_position"] is None
    assert isinstance(rec["position_history"], list)


@pytest.mark.asyncio
async def test_check_keyword_rankings_with_serper_mock():
    # Setup test record in local store
    save_local_rank_tracking({
        "id": "trk_test_1",
        "website_id": "test_site_2",
        "wp_post_id": "102",
        "wp_url": "https://houstonlaw.com/personal-injury-calculator",
        "target_keyword": "personal injury calculator houston",
        "status": "tracking",
        "current_position": 8,
        "best_position": 8,
        "position_history": [{"date": "2026-08-28T00:00:00", "position": 8}],
    })

    mock_serper_response = {
        "organic": [
            {"title": "Competitor 1", "link": "https://comp1.com/calc"},
            {"title": "Competitor 2", "link": "https://comp2.com/calc"},
            {"title": "Houston Law Personal Injury", "link": "https://houstonlaw.com/personal-injury-calculator"},
        ]
    }

    with patch("backend.services.serper_service.serper_service.search", new=AsyncMock(return_value=mock_serper_response)):
        updated = await check_keyword_rankings("test_site_2")
        assert len(updated) >= 1
        target_rec = [u for u in updated if u.get("id") == "trk_test_1"][0]
        assert target_rec["current_position"] == 3
        assert target_rec["best_position"] == 3
        assert len(target_rec["position_history"]) >= 2


@pytest.mark.asyncio
async def test_rank_alert_on_significant_drop():
    save_local_rank_tracking({
        "id": "trk_test_drop",
        "website_id": "test_site_alert",
        "wp_post_id": "103",
        "wp_url": "https://houstonlaw.com/truck-accident",
        "target_keyword": "truck accident lawyer",
        "status": "tracking",
        "current_position": 4,
        "best_position": 4,
        "position_history": [{"date": "2026-08-28T00:00:00", "position": 4}],
    })

    # Drops to #15
    mock_organic = [{"title": f"Comp {i}", "link": f"https://comp{i}.com"} for i in range(14)]
    mock_organic.append({"title": "Houston Law", "link": "https://houstonlaw.com/truck-accident"})

    with patch("backend.services.serper_service.serper_service.search", new=AsyncMock(return_value={"organic": mock_organic})):
        with patch("backend.services.rank_tracker.create_rank_alert", new=AsyncMock()) as mock_alert:
            await check_keyword_rankings("test_site_alert")
            assert mock_alert.called
            call_kwargs = mock_alert.call_args.kwargs
            assert call_kwargs["keyword"] == "truck accident lawyer"
            assert call_kwargs["change"] == -11  # dropped by 11


def test_get_tracked_rankings_enrichment():
    save_local_rank_tracking({
        "id": "trk_enriched_1",
        "website_id": "site_enrich",
        "wp_url": "https://example.com/test",
        "target_keyword": "test keyword",
        "status": "tracking",
        "current_position": 2,
        "best_position": 1,
        "position_history": [
            {"date": "2026-08-28T00:00:00", "position": 5},
            {"date": "2026-08-29T00:00:00", "position": 2},
        ],
    })

    rankings = get_tracked_rankings("site_enrich")
    assert len(rankings) >= 1
    item = [r for r in rankings if r["id"] == "trk_enriched_1"][0]
    assert item["status_label"] == "Top 3"
    assert item["change"] == 3  # improved from 5 to 2
