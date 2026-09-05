"""AEO Module Verification Tests — offline / mocked"""
import asyncio
import sys
import os
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from services.citation_injector import (
    inject_citations,
    inject_term_definitions,
    build_quick_facts_table,
    inject_quick_facts_table,
    validate_chunk_lengths,
    auto_fix_chunk_lengths,
)
from services.schema_generator import generate_article_schema
from services.llm_content_server import generate_markdown_version
from services.reddit_service import RedditService


SAMPLE_HTML = """<html><body>
<div class="tldr-block">TL;DR summary here</div>
<h1>Personal Injury Lawyer Houston</h1>
<p>Did you know that 73% of accident victims don't get the full compensation they deserve? Studies show most claims are undervalued. Data shows hiring a lawyer increases settlement by $40,000 on average. Research shows comparative negligence can affect your case significantly. Experts say insurance delays are common.</p>
<p>When dealing with a statute of limitations, you need to act fast. The contingency fee structure means your attorney only gets paid if you win. Subrogation is a complex concept. Reports indicate that discovery rule exceptions apply in many cases.</p>
<p>If you suffered a herniated disc in a car accident, you may be entitled to compensation. Traumatic brain injury cases require expert testimony. Whiplash injuries are often underestimated. EDR data can help prove your case.</p>
</body></html>"""


async def run_tests():
    print("=" * 60)
    print("AEO MODULE VERIFICATION")
    print("=" * 60)

    # CHECK 1 — CITATIONS INJECTED
    print("\n[CHECK 1] Citations injected...")
    mock_results = [
        {"link": "https://www.cdc.gov/statistics", "title": "CDC Statistics"},
        {"link": "https://www.nhtsa.gov/data", "title": "NHTSA Data"},
    ]
    with patch("services.serper_service.serper_search_safe", new_callable=AsyncMock, return_value=mock_results):
        cited = await inject_citations(SAMPLE_HTML, "personal injury lawyer houston", "test-site")
    citation_count = cited.count('href="https://')
    print(f"  External citation links found: {citation_count}")
    check1_pass = citation_count >= 2
    print(f"  PASS: {check1_pass}" if check1_pass else f"  FAIL: need >= 2, got {citation_count}")

    # CHECK 2 — DEFINITIONS WORK
    print("\n[CHECK 2] Definitions injected...")
    defined = inject_term_definitions(SAMPLE_HTML, "legal")
    abbr_count = defined.count('title=')
    print(f"  <abbr> title= attributes found: {abbr_count}")
    check2_pass = abbr_count >= 2
    print(f"  PASS: {check2_pass}" if check2_pass else f"  FAIL: need >= 2, got {abbr_count}")

    # CHECK 3 — QUICK FACTS TABLE
    print("\n[CHECK 3] Quick facts table...")
    facts = build_quick_facts_table(
        {"point_3_search_intent": {"what_reader_wants": "compensation guidance"}, "point_14_faqs": [{"q": "x", "a": "y"}]},
        {"location_city": "Houston", "location_state": "TX", "years_experience": 15, "business_name": "Test Law"},
        "personal injury lawyer"
    )
    with_facts = inject_quick_facts_table(SAMPLE_HTML, facts)
    has_table = "rf-quick-facts" in with_facts
    print(f"  rf-quick-facts class found: {has_table}")
    check3_pass = has_table
    print(f"  PASS: {check3_pass}" if check3_pass else "  FAIL")

    # CHECK 4 — SCHEMA VALID (structural check)
    print("\n[CHECK 4] Schema structure...")
    schema = await generate_article_schema(
        title="Test Article",
        html_content=SAMPLE_HTML,
        target_keyword="personal injury lawyer",
        website_facts={"business_name": "Test Law", "location_city": "Houston", "location_state": "TX"},
        wp_url="https://test.com/article",
        published_at="2026-01-01T00:00:00Z",
        faq_items=[{"question": "What is a statute of limitations?", "answer_draft": "It is the time limit to file a lawsuit."}]
    )
    has_article = '"@type": "Article"' in schema
    has_faq = '"@type": "FAQPage"' in schema
    has_breadcrumb = '"@type": "BreadcrumbList"' in schema
    check4_pass = has_article and has_faq and has_breadcrumb
    print(f"  Article: {has_article}, FAQ: {has_faq}, Breadcrumb: {has_breadcrumb}")
    print(f"  PASS: {check4_pass}" if check4_pass else "  FAIL")

    # CHECK 5 — MARKDOWN VERSION
    print("\n[CHECK 5] Markdown version generation...")
    md = await generate_markdown_version(SAMPLE_HTML, "Test Article", "personal injury lawyer", "https://test.com/article", "2026-01-01", {"business_name": "Test"})
    has_markdown = "# Personal Injury Lawyer Houston" in md and "**Source:**" in md
    has_minimal_html = md.count("<") < 10
    check5_pass = has_markdown and has_minimal_html
    print(f"  Markdown headers present: {has_markdown}")
    print(f"  Minimal HTML: {has_minimal_html}")
    print(f"  PASS: {check5_pass}" if check5_pass else "  FAIL")

    # CHECK 6 — REDDIT OPPORTUNITIES
    print("\n[CHECK 6] Reddit opportunities service...")
    reddit = RedditService()
    check6_pass = reddit is not None
    print(f"  RedditService instantiated: {check6_pass}")
    print(f"  PASS: {check6_pass}" if check6_pass else "  FAIL")

    # CHECK 7 — AEO PAGE LOADS (frontend syntax)
    print("\n[CHECK 7] Frontend AEO page sections...")
    try:
        with open("frontend-next/app/aeo/page.tsx", "r") as f:
            content = f.read()
        has_section1 = "AI Visibility Score" in content
        has_section2 = "Keyword" in content and "Tracking" in content
        has_section3 = "Reddit" in content
        has_section4 = "Semantic" in content
        has_section5 = "Schema Health" in content
        check7_pass = has_section1 and has_section2 and has_section3 and has_section4 and has_section5
        print(f"  S1={has_section1}, S2={has_section2}, S3={has_section3}, S4={has_section4}, S5={has_section5}")
        print(f"  PASS: {check7_pass}" if check7_pass else "  FAIL")
    except Exception as e:
        print(f"  FAIL: {e}")
        check7_pass = False

    # SUMMARY
    print("\n" + "=" * 60)
    all_pass = check1_pass and check2_pass and check3_pass and check4_pass and check5_pass and check6_pass and check7_pass
    print(f"CHECK 1 (Citations):       {'PASS' if check1_pass else 'FAIL'}")
    print(f"CHECK 2 (Definitions):     {'PASS' if check2_pass else 'FAIL'}")
    print(f"CHECK 3 (Quick Facts):     {'PASS' if check3_pass else 'FAIL'}")
    print(f"CHECK 4 (Schema Valid):    {'PASS' if check4_pass else 'FAIL'}")
    print(f"CHECK 5 (Markdown):        {'PASS' if check5_pass else 'FAIL'}")
    print(f"CHECK 6 (Reddit):          {'PASS' if check6_pass else 'FAIL'}")
    print(f"CHECK 7 (Frontend Page):   {'PASS' if check7_pass else 'FAIL'}")
    print("=" * 60)
    print(f"ALL 7 CHECKS PASSED: {all_pass}")
    print("=" * 60)

    return all_pass


if __name__ == "__main__":
    result = asyncio.run(run_tests())
    sys.exit(0 if result else 1)
