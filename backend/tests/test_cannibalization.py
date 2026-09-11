"""Cannibalization detector: grouping, recommendations, honesty edges."""
import pytest

from backend.services.cannibalization_service import (
    detect_cannibalization,
    normalize_keyword,
)


def test_normalize_groups_variants():
    assert normalize_keyword("Houston Car-Accident Lawyer!") == normalize_keyword("houston car accident lawyer")


def test_no_issue_for_single_page_keyword():
    rows = [{"keyword": "solo topic", "url": "https://x/a", "title": "A", "position": 5}]
    assert detect_cannibalization(rows) == []


def test_consolidate_when_gap_is_large():
    rows = [
        {"keyword": "injury claims", "url": "https://x/strong", "title": "Strong", "position": 4},
        {"keyword": "injury claims", "url": "https://x/weak", "title": "Weak", "position": 18},
    ]
    issues = detect_cannibalization(rows)
    assert len(issues) == 1
    assert issues[0]["action"] == "consolidate"
    assert issues[0]["severity"] == "high"
    assert "301-redirect" in issues[0]["recommendation"]


def test_differentiate_when_positions_close():
    rows = [
        {"keyword": "injury claims", "url": "https://x/a", "title": "A", "position": 8},
        {"keyword": "injury claims", "url": "https://x/b", "title": "B", "position": 11},
    ]
    issues = detect_cannibalization(rows)
    assert len(issues) == 1
    assert issues[0]["action"] == "differentiate"
    assert issues[0]["best_position"] == 8
    assert issues[0]["worst_position"] == 11


def test_unmeasured_content_rows_flagged_medium_with_warning():
    # Distinct untracked drafts are distinct pages -> flagged, unmeasured.
    rows = [
        {"keyword": "same topic", "url": "", "title": "Draft A", "position": None},
        {"keyword": "same topic", "url": "", "title": "Draft B", "position": None},
    ]
    issues = detect_cannibalization(rows)
    assert len(issues) == 1
    assert issues[0]["severity"] == "medium"
    assert issues[0]["unmeasured_count"] == 2
    assert "unmeasured" in issues[0]["recommendation"]


def test_empty_and_keywordless_rows_never_issue():
    assert detect_cannibalization([]) == []
    assert detect_cannibalization([{"keyword": "", "url": "https://x/a"}]) == []
