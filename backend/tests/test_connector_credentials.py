"""Tests for connector username/placeholder resolution."""

from services.connector_credentials import (
    is_placeholder_wp_username,
    resolve_wp_username,
)


def test_blank_and_known_placeholders_are_rejected():
    for value in ["", "   ", None, "nikhil_d", "your-username", "test"]:
        assert is_placeholder_wp_username(value) is True


def test_real_username_is_accepted():
    assert is_placeholder_wp_username("editor_jane") is False
    assert is_placeholder_wp_username("Nikhil") is False  # not the sentinel


def test_resolve_prefers_first_real_candidate():
    assert resolve_wp_username("nikhil_d", "real_user") == "real_user"
    assert resolve_wp_username("", "second_real") == "second_real"
    assert resolve_wp_username(None, None) == ""


def test_resolve_never_invents_a_fallback():
    # No candidates -> empty string, NOT a hardcoded developer account.
    assert resolve_wp_username() == ""
    assert resolve_wp_username("nikhil_d") == ""
