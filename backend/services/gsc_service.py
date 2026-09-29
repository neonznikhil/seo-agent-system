import json
import asyncio
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
logger = logging.getLogger("backend.services.gsc_service")


class GSCService:
    """Google Search Console API service for real traffic data."""
    
    def __init__(self, website_url: str = None, credentials_path: str = None):
        self.website_url = (
            website_url
            or os.getenv("GSC_SITE_URL")
            or os.getenv("GSC_PROPERTY")
            or "https://accident.innovatcs.com"
        )
        self.credentials_path = credentials_path or os.getenv("GSC_CREDENTIALS_PATH")
        self.service = None

    def _load_oauth_credentials(self):
        """Load OAuth2 credentials from token file or environment variables."""
        token_paths = [
            os.path.join(os.path.dirname(__file__), "..", "google_oauth_tokens.json"),
            os.path.join(os.getcwd(), "backend", "google_oauth_tokens.json"),
            os.path.join(os.getcwd(), "google_oauth_tokens.json"),
        ]
        tokens = {}
        for p in token_paths:
            if os.path.isfile(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        tokens = json.load(f)
                    if tokens.get("access_token") or tokens.get("refresh_token"):
                        break
                except Exception:
                    pass

        access_token = tokens.get("access_token") or os.getenv("GOOGLE_ACCESS_TOKEN")
        refresh_token = tokens.get("refresh_token") or os.getenv("GOOGLE_REFRESH_TOKEN")
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

        if access_token or refresh_token:
            try:
                from google.oauth2.credentials import Credentials
                creds = Credentials(
                    token=access_token,
                    refresh_token=refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=client_id,
                    client_secret=client_secret,
                    scopes=[
                        'https://www.googleapis.com/auth/webmasters.readonly',
                        'https://www.googleapis.com/auth/webmasters'
                    ]
                )
                return creds
            except Exception as e:
                logger.warning(f"Failed to create Google OAuth Credentials: {e}")
        return None
    
    def _get_service(self):
        """Get authenticated GSC API service via OAuth, Service Account file, or JSON string."""
        if self.service:
            return self.service

        from googleapiclient.discovery import build

        # 1. Try OAuth 2.0 Credentials
        oauth_creds = self._load_oauth_credentials()
        if oauth_creds:
            try:
                self.service = build('webmasters', 'v3', credentials=oauth_creds, cache_discovery=False)
                return self.service
            except Exception as e:
                logger.warning(f"GSC OAuth client init failed: {e}")

        # 2. Try Service Account File
        if self.credentials_path and os.path.isfile(self.credentials_path):
            try:
                from google.oauth2 import service_account
                creds = service_account.Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=['https://www.googleapis.com/auth/webmasters']
                )
                self.service = build('webmasters', 'v3', credentials=creds, cache_discovery=False)
                return self.service
            except Exception as e:
                logger.warning(f"GSC service account file init failed: {e}")

        # 3. Try Service Account JSON string in GSC_CREDENTIALS or GOOGLE_APPLICATION_CREDENTIALS
        raw_creds = os.getenv("GSC_CREDENTIALS") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if raw_creds and raw_creds.strip().startswith("{"):
            try:
                from google.oauth2 import service_account
                info = json.loads(raw_creds)
                creds = service_account.Credentials.from_service_account_info(
                    info,
                    scopes=['https://www.googleapis.com/auth/webmasters']
                )
                self.service = build('webmasters', 'v3', credentials=creds, cache_discovery=False)
                return self.service
            except Exception as e:
                logger.warning(f"GSC service account json init failed: {e}")

        raise ValueError("GSC credentials not configured - connect via OAuth or set GSC_CREDENTIALS_PATH")
    
    def is_connected(self) -> bool:
        """Check if GSC is configured via OAuth, service account file, or JSON string."""
        if self._load_oauth_credentials() is not None:
            return True
        if self.credentials_path and os.path.isfile(self.credentials_path):
            return True
        raw_creds = os.getenv("GSC_CREDENTIALS") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if raw_creds and (raw_creds.strip().startswith("{") or os.path.isfile(raw_creds)):
            return True
        return False
    
    async def get_keyword_performance(self, 
                                       start_date: str = None,
                                       end_date: str = None,
                                       dimensions: List[str] = None,
                                       row_limit: int = 5000) -> Dict[str, Any]:
        """Get real keyword performance data from GSC."""
        if dimensions is None:
            dimensions = ['query', 'page', 'device', 'country']
        
        if not start_date:
            start_date = (datetime.utcnow() - timedelta(days=28)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.utcnow().strftime('%Y-%m-%d')
        
        try:
            service = self._get_service()
            
            request_body = {
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': dimensions,
                'rowLimit': row_limit
            }
            
            result = service.searchanalytics().query(
                siteUrl=self.website_url,
                body=request_body
            ).execute()
            
            keywords = []
            for row in result.get('rows', []):
                dims = row.get('keys', [])
                keywords.append({
                    'keyword': dims[0] if len(dims) > 0 else '',
                    'page': dims[1] if len(dims) > 1 else '',
                    'device': dims[2] if len(dims) > 2 else 'desktop',
                    'country': dims[3] if len(dims) > 3 else 'global',
                    'impressions': row.get('impressions', 0),
                    'clicks': row.get('clicks', 0),
                    'ctr': row.get('ctr', 0),
                    'position': row.get('position', 0),
                    'data_source': 'gsc',
                    'date_range': {
                        'start': start_date,
                        'end': end_date
                    }
                })
            
            return {
                'keywords': keywords,
                'total_keywords': len(keywords),
                'total_impressions': sum(k.get('impressions', 0) for k in keywords),
                'total_clicks': sum(k.get('clicks', 0) for k in keywords),
                'avg_position': sum(k.get('position', 0) for k in keywords) / max(len(keywords), 1),
                'source': 'gsc',
                'connected': True
            }
        
        except Exception as e:
            logger.error(f"GSC API error: {e}")
            return {
                'error': str(e),
                'keywords': [],
                'total_keywords': 0,
                'total_impressions': 0,
                'total_clicks': 0,
                'avg_position': 0,
                'source': 'gsc',
                'connected': self.is_connected(),
                'message': 'Connect GSC credentials in environment variables'
            }
    
    async def get_top_pages(self, limit: int = 100) -> Dict[str, Any]:
        """Get top performing pages by clicks."""
        try:
            service = self._get_service()
            
            request_body = {
                'startDate': (datetime.utcnow() - timedelta(days=28)).strftime('%Y-%m-%d'),
                'endDate': datetime.utcnow().strftime('%Y-%m-%d'),
                'dimensions': ['page'],
                'rowLimit': limit
            }
            
            result = service.searchanalytics().query(
                siteUrl=self.website_url,
                body=request_body
            ).execute()
            
            pages = []
            for row in result.get('rows', []):
                dims = row.get('keys', [])
                pages.append({
                    'url': dims[0] if dims else '',
                    'clicks': row.get('clicks', 0),
                    'impressions': row.get('impressions', 0),
                    'ctr': row.get('ctr', 0),
                    'position': row.get('position', 0),
                    'data_source': 'gsc'
                })
            
            return {
                'pages': sorted(pages, key=lambda x: x.get('clicks', 0), reverse=True),
                'total_pages': len(pages),
                'top_click_page': pages[0] if pages else None,
                'source': 'gsc'
            }
        
        except Exception as e:
            return {
                'error': str(e),
                'pages': [],
                'source': 'gsc'
            }
    
    async def get_sitemaps(self) -> Dict[str, Any]:
        """Get sitemap status from GSC."""
        try:
            service = self._get_service()
            
            result = service.sitemaps().list(siteUrl=self.website_url).execute()
            
            sitemaps = []
            for sitemap in result.get('sitemap', []):
                sitemaps.append({
                    'url': sitemap.get('path'),
                    'last_submitted': sitemap.get('lastSubmitted'),
                    'is_final': sitemap.get('isFinal'),
                    'has_error': sitemap.get('errorCount', 0) > 0,
                    'error_count': sitemap.get('errorCount', 0),
                    'warning_count': sitemap.get('warningCount', 0),
                    'submitted_count': sitemap.get('submittedCount', 0),
                    'valid_count': sitemap.get('validCount', 0),
                    'data_source': 'gsc'
                })
            
            return {
                'sitemaps': sitemaps,
                'total_sitemaps': len(sitemaps),
                'sitemaps_with_errors': sum(1 for s in sitemaps if s.get('has_error')),
                'source': 'gsc'
            }
        
        except Exception as e:
            return {
                'error': str(e),
                'sitemaps': [],
                'source': 'gsc'
            }
    
    async def get_crawl_errors(self) -> Dict[str, Any]:
        """Get crawl errors from GSC."""
        try:
            service = self._get_service()
            
            url_crawl_errors = service.urlcrawlerrors().mobile().list(
                siteUrl=self.website_url
            ).execute()
            
            errors = []
            for error in url_crawl_errors.get('pageCrawlErrors', {}).get('mobileErrors', {}).get('errors', []):
                errors.append({
                    'url': error.get('url'),
                    'last_crawled': error.get('lastCrawled'),
                    'responseCode': error.get('responseCode'),
                    'category': error.get('category'),
                    'data_source': 'gsc_mobile'
                })
            
            return {
                'errors': errors,
                'total_errors': len(errors),
                'source': 'gsc'
            }
        
        except Exception as e:
            return {
                'errors': [],
                'total_errors': 0,
                'error': str(e),
                'source': 'gsc'
            }


    async def get_rankings(self, days: int = 30) -> Dict[str, Any]:
        """Fetch search rankings for the site over the specified timeframe."""
        start_date = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
        end_date = datetime.utcnow().strftime('%Y-%m-%d')
        return await self.get_keyword_performance(start_date=start_date, end_date=end_date)


async def get_keyword_performance(website_url: str = None, days: int = 28) -> Dict:
    """Standalone function for keyword performance."""
    service = GSCService(website_url)
    return await service.get_keyword_performance()


async def get_top_pages(website_url: str = None, limit: int = 100) -> Dict:
    """Standalone function for top pages."""
    service = GSCService(website_url)
    return await service.get_top_pages(limit)


async def list_verified_sites(website_url: str = None) -> List[str]:
    """Return the list of verified Search Console properties for the configured account."""
    svc = GSCService(website_url)
    if not svc.is_connected():
        raise ValueError("GSC not configured — set GSC_CREDENTIALS_PATH in Connectors")
    service = svc._get_service()
    sites = service.sites().list().execute()
    verified = [
        s.get("siteUrl")
        for s in (sites.get("siteEntry") or [])
        if s.get("permissionLevel") in ("siteOwner", "siteFullUser", "siteRestrictedUser")
    ]
    return [v for v in verified if v]


async def sync_gsc_data(website_id: Optional[str] = None) -> Dict[str, Any]:
    """Sync GSC search analytics data into database."""
    try:
        from services.analytics_service import AnalyticsService
    except (ImportError, ValueError):
        from backend.services.analytics_service import AnalyticsService
    return await AnalyticsService.sync_gsc_data(website_id=website_id)
