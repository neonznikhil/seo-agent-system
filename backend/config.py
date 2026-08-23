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
WORDPRESS_URL = os.getenv("WORDPRESS_URL", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
PAGESPEED_API_KEY = os.getenv("PAGESPEED_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
REDIRECT_URI = os.getenv("REDIRECT_URI", f"{BACKEND_URL}/api/wordpress/oauth/callback")
ALLOWED_CORS_ORIGINS = os.getenv("ALLOWED_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,*").split(",")


def validate_env() -> None:
    missing = []
    if not os.getenv("NVIDIA_API_KEY"):
        missing.append("NVIDIA_API_KEY")
    if not os.getenv("SUPABASE_URL"):
        missing.append("SUPABASE_URL")
    if not os.getenv("SUPABASE_KEY"):
        missing.append("SUPABASE_KEY")
    if missing:
        for m in missing:
            print(f"⚠️ {m} not configured")
        if "SUPABASE_URL" in missing or "SUPABASE_KEY" in missing:
            print("⚠️ Supabase not connected - check .env")
        warnings.warn(f"Missing env vars: {', '.join(missing)}")
    if not os.getenv("GSC_CREDENTIALS_PATH"):
        warnings.warn("GSC_CREDENTIALS_PATH not set - GSC tools will return empty results instead of mock data")

ENCRYPTION_SECRET = os.getenv("ENCRYPTION_SECRET", "gAAAAABl8x4z7k1v5q6w8e9r0t1y2u3i4o5p6a7s8d9f0g1h2j3k4l5z6x7c8v9b0n1m=")
