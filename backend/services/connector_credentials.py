"""Shared credential-identity helpers for connector endpoints.

WordPress application passwords are scoped to a specific username. Plugin code
often defaults a missing username to a literal developer value, which then
silently attempts authentication as the wrong account and reports a bogus
"connected" result. These helpers make the placeholder explicit so callers can
refuse to persist a fake identity instead.
"""

from typing import List, Optional

PLACEHOLDER_WP_USERNAMES = {
    "",
    "admin",
    "administrator",
    "root",
    "nikhil_d",
    "your-username",
    "yourusername",
    "your_user",
    "username",
    "wp-username",
    "wpuser",
    "test",
    "demo",
    "example",
    "user@example.com",
    "you@example.com",
}


def is_placeholder_wp_username(username: Optional[str]) -> bool:
    """True when the value is empty or a known placeholder sentinel."""
    if username is None:
        return True
    return username.strip().lower() in PLACEHOLDER_WP_USERNAMES


def resolve_wp_username(*candidates: Optional[str]) -> str:
    """Return the first candidate that is a real username, else an empty string.

    Never invents a fallback identity: an empty result means the caller must ask
    the user for their actual WordPress username.
    """
    for candidate in candidates:
        if candidate and not is_placeholder_wp_username(candidate):
            return candidate.strip()
    return ""


def candidates_from(*values: Optional[str]) -> List[str]:
    """Utility used by tests/diagnostics to inspect candidate ordering."""
    return [v.strip() for v in values if v]
