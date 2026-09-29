import json
import asyncio
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("backend.services.ga4_service")


class GA4Service:
    """Google Analytics 4 Data API service for real traffic data."""
    
    def __init__(self, property_id: str = None, credentials_path: str = None):
        self._property_id = property_id
        self._credentials_path = credentials_path
        self._initialized = False
        self._service = None
        self._credentials = None

    @property
    def property_id(self) -> Optional[str]:
        return self._property_id or os.getenv("GA4_PROPERTY_ID")

    @property_id.setter
    def property_id(self, val: Optional[str]):
        self._property_id = val

    @property
    def credentials_path(self) -> Optional[str]:
        return self._credentials_path or os.getenv("GA4_CREDENTIALS_PATH")

    @credentials_path.setter
    def credentials_path(self, val: Optional[str]):
        self._credentials_path = val

    def _has_oauth_tokens(self) -> bool:
        """Check if OAuth tokens exist."""
        tokens_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "google_oauth_tokens.json")
        if os.path.exists(tokens_file):
            return True
        if os.getenv("GOOGLE_ACCESS_TOKEN") or os.getenv("GOOGLE_REFRESH_TOKEN"):
            return True
        return False

    def _load_oauth_credentials(self):
        """Try loading user OAuth credentials from tokens file or environment."""
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            
            tokens_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "google_oauth_tokens.json")
            data = None
            if os.path.exists(tokens_file):
                with open(tokens_file, "r") as f:
                    data = json.load(f)
            elif os.getenv("GOOGLE_ACCESS_TOKEN") or os.getenv("GOOGLE_REFRESH_TOKEN"):
                data = {
                    "token": os.getenv("GOOGLE_ACCESS_TOKEN"),
                    "refresh_token": os.getenv("GOOGLE_REFRESH_TOKEN"),
                    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                    "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            if data:
                creds = Credentials(
                    token=data.get("token") or data.get("access_token"),
                    refresh_token=data.get("refresh_token"),
                    token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
                    client_id=data.get("client_id") or os.getenv("GOOGLE_CLIENT_ID"),
                    client_secret=data.get("client_secret") or os.getenv("GOOGLE_CLIENT_SECRET"),
                    scopes=['https://www.googleapis.com/auth/analytics.readonly']
                )
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                return creds
        except Exception as e:
            logger.debug(f"GA4 OAuth credentials loading failed: {e}")
        return None

    def _ensure_initialized(self):
        """Initialize GA4 data API client."""
        if self._initialized and self._service:
            return
        
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            creds = self._load_oauth_credentials()
            
            if not creds:
                cred_path = self.credentials_path or os.getenv("GA4_CREDENTIALS_PATH") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                cred_json = os.getenv("GA4_CREDENTIALS") or os.getenv("GSC_CREDENTIALS")
                
                if cred_path and os.path.exists(cred_path):
                    creds = service_account.Credentials.from_service_account_file(
                        cred_path,
                        scopes=['https://www.googleapis.com/auth/analytics.readonly']
                    )
                elif cred_json:
                    info = json.loads(cred_json) if isinstance(cred_json, str) else cred_json
                    creds = service_account.Credentials.from_service_account_info(
                        info,
                        scopes=['https://www.googleapis.com/auth/analytics.readonly']
                    )
                else:
                    raise ValueError("GA4 credentials not configured (neither OAuth nor service account found)")
            
            self._credentials = creds
            self._service = build('analyticsdata', 'v1beta', credentials=self._credentials)
            self._initialized = True
            
        except ImportError as e:
            logger.error(f"GA4 API client not available: {e}")
            raise
        except Exception as e:
            logger.error(f"GA4 initialization failed: {e}")
            raise
    
    def is_connected(self) -> bool:
        """Check if GA4 is configured."""
        has_creds = bool(
            self.credentials_path 
            or os.getenv("GA4_CREDENTIALS")
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            or self._has_oauth_tokens()
        )
        return bool(self.property_id and has_creds)
    
    async def get_page_traffic(self, 
                               start_date: str = None,
                               end_date: str = None,
                               limit: int = 25000) -> Dict[str, Any]:
        """Get real page traffic data from GA4."""
        if not start_date:
            start_date = (datetime.utcnow() - timedelta(days=28)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.utcnow().strftime('%Y-%m-%d')
        
        if not self.is_connected():
            return {
                'error': 'GA4 not configured',
                'pages': [],
                'message': 'Set GA4_PROPERTY_ID and connect Google credentials in Connectors',
                'source': 'ga4',
                'connected': False
            }
        
        try:
            self._ensure_initialized()
            clean_id = str(self.property_id).replace("properties/", "").strip()
            
            request_body = {
                'dateRanges': [{'startDate': start_date, 'endDate': end_date}],
                'dimensions': [{'name': 'pagePath'}, {'name': 'sessionDefaultChannel'}],
                'metrics': [
                    {'name': 'sessions'},
                    {'name': 'totalUsers'},
                    {'name': 'averageSessionDuration'},
                    {'name': 'bounceRate'}
                ],
                'limit': limit
            }
            
            response = self._service.properties().runReport(
                property=f"properties/{clean_id}",
                body=request_body
            ).execute()
            
            pages = []
            for row in response.get('rows', []):
                dims = row.get('dimensionValues', [])
                metrics = row.get('metricValues', [])
                
                page_data = {
                    'page_path': dims[0].get('value', '') if len(dims) > 0 else '',
                    'channel': dims[1].get('value', '') if len(dims) > 1 else '',
                    'sessions': int(metrics[0].get('value', 0)) if len(metrics) > 0 else 0,
                    'total_users': int(metrics[1].get('value', 0)) if len(metrics) > 1 else 0,
                    'avg_session_duration': float(metrics[2].get('value', 0)) if len(metrics) > 2 else 0,
                    'bounce_rate': float(metrics[3].get('value', 0)) if len(metrics) > 3 else 0,
                    'data_source': 'ga4'
                }
                pages.append(page_data)
            
            return {
                'pages': pages,
                'total_sessions': sum(p['sessions'] for p in pages),
                'total_users': sum(p['total_users'] for p in pages),
                'date_range': {'start': start_date, 'end': end_date},
                'source': 'ga4',
                'connected': True
            }
        
        except Exception as e:
            logger.error(f"GA4 API error: {e}")
            return {
                'pages': [],
                'error': str(e),
                'source': 'ga4',
                'connected': self.is_connected()
            }
    
    async def get_content_performance(self, limit: int = 100) -> Dict[str, Any]:
        """Get content performance using page-level analysis."""
        traffic_data = await self.get_page_traffic()
        
        if traffic_data.get('error'):
            return traffic_data
        
        pages = traffic_data.get('pages', [])
        
        content_pages = [
            p for p in pages 
            if any(path in p['page_path'].lower() for path in ['/blog/', '/article/', '/post/', '/content/'])
        ]
        
        product_pages = [
            p for p in pages 
            if any(path in p['page_path'].lower() for path in ['/product/', '/features/', '/pricing/', '/demo/'])
        ]
        
        return {
            'content_pages': sorted(content_pages, key=lambda x: x.get('sessions', 0), reverse=True)[:limit],
            'product_pages': sorted(product_pages, key=lambda x: x.get('sessions', 0), reverse=True)[:limit],
            'top_content': content_pages[:10] if content_pages else [],
            'high_traffic_pages': pages[:10] if pages else [],
            'source': 'ga4'
        }
    
    async def get_user_engagement(self) -> Dict[str, Any]:
        """Get user engagement metrics."""
        if not self.is_connected():
            return {'error': 'GA4 not configured', 'source': 'ga4', 'connected': False}
        
        try:
            self._ensure_initialized()
            clean_id = str(self.property_id).replace("properties/", "").strip()
            
            request_body = {
                'dateRanges': [{'startDate': '30daysAgo', 'endDate': 'today'}],
                'metrics': [
                    {'name': 'sessions'},
                    {'name': 'totalUsers'},
                    {'name': 'engagementRate'},
                    {'name': 'averageSessionDuration'},
                    {'name': 'screenPageViews'}
                ]
            }
            
            response = self._service.properties().runReport(
                property=f"properties/{clean_id}",
                body=request_body
            ).execute()
            
            metrics = response.get('rows', [{}])[0].get('metricValues', [])
            
            return {
                'sessions': int(metrics[0].get('value', 0)) if metrics else 0,
                'total_users': int(metrics[1].get('value', 0)) if len(metrics) > 1 else 0,
                'engagement_rate': float(metrics[2].get('value', 0)) if len(metrics) > 2 else 0,
                'avg_session_duration': float(metrics[3].get('value', 0)) if len(metrics) > 3 else 0,
                'screen_page_views': int(metrics[4].get('value', 0)) if len(metrics) > 4 else 0,
                'source': 'ga4',
                'connected': True
            }
        
        except Exception as e:
            return {'error': str(e), 'source': 'ga4', 'connected': self.is_connected()}


async def get_page_traffic(property_id: str = None) -> Dict:
    """Standalone function for page traffic."""
    service = GA4Service(property_id)
    return await service.get_page_traffic()


async def get_content_performance(property_id: str = None) -> Dict:
    """Standalone function for content performance."""
    service = GA4Service(property_id)
    return await service.get_content_performance()


class _GA4SingletonWrapper(GA4Service):
    """Module-level singleton exposing get_recent_sessions for connector tests."""
    def __init__(self):
        super().__init__()

    async def get_recent_sessions(self, website_id: str = None, days: int = 7) -> Dict[str, Any]:
        return await get_recent_sessions(website_id=website_id, days=days)


ga4_service = _GA4SingletonWrapper()


async def get_recent_sessions(website_id: str = None, days: int = 7) -> Dict[str, Any]:
    """Real GA4 call returning total sessions over the last `days` days."""
    if not ga4_service.is_connected():
        return {
            "connected": False,
            "error": "GA4 not configured — set GA4_PROPERTY_ID and connect Google credentials in Connectors",
            "sessions": 0,
        }
    try:
        ga4_service._ensure_initialized()
        clean_id = str(ga4_service.property_id).replace("properties/", "").strip()
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        request_body = {
            "dateRanges": [{"startDate": start_date, "endDate": end_date}],
            "metrics": [{"name": "sessions"}],
        }
        response = ga4_service._service.properties().runReport(
            property=f"properties/{clean_id}",
            body=request_body
        ).execute()
        metrics = response.get("rows", [{}])[0].get("metricValues", [])
        sessions = int(metrics[0].get("value", 0)) if metrics else 0
        return {
            "connected": True,
            "sessions": sessions,
            "message": f"GA4 returned {sessions} sessions for the last {days} days",
        }
    except Exception as e:
        logger.error(f"GA4 recent-sessions error: {e}")
        return {"connected": False, "error": str(e)[:200], "sessions": 0}