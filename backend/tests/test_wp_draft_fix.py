import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from services.wordpress_service import WordPressService


@pytest.mark.asyncio
async def test_create_draft_success():
    svc = WordPressService("test_wid")
    svc.site = {
        "wordpress_url": "https://mysite.com",
        "wordpress_user": "myuser",
        "wordpress_password": "mypassword",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "id": 789,
        "link": "https://mysite.com/?p=789",
    }

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        res = await svc.create_draft(
            website_id="test_wid",
            title="My Car Accident Compensation Guide",
            content="<p>Detailed guide on compensation.</p>",
            keywords=["car accident compensation"],
        )
        assert res["success"] is True
        assert res["wp_post_id"] == 789
        assert "mysite.com" in res["edit_url"]


@pytest.mark.asyncio
async def test_publish_post_existing_draft():
    svc = WordPressService("test_wid")
    svc.site = {
        "wordpress_url": "https://mysite.com",
        "wordpress_user": "myuser",
        "wordpress_password": "mypassword",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": 789, "status": "publish"}

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        res = await svc.publish_post(
            website_id="test_wid",
            wp_post_id=789,
            user_id="admin_user",
        )
        assert res["published"] is True
        assert res["post_id"] == 789


@pytest.mark.asyncio
async def test_publish_post_polymorphic_create_and_publish():
    svc = WordPressService("test_wid")
    svc.site = {
        "wordpress_url": "https://mysite.com",
        "wordpress_user": "myuser",
        "wordpress_password": "mypassword",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"id": 999, "status": "publish", "link": "https://mysite.com/?p=999"}

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        with patch.object(svc, "check_publish_capability", new=AsyncMock(return_value={"can_publish": True, "roles": ["editor"]})):
            res = await svc.publish_post(
                website_id="test_wid",
                title="New Article Title",
                html_content="<p>Full article body</p>",
                auto_publish=True,
            )
            assert res["success"] is True
            assert res["wordpress_post_id"] == 999
