import os
import sys
import logging
import warnings
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("backend.config")

# Core Service Keys & URLs
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Integration API Keys
SERPER_API_KEY: str = os.getenv("SERPER_API_KEY", "")
SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "")
PAGESPEED_API_KEY: str = os.getenv("PAGESPEED_API_KEY", "")
AHREFS_API_KEY: str = os.getenv("AHREFS_API_KEY", "")
RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")

# Slack Credentials
SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN: str = os.getenv("SLACK_APP_TOKEN", "")
SLACK_SIGNING_SECRET: str = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_CLIENT_ID: str = os.getenv("SLACK_CLIENT_ID", "")
SLACK_CLIENT_SECRET: str = os.getenv("SLACK_CLIENT_SECRET", "")
SLACK_OWNER_USER_ID: str = os.getenv("SLACK_OWNER_USER_ID", "U_OWNER_RANKFORGE")

# Google OAuth (GSC & GA4)
GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
GSC_CREDENTIALS_PATH: str = os.getenv("GSC_CREDENTIALS_PATH", "")
GA4_CREDENTIALS_PATH: str = os.getenv("GA4_CREDENTIALS_PATH", "")

# WordPress Credentials
WP_SITE_URL: str = os.getenv("WP_SITE_URL", "")
WORDPRESS_URL: str = os.getenv("WORDPRESS_URL", "")
WP_OAUTH_CLIENT_ID: str = os.getenv("WP_OAUTH_CLIENT_ID", "")
WP_OAUTH_CLIENT_SECRET: str = os.getenv("WP_OAUTH_CLIENT_SECRET", "")
WP_OAUTH_AUTHORIZE_URL: str = os.getenv("WP_OAUTH_AUTHORIZE_URL", "https://public-api.wordpress.com/oauth2/authorize")
WP_OAUTH_TOKEN_URL: str = os.getenv("WP_OAUTH_TOKEN_URL", "https://public-api.wordpress.com/oauth2/token")

# Token Encryption
import base64
import hashlib

_raw_secret = os.getenv("TOKEN_ENCRYPTION_KEY") or os.getenv("ENCRYPTION_SECRET") or "rankforge-production-master-secret-key-32bytes"
# Always ensure exactly 32 url-safe base64-encoded bytes for Fernet
TOKEN_ENCRYPTION_KEY: str = base64.urlsafe_b64encode(hashlib.sha256(_raw_secret.encode()).digest()).decode()
ENCRYPTION_SECRET: str = TOKEN_ENCRYPTION_KEY


# Thresholds & URLs
DUPLICATE_THRESHOLD: float = float(os.getenv("DUPLICATE_THRESHOLD", "0.85"))
FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
REDIRECT_URI: str = os.getenv("REDIRECT_URI", f"{BACKEND_URL}/api/wordpress/oauth/callback")
ALLOWED_CORS_ORIGINS: list = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,https://*.cloudworkstations.dev,https://*.app.github.dev,*",
    ).split(",")
    if origin.strip()
]


def _mask(val: str) -> str:
    if not val:
        return "[NOT SET]"
    if len(val) <= 6:
        return "****"
    return f"{val[:4]}****{val[-2:]}"


def validate_env() -> None:
    """Validate required environment variables on startup and print a clear masked diagnostic report."""
    print("================================================================")
    print("           RANKFORGE PRODUCTION ENVIRONMENT DIAGNOSTIC          ")
    print("================================================================")
    
    # Core variables
    core_vars = {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
        "NVIDIA_API_KEY": NVIDIA_API_KEY,
        "REDIS_URL": REDIS_URL,
    }
    
    # Optional integrations
    integration_vars = {
        "SERPER_API_KEY": SERPER_API_KEY,
        "SLACK_BOT_TOKEN": SLACK_BOT_TOKEN,
        "SLACK_WEBHOOK_URL": SLACK_WEBHOOK_URL,
        "RESEND_API_KEY": RESEND_API_KEY,
        "AHREFS_API_KEY": AHREFS_API_KEY,
        "GOOGLE_CLIENT_ID": GOOGLE_CLIENT_ID,
        "WP_SITE_URL": WP_SITE_URL or WORDPRESS_URL,
    }

    missing_core = []
    for k, v in core_vars.items():
        masked = _mask(v)
        status = "[OK]" if v else "[MISSING]"
        print(f"  [CORE] {k.ljust(20)}: {masked.ljust(18)} {status}")
        if not v and k in ["SUPABASE_URL", "SUPABASE_KEY", "NVIDIA_API_KEY"]:
            missing_core.append(k)

    print("----------------------------------------------------------------")
    for k, v in integration_vars.items():
        masked = _mask(v)
        status = "[CONFIGURED]" if v else "[OPTIONAL/FALLBACK]"
        print(f"  [OPT]  {k.ljust(20)}: {masked.ljust(18)} {status}")

    print("================================================================")

    if missing_core and not os.getenv("TESTING"):
        error_msg = f"FATAL: Missing critical environment variables: {', '.join(missing_core)}. RankForge cannot start without these."
        logger.error(error_msg)
        warnings.warn(error_msg)
