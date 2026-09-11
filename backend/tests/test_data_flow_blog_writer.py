import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.crew_blog_writer import (
    build_grounding_bundle,
    build_default_15point_outline,
    _build_writer_task_prompt,
    run_writer_agent,
    contains_wrong_audience_content,
    clean_wrong_audience_content,
    remove_invalid_h2_sections,
    ensure_faqs_and_ctas,
    ensure_each_section_minimum_length,
)
from services.seo_quality_gate import run_qa_gate


async def run_tests():
    print("=== TEST 1: build_default_15point_outline Adaptivity ===")
    # 1. Tech / SaaS Bundle
    saas_bundle = {
        "website_id": "test-saas-site",
        "topic": "Predictive Analytics for SaaS Churn Reduction",
        "business_name": "SaaSMetrics Pro",
        "domain": "saasmetrics.io",
        "niche": "B2B SaaS Analytics & Revenue Operations",
        "target_audience": "SaaS founders, VP of Product, and Growth Leaders",
        "is_personal_injury": False,
        "brand_voice_guide": {
            "tone_description": "Data-driven, authoritative, pragmatic, and clear",
            "banned_phrases": ["revolutionary", "game-changing"],
            "verified_facts": [
                "SaaSMetrics Pro processes over 40 million event streams monthly.",
                "Reduces net revenue churn by an average of 18% in 90 days."
            ]
        },
        "brand_voice_block": "Brand: SaaSMetrics Pro\nNiche: B2B SaaS Analytics\nTone: Data-driven\nBanned: revolutionary",
        "verified_facts": [
            "SaaSMetrics Pro processes over 40 million event streams monthly.",
            "Reduces net revenue churn by an average of 18% in 90 days."
        ],
        "knowledge_facts_str": "- SaaS customer churn predictive models require at least 6 months of cohort usage data.\n- Feature engagement drop-offs precede account cancellations by 21 days on average.",
        "internal_links": [
            {"url": "/features/churn-prediction", "anchor": "predictive churn modeling software"},
            {"url": "/blog/customer-health-score", "anchor": "customer health score framework"}
        ],
        "serp_competitors": [
            {"title": "How to Predict SaaS Churn", "snippet": "Use machine learning to identify at-risk subscribers early.", "link": "https://example.com/churn"}
        ],
        "paa_questions": [
            "What is predictive churn modeling for SaaS?",
            "How do you calculate customer health scores?",
            "What metrics indicate high churn risk?"
        ]
    }

    outline_saas = build_default_15point_outline(
        target_keyword="Predictive Analytics for SaaS Churn Reduction",
        grounding_bundle=saas_bundle
    )

    # Assert no accident/injury terms in outline
    outline_saas_str = str(outline_saas).lower()
    assert "car accident" not in outline_saas_str, "FAIL: 'car accident' leaked into SaaS outline!"
    assert "insurance adjuster" not in outline_saas_str, "FAIL: 'insurance adjuster' leaked into SaaS outline!"
    assert "whiplash" not in outline_saas_str, "FAIL: 'whiplash' leaked into SaaS outline!"
    assert "saas" in outline_saas_str, "FAIL: 'saas' missing from SaaS outline!"
    print("  [PASS] SaaS Outline correctly adapted with zero car-accident bleed.")

    # 2. Personal Injury Bundle
    pi_bundle = {
        "website_id": "test-legal-site",
        "topic": "California Car Accident Statute of Limitations",
        "business_name": "Pacific Injury Law",
        "domain": "pacificinjurylaw.com",
        "niche": "Personal Injury Law",
        "target_audience": "Car crash victims and claimants",
        "is_personal_injury": True,
        "verified_facts": ["California CCP Section 335.1 provides a 2-year statute of limitations."]
    }
    outline_pi = build_default_15point_outline(
        target_keyword="California Car Accident Statute of Limitations",
        grounding_bundle=pi_bundle
    )
    outline_pi_str = str(outline_pi).lower()
    assert "statut" in outline_pi_str, "FAIL: statutory terms missing from PI outline!"
    print("  [PASS] Personal Injury outline correctly preserves statutory claim guidance.")

    print("\n=== TEST 2: _build_writer_task_prompt Grounding Injection ===")
    prompt = _build_writer_task_prompt(
        target_keyword="Predictive Analytics for SaaS Churn Reduction",
        outline=outline_saas,
        grounding_bundle=saas_bundle,
        tone="Data-driven and pragmatic",
        word_count_target=2600
    )

    assert "SaaSMetrics Pro" in prompt, "FAIL: business_name missing from writer prompt!"
    assert "40 million event streams" in prompt, "FAIL: verified fact missing from writer prompt!"
    assert "predictive churn modeling software" in prompt, "FAIL: real internal link anchor missing from writer prompt!"
    assert "/features/churn-prediction" in prompt, "FAIL: real internal link URL missing from writer prompt!"
    assert "What is predictive churn modeling for SaaS?" in prompt, "FAIL: PAA missing from writer prompt!"
    assert "2026" in prompt, "FAIL: current year 2026 missing from prompt!"
    print("  [PASS] Writer task prompt perfectly contains all grounding blocks.")

    print("\n=== TEST 3: Audience Sanitizers Preserve B2B/SaaS Niches ===")
    saas_text = "<h2>Maximizing Return on Investment with Predictive Analytics</h2><p>Improving cash flow and resource allocation requires data-driven decision making.</p>"
    
    # When is_personal_injury is False:
    assert not contains_wrong_audience_content(saas_text, is_personal_injury=False), "FAIL: B2B text falsely flagged as wrong audience!"
    cleaned_saas = clean_wrong_audience_content(saas_text, is_personal_injury=False)
    assert "Return on Investment" in cleaned_saas, "FAIL: ROI was mangled for SaaS niche!"
    h2_preserved = remove_invalid_h2_sections(saas_text, is_personal_injury=False)
    assert "Maximizing Return on Investment" in h2_preserved, "FAIL: Valid B2B H2 was deleted!"
    print("  [PASS] Audience cleaners protect B2B/SaaS terminology when is_personal_injury is False.")

    # When is_personal_injury is True:
    pi_text = "<h2>Maximizing Return on Investment for Your Accident Claim</h2>"
    assert contains_wrong_audience_content(pi_text, is_personal_injury=True), "FAIL: Wrong audience not detected for personal injury!"
    cleaned_pi = clean_wrong_audience_content(pi_text, is_personal_injury=True)
    assert "expected recovery value" in cleaned_pi.lower(), "FAIL: ROI not converted for personal injury!"
    print("  [PASS] Audience cleaners properly sanitize personal injury claims when is_personal_injury is True.")

    print("\n=== TEST 4: run_writer_agent Fallback Assembly ===")
    planner_data = {
        "outline": outline_saas,
        "knowledge_hits": [{"content": saas_bundle["knowledge_facts_str"]}],
        "grounding_bundle": saas_bundle
    }

    assembled_html = await run_writer_agent(
        planner_data=planner_data,
        topic="Predictive Analytics for SaaS Churn Reduction",
        website_id="test-saas-site",
        business_name="SaaSMetrics Pro",
        tone="Data-driven and pragmatic",
        grounding_bundle=saas_bundle
    )

    assembled_lower = assembled_html.lower()
    assert "collision" not in assembled_lower, "FAIL: 'collision' leaked into SaaS fallback output!"
    assert "$24,500" not in assembled_lower, "FAIL: '$24,500' leaked into SaaS fallback output!"
    assert "whiplash" not in assembled_lower, "FAIL: 'whiplash' leaked into SaaS fallback output!"
    assert "insurance adjuster" not in assembled_lower, "FAIL: 'insurance adjuster' leaked into SaaS fallback output!"
    assert "standard injury" not in assembled_lower, "FAIL: 'standard injury' table leaked into SaaS fallback output!"
    assert "operational requirements" in assembled_lower, "FAIL: operational table missing from SaaS fallback output!"
    assert "<h1" in assembled_html, "FAIL: <h1> missing from fallback output!"
    assert "<h2>" in assembled_html, "FAIL: <h2> missing from fallback output!"
    assert "Meta Description:" in assembled_html, "FAIL: Meta Description missing from fallback output!"
    print("  [PASS] run_writer_agent fallback assembled 100% niche-accurate HTML without car crashes.")

    print("\n=== TEST 5: ensure_faqs_and_ctas & section length ===")
    test_short_h2 = "<h2>Core Architecture</h2><p>This is a short section with 10 words.</p>"
    padded = ensure_each_section_minimum_length(test_short_h2, niche="B2B SaaS Analytics", is_personal_injury=False)
    assert "insurance adjusters" not in padded, "FAIL: insurance adjusters leaked into section padding!"
    assert "operational consistency" in padded, "FAIL: domain-neutral padding missing!"

    with_cta = ensure_faqs_and_ctas(padded, outline=outline_saas, business_name="SaaSMetrics Pro", niche="B2B SaaS Analytics", is_personal_injury=False)
    assert "accident claim attorneys" not in with_cta, "FAIL: accident claim attorney CTA leaked!"
    assert "SaaSMetrics Pro" in with_cta, "FAIL: Business CTA missing!"
    print("  [PASS] Dynamic FAQs, CTAs, and section padding work accurately.")

    print("\n=== TEST 6: Quality Gate with Verified Facts ===")
    # Verified statutory fact
    test_article = """<h1>California Car Accident Statute of Limitations</h1>
    <div class="tldr-block" style="border-left: 4px solid #ff6b35;"><ul><li>Filing within two years is required under California CCP Section 335.1.</li><li>Immediate documentation preserves crucial evidence.</li><li>Contact counsel early.</li><li>Act promptly.</li></ul></div>
    <h2>Statutory Deadlines</h2><p>""" + "Under California CCP Section 335.1, the statute of limitations is 2 years to file. " * 30 + """</p>
    <h2>Key Requirements</h2><p>""" + "Gather medical documentation and police records promptly. " * 30 + """</p>
    <h2>Procedural Pitfalls</h2><p>""" + "Avoid missing filing deadlines. " * 30 + """</p>
    <div class="faq-accordion"><h3>What is the deadline?</h3><p>Two years under California CCP Section 335.1.</p></div>
    <div class="cta-block"><p>Contact our legal team.</p></div>
    <p>Disclaimer: This is for informational purposes.</p>
    <a href="/guide">read our in-depth guidance on filing</a>
    <a href="/claims">explore our legal claims overview</a>
    """
    qa_res = run_qa_gate(
        test_article,
        keyword="California Car Accident Statute of Limitations",
        meta_description="Guide to statute of limitations in California.",
        verified_facts=["California CCP Section 335.1 provides a 2-year statute of limitations."]
    )
    statute_check = qa_res.get("details", {}).get("statutes_and_figures", {})
    assert statute_check.get("status") == "PASS", f"FAIL: Expected PASS on traced claim, got {statute_check}"
    print("  [PASS] Quality gate passes verified claims against brand voice facts.")

    print("\nALL 6 VERIFICATION SUITES PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(run_tests())
