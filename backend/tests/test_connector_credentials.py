"""Tests for connector username/placeholder resolution."""

from services.connector_credentials import (
    is_placeholder_wp_username,
    resolve_wp_username,
)


def test_blank_and_known_placeholders_are_rejected():
    for value in ["", "   ", None, "admin", "your-username", "test"]:
        assert is_placeholder_wp_username(value) is True


def test_a_real_person_username_is_not_blocked():
    # Regression: the repo once listed its author's own username as a
    # placeholder sentinel, which rejected that owner's genuine credentials.
    assert is_placeholder_wp_username("nikhil_d") is False
    assert is_placeholder_wp_username("Nikhil_D") is False


def test_spelling_variants_of_placeholder_are_rejected():
    # Separator/case variants must not slip past the sentinel check.
    for value in [
        "your_username",
        "yourusername",
        "YourUsername",
        "your-name",
        "Your Name",
        "yourname",
        "your_user",
        "YourUser",
        "wp_username",
        "wp-user",
        "testuser",
        "exampleuser",
    ]:
        assert is_placeholder_wp_username(value) is True, value


def test_real_username_is_accepted():
    assert is_placeholder_wp_username("editor_jane") is False
    assert is_placeholder_wp_username("Nikhil") is False  # not the sentinel
    # A genuine name that merely contains a placeholder substring is allowed.
    assert is_placeholder_wp_username("administrator_jane") is False
    assert is_placeholder_wp_username("mytest") is False


def test_resolve_prefers_first_real_candidate():
    assert resolve_wp_username("admin", "real_user") == "real_user"
    assert resolve_wp_username("", "second_real") == "second_real"
    assert resolve_wp_username(None, None) == ""


def test_resolve_never_invents_a_fallback():
    # No candidates -> empty string, NOT a hardcoded developer account.
    assert resolve_wp_username() == ""
    assert resolve_wp_username("admin") == ""
