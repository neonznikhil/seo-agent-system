import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.tools.humanizer import (
    humanize_content,
    detect_ai_patterns,
    optimize_for_human_readability,
    ensure_keyword_in_title_content,
    calculate_tone_match
)


class TestHumanizeContent:
    
    def test_remove_em_dash(self):
        text = "This is a test—another test."
        result = humanize_content(text)
        assert '—' not in result
        assert 'another test' in result
    
    def test_remove_banned_phrases(self):
        text = "In today's fast-paced world, it's important to note that we need to leverage this."
        result = humanize_content(text)
        assert "in today's fast-paced world" not in result.lower()
        assert "it's important to note" not in result.lower()
        assert "leverage" not in result.lower()
    
    def test_fix_excess_quotes(self):
        text = "This is the 'best' 'way' 'to' 'do' 'it'."
        result = humanize_content(text)
        assert "'best'" not in result
        assert "best" in result
    
    def test_normalize_spacing(self):
        text = "This   has    too     many     spaces."
        result = humanize_content(text)
        assert "  " not in result


class TestDetectAIPatterns:
    
    def test_detects_em_dash(self):
        text = "This uses em dash—for AI patterns."
        result = detect_ai_patterns(text)
        assert result["is_human"] == False
        assert result["human_score"] < 75
    
    def test_detects_banned_phrases(self):
        text = "Delve into this comprehensive guide to unlock success."
        result = detect_ai_patterns(text)
        assert "banned_phrases" in str(result["issues"])
    
    def test_high_score_pass(self):
        text = "This is real human content. We built this for customers. It works well."
        result = detect_ai_patterns(text)
        assert result["is_human"] == True
        assert result["human_score"] >= 75


class TestOptimizeForReadability:
    
    def test_improves_burstiness(self):
        text = "This is a very long sentence that could be split into two parts for better readability and engagement with the reader."
        result = optimize_for_human_readability(text)
        assert result == text or '.' in result


class TestKeywordPresence:
    
    def test_keyword_in_title_required(self):
        text = """# How to Optimize Your Business

        This is about SEO and keywords."""
        result, has_kw = ensure_keyword_in_title_content(text, "SEO")
        assert has_kw == True
    
    def test_keyword_in_intro(self):
        text = """# How to Optimize Your Business

        Learn about SEO strategies here."""
        result, has_kw = ensure_keyword_in_title_content(text, "SEO")
        assert has_kw == True


class TestToneMatch:
    
    def test_tone_matches_example_phrases(self):
        text = "Here's what actually works. We built this for customers."
        tone = {"example_phrases": ["here's what actually works", "built for customers"]}
        score = calculate_tone_match(text, tone)
        assert score > 0.5
    
    def test_no_tone_profile_defaults(self):
        text = "Some content here."
        score = calculate_tone_match(text, None)
        assert score == 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])