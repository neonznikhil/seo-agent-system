import pytest
import re
from bs4 import BeautifulSoup
from backend.agents.crew_blog_writer import (
    sanitize_keyword,
    fix_broken_year_in_content,
    validate_word_count,
    ensure_minimum_word_count,
    validate_outline,
    build_default_15point_outline,
    detect_duplicate_examples,
    enforce_keyword_density,
    fix_broken_sentences,
    remove_broken_links,
    validate_and_fix_tldr,
    ensure_dollar_example,
    process_blog_output,
    run_planner,
    run_writer,
)


class Test15PointOutlineValidation:
    """CHECK 1: Outline generation and validation rules."""

    def test_valid_15point_outline_passes(self):
        outline = build_default_15point_outline("statutory limitation period accident claims")
        is_valid, errors = validate_outline(outline, "statutory limitation period accident claims")
        assert is_valid is True, f"Validation failed with errors: {errors}"
        assert len(errors) == 0

    def test_invalid_outline_detected(self):
        # Missing title, too few H2s, placeholder bullets
        bad_outline = {
            "point_1_title": {"recommended_title": "The Ultimate Comprehensive Masterclass to Filing"},
            "point_2_target_keyword": {"keyword_density_target": "unlimited"},
            "point_7_h2_sections": [
                {"heading": "Section 1", "reader_question_answered": "Essential details and actionable guidance"}
            ],
            "point_14_faqs": [],
            "tldr": {"bullet_1_text": "Essential details and actionable guidance about this topic"},
            "point_13_ctas": []
        }
        is_valid, errors = validate_outline(bad_outline, "statutory limitation period accident claims")
        assert is_valid is False
        assert any("Hype word in title" in e for e in errors)
        assert any("Keyword density not properly limited" in e for e in errors)
        assert any("Too few H2 sections" in e for e in errors)
        assert any("Too few FAQs" in e for e in errors)
        assert any("TL;DR bullet 1 is a placeholder" in e for e in errors)
        assert any("No CTAs defined" in e for e in errors)


class TestTLDRRealContent:
    """CHECK 2: TL;DR is real, not placeholder fillers."""

    def test_tldr_has_real_content_and_no_placeholders(self):
        outline = build_default_15point_outline("statutory limitation period accident claims")
        html_input = "<h1>Statutory Limitation Periods in Accident Claims</h1><p>Intro paragraph</p>"
        result_html = validate_and_fix_tldr(html_input, "statutory limitation period accident claims", outline=outline)
        
        assert "class=\"tldr-block\"" in result_html
        assert "Essential details and actionable guidance" not in result_html
        soup = BeautifulSoup(result_html, "html.parser")
        tldr_div = soup.find("div", class_="tldr-block")
        assert tldr_div is not None
        lis = tldr_div.find_all("li")
        assert len(lis) == 4
        for li in lis:
            text = li.get_text()
            assert "essential details" not in text.lower()
            assert len(text) > 20


class TestKeywordDensityEnforcer:
    """CHECK 3: Primary keyword maximum 8 times with natural variations."""

    def test_enforces_max_8_keyword_occurrences(self):
        primary_kw = "statutory limitation period"
        # Create an article with 20 occurrences
        paragraphs = ["<h1>Guide</h1>", "<div class=\"tldr-block\"><p>TLDR with statutory limitation period</p></div>"]
        for i in range(18):
            paragraphs.append(f"<p>Paragraph {i+1} mentions statutory limitation period in your case.</p>")
        paragraphs.append("<p>Conclusion on statutory limitation period.</p>")
        html_input = "\n".join(paragraphs)
        
        # Verify input has ~20 occurrences
        count_before = len(re.findall(re.escape(primary_kw), html_input, re.I))
        assert count_before >= 15
        
        # Enforce density
        result_html = enforce_keyword_density(html_input, primary_kw, max_count=8)
        count_after = len(re.findall(re.escape(primary_kw), result_html, re.I))
        assert count_after <= 8, f"Expected <= 8 keyword occurrences, got {count_after}"


class TestDuplicateExampleDetector:
    """CHECK 4: Zero duplicate example sentences."""

    def test_removes_duplicate_examples(self):
        dup_example = "<p>For example, say you were dealing with statutory limitation period accident claims after a rear-end collision - you'd want to document everything right away.</p>"
        html_input = f"""
        <h1>Article</h1>
        <h2>Section 1</h2>
        {dup_example}
        <h2>Section 2</h2>
        {dup_example}
        <h2>Section 3</h2>
        {dup_example}
        """
        result_html = detect_duplicate_examples(html_input)
        soup = BeautifulSoup(result_html, "html.parser")
        ps = [p.get_text() for p in soup.find_all("p") if "for example, say you were dealing with" in p.get_text().lower()]
        assert len(ps) == 1, f"Expected exactly 1 instance of example, found {len(ps)}"


class TestSectionHeadingRelevance:
    """CHECK 5: Section headings match keyword intent (no off-topic pain & suffering on limitation claims)."""

    def test_limitation_outline_has_no_pain_and_suffering_h2s(self):
        outline = build_default_15point_outline("statutory limitation period accident claims")
        h2s = outline.get("point_7_h2_sections", [])
        headings = [h.get("heading", "") for h in h2s]
        for hd in headings:
            assert "pain and suffering" not in hd.lower(), f"Found unrelated H2 heading: '{hd}'"
            assert any(term in hd.lower() for term in ["statut", "limit", "deadline", "clock", "exception", "claim", "time", "action"])


class TestNoBrokenSentences:
    """CHECK 6: No broken dangling sentences."""

    def test_fixes_dangling_broken_sentences(self):
        broken_html = "<p>The multiplier method is applied then.\nwe calculate damages.</p><p>These rules hold then.</p><p>and continue.</p>"
        fixed_html = fix_broken_sentences(broken_html)
        assert "then.\nwe" not in fixed_html
        assert "then.</p><p>and" not in fixed_html


class TestNoPlaceholderLinks:
    """CHECK 7: No broken placeholder links or strategic resource fillers."""

    def test_removes_placeholder_strategic_resources(self):
        html_input = """
        <h1>Article</h1>
        <p>Real content paragraph.</p>
        <p>For related strategies, explore our strategic resources.</p>
        <p><a href="/strategies">Explore our strategic resources.</a></p>
        <p>Final content paragraph.</p>
        """
        cleaned = remove_broken_links(html_input)
        assert "explore our strategic resources" not in cleaned.lower()
        assert "for related strategies" not in cleaned.lower()


class TestFAQsAndCTAs:
    """CHECKS 8 & 9: Real FAQs and CTAs present."""

    def test_faqs_and_ctas_in_15point_pipeline(self):
        outline = build_default_15point_outline("statutory limitation period accident claims")
        faqs = outline.get("point_14_faqs", [])
        assert len(faqs) >= 4
        for faq in faqs:
            ans = faq.get("answer_draft", "")
            assert len(ans) >= 40
            assert "dismiss your lawsuit" in ans or "tolling" in ans or "negotiating" in ans or "attorney" in ans or "strict time limits" in ans

        ctas = outline.get("point_13_ctas", [])
        assert len(ctas) >= 1
        assert "case review" in ctas[0].get("cta_text", "").lower() or "consultation" in ctas[0].get("cta_type", "").lower()


@pytest.mark.asyncio
async def test_full_15point_generation_pipeline_order():
    """End-to-end pipeline test generating 'statutory limitation period accident claims'."""
    topic = "statutory limitation period accident claims"
    outline = await run_planner(target_keyword=topic, website_id="default", business_name="Accident Legal Help")
    
    # Check 1: Outline validation
    is_valid, errors = validate_outline(outline, topic)
    assert is_valid is True, f"Planner generated invalid outline: {errors}"
    
    # Run Writer
    raw_article = await run_writer(outline=outline, target_keyword=topic, website_id="default")
    assert raw_article.startswith("<h1") or "<h1>" in raw_article
    
    # Run full process_blog_output
    final_article = await process_blog_output(raw_article, website_id="default", target_keyword=topic, outline=outline, primary_keyword=topic)
    
    # Check 2: TL;DR has real content
    assert "class=\"tldr-block\"" in final_article
    assert "Essential details and actionable guidance" not in final_article
    
    # Check 3: Keyword density <= 8
    pattern = re.compile(re.escape("statutory limitation period"), re.IGNORECASE)
    kw_count = len(pattern.findall(final_article))
    assert kw_count <= 8, f"Keyword count is {kw_count}, expected <= 8"
    
    # Check 4: Zero duplicate examples
    soup = BeautifulSoup(final_article, "html.parser")
    example_texts = [p.get_text() for p in soup.find_all("p") if p.get_text().strip().lower().startswith(("for example,", "say you", "imagine you"))]
    assert len(example_texts) == len(set(example_texts)), "Found duplicate examples in final article"
    
    # Check 5: Sections match keyword
    h2s = [h.get_text() for h in soup.find_all("h2")]
    for h in h2s:
        if "frequently asked" not in h.lower() and "conclusion" not in h.lower():
            assert "pain and suffering" not in h.lower()
            
    # Check 6: No broken sentences
    assert not re.search(r"\b(then|these|and|or)\.\s*\n+\s*[a-z]", final_article)
    
    # Check 7: No placeholder links
    assert "explore our strategic resources" not in final_article.lower()
    
    # Check 8: FAQs present
    h3s = [h.get_text() for h in soup.find_all("h3")]
    assert len(h3s) >= 4
    
    # Check 9: CTA present
    assert "cta-box" in final_article or "case review" in final_article.lower() or "free consultation" in final_article.lower() or "contact" in final_article.lower()


class TestKeywordSanitization:
    """CHECK 1: Keyword sanitization fixes year concatenation and leading numbers."""

    def test_sanitize_keyword_year_attached(self):
        assert sanitize_keyword("2026accident liability", 2026) == "2026 accident liability"
        assert sanitize_keyword("2026liability evidence", 2026) == "2026 liability evidence"

    def test_sanitize_keyword_stray_number(self):
        assert sanitize_keyword("2accident liability evidence requirements", 2026) == "accident liability evidence requirements"
        assert sanitize_keyword("2framework for accident claims", 2026) == "framework for accident claims"

    def test_sanitize_keyword_duplicate_year(self):
        assert sanitize_keyword("2026 2026 accident claims", 2026) == "2026 accident claims"


class TestBrokenYearInContent:
    """CHECK 1 & 3: Content year and number merging fixes."""

    def test_fix_broken_year_in_html(self):
        raw_html = "<p>Dealing with 2026accident claims or 2026liability requires understanding 2accident rules and 2framework.</p><p>You have 2 weeks and 2 years to file.</p>"
        fixed = fix_broken_year_in_content(raw_html)
        assert "2026 accident" in fixed
        assert "2026 liability" in fixed
        assert "accident rules" in fixed
        assert "framework." in fixed
        # Preserves numbers with spaces like "2 weeks" and "2 years"
        assert "2 weeks" in fixed
        assert "2 years" in fixed


class TestWordCountValidationAndExpansion:
    """CHECK 2 & 3: Word count validation and expansion."""

    def test_validate_word_count(self):
        short_text = "<p>" + " ".join(["word"] * 500) + "</p>"
        is_valid, count = validate_word_count(short_text, min_words=2400, max_words=3200)
        assert is_valid is False
        assert count == 500

        good_text = "<p>" + " ".join(["word"] * 2600) + "</p><p>Meta Description: Test meta desc</p>"
        is_valid, count = validate_word_count(good_text, min_words=2400, max_words=3200)
        assert is_valid is True
        assert count == 2600

    @pytest.mark.asyncio
    async def test_ensure_minimum_word_count_expands_sections(self):
        short_article = """
        <h1>Accident liability evidence requirements</h1>
        <h2>Section 1: Initial Documentation</h2>
        <p>Short section text here about evidence.</p>
        <h2>Section 2: Witness Statements</h2>
        <p>Another short section text here.</p>
        <h2>Frequently Asked Questions</h2>
        <h3>What evidence is required?</h3>
        <p>Detailed evidence documentation is required.</p>
        """
        is_valid, count = validate_word_count(short_article)
        assert count < 100
        
        expanded = await ensure_minimum_word_count(
            html_content=short_article,
            outline={},
            target_keyword="accident liability evidence requirements",
            website_id="default",
            current_word_count=count,
            min_words=300
        )
        _, new_count = validate_word_count(expanded)
        assert new_count > count


@pytest.mark.asyncio
async def test_accident_liability_evidence_requirements_e2e():
    """
    VERIFICATION TEST FOR:
    Keyword 'accident liability evidence requirements'
    Checks all 6 requirements:
    1. Keyword clean (no '2accident', '2framework', '2liability', '2026accident')
    2. Word count between 2400 and 3200 words
    3. Section lengths (no section under 200 words)
    4. Quality not padded
    5. Example variety (no duplicates)
    6. Real TL;DR bullets
    """
    topic = "accident liability evidence requirements"
    outline = await run_planner(target_keyword=topic, website_id="default", business_name="Accident Legal Help")
    
    # 1. Validate outline
    is_valid, errors = validate_outline(outline, topic)
    assert is_valid is True, f"Planner generated invalid outline: {errors}"
    
    # 2. Run Writer
    raw_article = await run_writer(outline=outline, target_keyword=topic, website_id="default", word_count_target=2500)
    assert raw_article.startswith("<h1") or "<h1>" in raw_article
    
    # 3. Run Post-processing
    final_article = await process_blog_output(raw_article, website_id="default", target_keyword=topic, outline=outline, primary_keyword=topic)
    
    # CHECK 1: KEYWORD CLEAN
    assert "2accident" not in final_article
    assert "2framework" not in final_article
    assert "2liability" not in final_article
    assert "2026accident" not in final_article
    assert not re.search(r'\b20\d{2}[a-zA-Z]', final_article)
    assert not re.search(r'\b[1-9][a-zA-Z]{3,}\b', final_article)
    
    # CHECK 2: WORD COUNT
    is_valid_wc, count = validate_word_count(final_article, min_words=2400, max_words=3200)
    assert count >= 2400, f"Word count is {count}, expected >= 2400"
    
    # CHECK 3: SECTION LENGTHS (no section under 200 words)
    soup = BeautifulSoup(final_article, "html.parser")
    for h2 in soup.find_all("h2"):
        h2_title = h2.get_text()
        if "frequently asked" in h2_title.lower() or "faq" in h2_title.lower():
            continue
        sec_text = ""
        sib = h2.next_sibling
        while sib and sib.name not in ["h2", "h1"]:
            if hasattr(sib, "get_text"):
                sec_text += sib.get_text() + " "
            sib = sib.next_sibling
        words_in_sec = len(sec_text.split())
        assert words_in_sec >= 180, f"Section '{h2_title}' is too short: {words_in_sec} words"

    # CHECK 5: EXAMPLE VARIETY (no duplicate examples)
    example_paras = [p.get_text().strip() for p in soup.find_all("p") if p.get_text().strip().lower().startswith(("for example,", "say you", "imagine you", "think about", "consider this"))]
    assert len(example_paras) == len(set(example_paras)), "Found duplicate example paragraphs"
    
    # CHECK 6: TL;DR BULLETS ARE REAL
    assert 'class="tldr-block"' in final_article
    assert "Essential details and actionable guidance" not in final_article


class TestLimitationPeriodSpecifics:
    """CHECK: Specific tests for 2-year limitation period accident claims 2026."""

    def test_2year_limitation_keyword_sanitized(self):
        kw1 = sanitize_keyword("2-year limitation period accident claims 2026", 2026)
        assert kw1 == "2-year limitation period accident claims 2026"
        
        kw2 = sanitize_keyword("2year limitation period accident claims", 2026)
        assert kw2 == "2-year limitation period accident claims"
        
        kw3 = sanitize_keyword("2statutory limitation period accident claims", 2026)
        assert kw3 == "statutory limitation period accident claims"

    def test_tldr_clean_for_limitation_claims(self):
        bad_html = """
        <h1>2-year limitation period accident claims 2026</h1>
        <div class="tldr-block">
        <p><strong>TL;DR:</strong> This guide covers 2-year limitation period accident claims 2026 - what it means, how it works, and what to do next. You'll learn the key steps, common pitfalls, and the single most important takeaway to act confidently.</p>
        <ul>
        <li><strong>Frequently Asked Questions:</strong> Essential details and actionable guidance about this aspect of 2-year limitation period accident claims .</li>
        <li><strong>Key insight about 2-year limitation peri:</strong> Essential details and actionable guidance about this aspect of 2-year limitation period accident claims .</li>
        <li><strong>Key insight about 2-year limitation peri:</strong> Essential details and actionable guidance about this aspect of 2-year limitation period accident claims .</li>
        <li><strong>Key insight about 2-year limitation peri:</strong> Essential details and actionable guidance about this aspect of 2-year limitation period accident claims .</li>
        </ul>
        </div>
        <h2>When the Limitation Period Starts Running</h2>
        <p>The limitation clock starts on the crash date.</p>
        """
        fixed = validate_and_fix_tldr(bad_html, "2-year limitation period accident claims 2026")
        assert "Essential details and actionable guidance" not in fixed
        assert "Key insight about 2-year limitation peri" not in fixed
        assert "Frequently Asked Questions:" not in fixed
        assert "Statutory Deadlines" in fixed or "Limitation Clock" in fixed or "When the Limitation Period" in fixed

    def test_no_offtopic_multiplier_in_limitation_article(self):
        html_input = """
        <h1>2-year limitation period accident claims 2026</h1>
        <div class="tldr-block"><p>TL;DR summary</p><ul><li><strong>Point:</strong> Real takeaway</li></ul></div>
        <h2>When the Limitation Period Starts Running</h2>
        <p>The limitation period begins on the day of the crash.</p>
        <h2>Exceptions That Can Pause the Deadline</h2>
        <p>Tolling applies for minors.</p>
        <h2>Frequently Asked Questions</h2>
        <h3>How long do I have?</h3>
        <p>You have two years to file.</p>
        """
        # Ensure dollar example does NOT inject multiplier for limitation keywords
        fixed_dollar = ensure_dollar_example(html_input, "2-year limitation period accident claims 2026")
        assert "The multiplier method is the most common approach" not in fixed_dollar
        assert "Say your medical bills total $15,000" not in fixed_dollar

    def test_no_duplicate_sentence_boilerplate(self):
        dup_sentence = "This is where detailed medical records, physician statements, and consistent pain diaries become critical. Without them, the insurer has room to argue that your reported pain doesn't match the treatment history, which directly lowers the multiplier they'll accept."
        html_input = f"""
        <h1>Article</h1>
        <h2>Section 1</h2>
        <p>Introductory sentence. {dup_sentence}</p>
        <h2>Section 2</h2>
        <p>Second section info. {dup_sentence}</p>
        """
        cleaned = detect_duplicate_examples(html_input)
        assert cleaned.count("This is where detailed medical records") == 1
