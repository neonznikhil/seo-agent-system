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

try:
    import bleach
except ImportError:
    bleach = None
from cryptography.fernet import Fernet, MultiFernet, InvalidToken

logger = logging.getLogger("backend.security")

# ---------------------------------------------------------------------------
# Fernet key derivation with MultiFernet fallback support
# ---------------------------------------------------------------------------

_multi_fernet: Optional[MultiFernet] = None


def _init_multi_fernet() -> MultiFernet:
    global _multi_fernet
    raw_keys = [
        os.getenv("TOKEN_ENCRYPTION_KEY"),
        os.getenv("ENCRYPTION_KEY"),
        os.getenv("ENCRYPTION_SECRET"),
        "rankforge-local-dev-secret-key-32bytes-secure",
        "rankforge-production-fallback-key-32bytes",
    ]
    extra = os.getenv("FALLBACK_ENCRYPTION_KEYS", "") or os.getenv("TOKEN_ENCRYPTION_KEY_FALLBACKS", "")
    if extra:
        raw_keys.extend(k.strip() for k in extra.split(",") if k.strip())

    seen_b64 = set()
    fernets = []
    for rk in raw_keys:
        if not rk:
            continue
        # 1. SHA256-derived 32-byte urlsafe base64 key
        try:
            derived = base64.urlsafe_b64encode(hashlib.sha256(rk.encode()).digest()).decode()
            if derived not in seen_b64:
                seen_b64.add(derived)
                fernets.append(Fernet(derived.encode()))
        except Exception:
            pass
        # 2. Direct key if already a valid 44-char base64 Fernet key
        try:
            rk_clean = rk.strip()
            if len(rk_clean) == 44:
                Fernet(rk_clean.encode())
                if rk_clean not in seen_b64:
                    seen_b64.add(rk_clean)
                    fernets.append(Fernet(rk_clean.encode()))
        except Exception:
            pass

    if not fernets:
        fernets.append(Fernet(Fernet.generate_key()))

    _multi_fernet = MultiFernet(fernets)
    return _multi_fernet


def _get_fernet():
    global _multi_fernet
    if _multi_fernet is None:
        _multi_fernet = _init_multi_fernet()
    return _multi_fernet


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
    """Decrypt a stored Fernet token. Returns '' when missing or undecryptable."""
    if not value:
        return ""
    try:
        decrypted = _get_fernet().decrypt(value.encode()).decode()
        return decrypted
    except Exception:
        # If it looks like a Fernet token (starts with gAAAA), NEVER return the raw ciphertext!
        if isinstance(value, str) and (value.startswith("gAAAA") or looks_encrypted(value)):
            return ""
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
        if bleach:
            cleaned = bleach.clean(
                html_content,
                tags=ALLOWED_HTML_TAGS,
                attributes=ALLOWED_HTML_ATTRIBUTES,
                styles=ALLOWED_HTML_STYLES,
                strip=True,
                strip_comments=True,
            )
            return cleaned
        else:
            # High-security regex fallback stripping script, iframe, object, event handlers, and javascript: URIs
            cleaned = re.sub(r"<(script|iframe|object|embed|applet)[\s\S]*?/\1>", "", html_content, flags=re.I)
            cleaned = re.sub(r"<(script|iframe|object|embed|applet)[^>]*>", "", cleaned, flags=re.I)
            cleaned = re.sub(r"\son\w+\s*=\s*(?:'[^']*'|\"[^\"]*\"|[^\s>]+)", "", cleaned, flags=re.I)
            cleaned = re.sub(r"javascript\s*:", "", cleaned, flags=re.I)
            return cleaned
    except Exception as e:
        logger.warning(f"[Security] HTML sanitization failed: {e}")
        return ""
