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
    "your-username",
    "yourusername",
    "your_username",
    "your name",
    "yourname",
    "your_user",
    "youruser",
    "username",
    "wp-username",
    "wp_username",
    "wpuser",
    "test",
    "testuser",
    "demo",
    "example",
    "exampleuser",
    "user@example.com",
    "you@example.com",
}

# NOTE: do not add a *real* account name here. This set exists to catch the
# generic sentinels an app invents as a default; blocklisting one specific
# person's username (the repo once listed its author's) rejects that owner's
# genuine credentials. The hardcoded default itself was removed from the
# WordPress service, which is the actual fix — see test_wordpress_drafting.py.

# Normalising away separators catches "Your_Name", "your-name" and "YourName"
# from a single entry so new spelling variants of the same sentinel stay caught.
_SEPARATORS = str.maketrans("", "", "_- .")


def _normalize(username: str) -> str:
    return username.strip().lower().translate(_SEPARATORS)


_NORMALIZED_PLACEHOLDERS = {_normalize(name) for name in PLACEHOLDER_WP_USERNAMES}


def is_placeholder_wp_username(username: Optional[str]) -> bool:
    """True when the value is empty or a known placeholder sentinel."""
    if username is None:
        return True
    return _normalize(username) in _NORMALIZED_PLACEHOLDERS


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
