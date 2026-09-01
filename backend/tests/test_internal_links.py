import pytest
from bs4 import BeautifulSoup
from services.internal_links import (
    index_blog_for_linking,
    inject_internal_links,
)
from services.local_store import save_local_internal_link


@pytest.mark.asyncio
async def test_index_blog_for_linking_extraction():
    sample_html = """<h1>Car Accident Guide</h1>
<div class="tldr-block"><p><strong>TL;DR:</strong> Summary</p></div>
<p>If you were involved in a collision, obtaining proper medical documentation is essential.</p>
<h2>How to Document Medical Expenses</h2>
<p>Keep every hospital bill and prescription receipt.</p>
<h2>Understanding the Multiplier Method</h2>
<p>Insurers multiply your bills by a factor from 1.5 to 5.</p>"""

    rec = await index_blog_for_linking(
        blog_id="b_index_1",
        website_id="site_il_1",
        title="Car Accident Guide",
        url="https://example.com/car-accident-guide",
        target_keyword="car accident medical documentation",
        html_content=sample_html,
    )

    assert rec["website_id"] == "site_il_1"
    assert rec["url"] == "https://example.com/car-accident-guide"
    assert "How to Document Medical Expenses" in rec["linkable_topics"]
    assert "Understanding the Multiplier Method" in rec["linkable_topics"]
    assert "medical documentation" in rec["summary"].lower()


@pytest.mark.asyncio
async def test_inject_internal_links_into_article():
    # Index published article
    save_local_internal_link({
        "id": "link_art_1",
        "website_id": "site_il_2",
        "url": "https://example.com/multiplier-method",
        "title": "How Insurance Multipliers Work",
        "target_keyword": "insurance multiplier method",
        "linkable_topics": ["Multiplier calculation", "Settlement factors"],
        "published_at": "2026-08-28T10:00:00",
    })

    new_article_html = """<h1>Pain and Suffering Claims</h1>
<div class="tldr-block"><p><strong>TL;DR:</strong> Summary</p></div>
<p>Calculating your non-economic damages involves several steps. Adjusters frequently evaluate claims using an insurance multiplier method based on injury severity.</p>
<h2>Next steps</h2>
<p>Always speak with an attorney before signing any agreement.</p>"""

    linked_html = await inject_internal_links(new_article_html, website_id="site_il_2", max_links=3)
    assert '<a href="https://example.com/multiplier-method">' in linked_html
    soup = BeautifulSoup(linked_html, 'html.parser')
    anchor = soup.find('a', href="https://example.com/multiplier-method")
    assert anchor is not None
    assert "multiplier" in anchor.get_text().lower()
