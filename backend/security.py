"""Central credential security helpers.

Rules enforced across RankForge:
1. Credentials are encrypted with Fernet before touching Supabase.
2. Decrypted values NEVER leave the backend except inside an outbound API call.
3. Every API response passes website rows through `sanitize_website_row` /
   `sanitize_dict` so raw secrets can never leak to the frontend.
4. Status endpoints only ever return booleans (`is_configured`), never values.
"""

import base64
import hashlib
import logging
import os
import re
from typing import Any, Dict, Optional

import bleach
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("backend.security")

# ---------------------------------------------------------------------------
# Fernet key derivation (mirrors config.py so both stay in sync)
# ---------------------------------------------------------------------------

_raw_secret = (
    os.getenv("TOKEN_ENCRYPTION_KEY")
    or os.getenv("ENCRYPTION_SECRET")
    or ""
)
if not _raw_secret:
    if os.getenv("TESTING") or os.getenv("ENVIRONMENT") != "production":
        _raw_secret = "rankforge-local-dev-secret-key-32bytes-secure"
    else:
        logger.warning(
            "[Security] TOKEN_ENCRYPTION_KEY not set in production. "
            "Generating ephemeral 256-bit key."
        )
        _raw_secret = base64.urlsafe_b64encode(os.urandom(32)).decode()

_FERNET_KEY = base64.urlsafe_b64encode(hashlib.sha256(_raw_secret.encode()).digest()).decode()
_fernet: Optional[Fernet] = None

CREDENTIAL_FIELD_NAMES = {
    "app_password",
    "wordpress_password",
    "wordpress_password_encrypted",
    "wp_app_password",
    "serper_api_key",
    "serper_api_key_encrypted",
    "nvidia_api_key",
    "slack_bot_token",
    "slack_token_encrypted",
    "ahrefs_api_key",
    "resend_api_key",
    "openai_api_key",
    "gsc_service_account_json",
    "ga4_credentials_json",
    "client_secret",
    "api_key",
    "token_encrypted",
    "webhook_url",
}

# Fields that are safe to expose even though they live on the websites row.
SAFE_WEBSITE_FIELDS = {
    "id",
    "domain",
    "url",
    "cms_url",
    "cms_user",
    "wordpress_url",
    "wordpress_user",
    "gsc_property",
    "ga4_property_id",
    "niche",
    "name",
    "status",
    "created_at",
    "updated_at",
    "last_audit_score",
    "last_audit_date",
    "tone_profile_id",
}


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_FERNET_KEY.encode())
    return _fernet


def encrypt_secret(value: str) -> str:
    """Encrypt a secret for storage in Supabase. Returns Fernet token string."""
    if not value:
        return ""
    try:
        return _get_fernet().encrypt(value.encode()).decode()
    except Exception as e:
        logger.error(f"[Security] encrypt_secret failed: {e}")
        raise


def decrypt_secret(value: str) -> str:
    """Decrypt a stored Fernet token. Returns '' when missing/undecryptable."""
    if not value:
        return ""
    try:
        return _get_fernet().decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
        # Value may be legacy plaintext; never log the value itself.
        return value if isinstance(value, str) else ""


def looks_encrypted(value: str) -> bool:
    if not value:
        return False
    try:
        decoded = base64.urlsafe_b64decode(value.encode())
        # Fernet tokens start with version byte 0x80
        return len(decoded) > 30 and decoded[0] == 0x80
    except Exception:
        return False


def is_credential_field(key: str) -> bool:
    k = (key or "").lower()
    if k in CREDENTIAL_FIELD_NAMES:
        return True
    return bool(re.search(r"(password|secret|token|api_key|apikey|credential)", k))


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively remove any field that carries a raw credential value.

    Nested dicts named like credentials (e.g. slack_credentials) keep their
    non-secret metadata but lose any *token/password/key/webhook* entries,
    which are replaced by an `is_configured` boolean.
    """
    if not isinstance(data, dict):
        return data
    clean: Dict[str, Any] = {}
    for key, value in data.items():
        kl = (key or "").lower()
        if isinstance(value, dict):
            clean[key] = sanitize_dict(value)
            continue
        if is_credential_field(kl):
            clean[key] = None
            clean[f"{key}_is_configured"] = bool(value)
            continue
        if isinstance(value, list):
            clean[key] = [sanitize_dict(v) if isinstance(v, dict) else v for v in value]
            continue
        clean[key] = value
    return clean


def sanitize_website_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Return a websites-table row safe for API responses.

    Keeps only whitelisted fields and adds `is_configured` booleans so the UI
    can show a 'Saved' badge without ever seeing the real secret.
    """
    if not isinstance(row, dict):
        return row

    safe: Dict[str, Any] = {k: row.get(k) for k in SAFE_WEBSITE_FIELDS if k in row}
    safe["wordpress_configured"] = bool(
        (row.get("app_password") or row.get("wordpress_password") or row.get("wordpress_password_encrypted"))
        and (row.get("cms_user") or row.get("wordpress_user"))
    )
    safe["serper_configured"] = bool(row.get("serper_api_key") or row.get("serper_api_key_encrypted"))
    slack_creds = row.get("slack_credentials") or {}
    if isinstance(slack_creds, dict):
        safe["slack_workspace_name"] = slack_creds.get("workspace_name")
        safe["slack_connected"] = bool(slack_creds.get("token_encrypted"))
    else:
        safe["slack_connected"] = False
        safe["slack_workspace_name"] = None
    return safe


ALLOWED_HTML_TAGS = [
    "p", "br", "hr", "pre", "blockquote",
    "ul", "ol", "li",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "thead", "tbody", "tr", "td", "th",
    "strong", "b", "em", "i", "u", "s", "del", "ins",
    "a", "span", "div",
    "img",
    "code", "pre",
    "details", "summary",
    "figure", "figcaption",
    "dl", "dt", "dd",
    "sup", "sub",
]

ALLOWED_HTML_ATTRIBUTES = {
    "*": ["class", "id", "style", "aria-label", "role"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "loading", "width", "height"],
    "td": ["colspan", "rowspan", "align", "valign"],
    "th": ["colspan", "rowspan", "align", "valign"],
    "tr": ["align", "valign"],
    "table": ["border", "cellpadding", "cellspacing", "align", "valign", "width"],
}

ALLOWED_HTML_STYLES = [
    "color", "background-color", "font-size", "font-weight", "font-style",
    "text-align", "text-decoration", "margin", "margin-left", "margin-right",
    "margin-top", "margin-bottom", "padding", "padding-left", "padding-right",
    "padding-top", "padding-bottom", "border", "border-radius", "width", "height",
    "display", "flex", "grid", "gap", "line-height", "letter-spacing",
]


def sanitize_html(html_content: str) -> str:
    """Sanitize HTML content to prevent XSS attacks.

    Uses bleach to strip dangerous tags/attributes while preserving safe formatting.
    """
    if not html_content or not isinstance(html_content, str):
        return ""
    try:
        cleaned = bleach.clean(
            html_content,
            tags=ALLOWED_HTML_TAGS,
            attributes=ALLOWED_HTML_ATTRIBUTES,
            styles=ALLOWED_HTML_STYLES,
            strip=True,
            strip_comments=True,
        )
        return cleaned
    except Exception as e:
        logger.warning(f"[Security] HTML sanitization failed: {e}")
        return ""
