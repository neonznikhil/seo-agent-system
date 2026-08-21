import os
import warnings
from dotenv import load_dotenv

load_dotenv()

DUPLICATE_THRESHOLD = float(os.getenv("DUPLICATE_THRESHOLD", "0.85"))
GSC_CREDENTIALS_PATH = os.getenv("GSC_CREDENTIALS_PATH", "")
GA4_CREDENTIALS_PATH = os.getenv("GA4_CREDENTIALS_PATH", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
WP_SITE_URL = os.getenv("WP_SITE_URL", "")
WP_OAUTH_CLIENT_ID = os.getenv("WP_OAUTH_CLIENT_ID", "")
WP_OAUTH_CLIENT_SECRET = os.getenv("WP_OAUTH_CLIENT_SECRET", "")
WP_OAUTH_AUTHORIZE_URL = os.getenv("WP_OAUTH_AUTHORIZE_URL", "")
WP_OAUTH_TOKEN_URL = os.getenv("WP_OAUTH_TOKEN_URL", "")
TOKEN_ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY", "")
WORDPRESS_URL = os.getenv("WORDPRESS_URL", "") or WP_SITE_URL
WORDPRESS_USERNAME = os.getenv("WORDPRESS_USERNAME", "")
WORDPRESS_APP_PASSWORD = os.getenv("WORDPRESS_APP_PASSWORD", "")
WP_API_URL = os.getenv("WP_API_URL", "")
WP_SITES_FILE = os.getenv("WP_SITES_FILE", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".data", "wordpress_sites.json"))
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
PAGESPEED_API_KEY = os.getenv("PAGESPEED_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
REDIRECT_URI = os.getenv("REDIRECT_URI", f"{BACKEND_URL}/api/wordpress/oauth/callback")

_DEFAULT_CORS_ORIGINS = [FRONTEND_URL, "http://localhost:3000", "http://127.0.0.1:3000"]
ALLOWED_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_CORS_ORIGINS", ",".join(_DEFAULT_CORS_ORIGINS)).split(",")
    if origin.strip()
]
ALLOWED_CORS_ORIGIN_REGEX = os.getenv(
    "ALLOWED_CORS_ORIGIN_REGEX", r"https://.*\.vercel\.app"
)


def validate_env() -> None:
    missing = []
    if not os.getenv("NVIDIA_API_KEY"):
        missing.append("NVIDIA_API_KEY")
    if not os.getenv("SUPABASE_URL"):
        missing.append("SUPABASE_URL")
    if not os.getenv("SUPABASE_KEY"):
        missing.append("SUPABASE_KEY")
    if missing:
        warnings.warn(f"Missing env vars: {', '.join(missing)}")
    if not os.getenv("GSC_CREDENTIALS_PATH"):
        warnings.warn("GSC_CREDENTIALS_PATH not set - GSC tools will return empty results instead of mock data")
