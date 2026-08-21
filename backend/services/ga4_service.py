import asyncio
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("backend.services.ga4_service")


class GA4Service:
    """Google Analytics 4 Data API service for real traffic data."""
    
    def __init__(self, property_id: str = None, credentials_path: str = None):
        self.property_id = property_id or os.getenv("GA4_PROPERTY_ID")
        self.credentials_path = credentials_path or os.getenv("GA4_CREDENTIALS_PATH")
        self._initialized = False
    
    def _ensure_initialized(self):
        """Initialize GA4 data API client."""
        if self._initialized:
            return
        
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            
            if not self.credentials_path:
                raise ValueError("GA4 credentials not configured")
            
            self._credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/analytics.readonly']
            )
            
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
        return bool(self.property_id and self.credentials_path)
    
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
                'message': 'Set GA4_PROPERTY_ID and GA4_CREDENTIALS_PATH environment variables',
                'source': 'ga4'
            }
        
        try:
            self._ensure_initialized()
            
            request_body = {
                'dateRanges': [{'startDate': start_date, 'endDate': end_date}],
                'dimensions': [{'name': 'pagePath'}, {'name': 'sessionDefaultChannel'}],
                'metrics': [
                    {'name': 'sessions'},
                    {'name': 'totalUsers'},
                    {'name': 'averageSessionDuration'},
                    {'name': 'bounceRate'}
                ],
                'limit': limit,
                'dimensionFilter': {
                    'filter': {
                        'fieldName': 'pagePath',
                        'stringFilter': {'matchType': 'EXACT'}
                    }
                }
            }
            
            response = self._service.runReport(body=request_body)
            
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
            return {'error': 'GA4 not configured', 'source': 'ga4'}
        
        try:
            self._ensure_initialized()
            
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
            
            response = self._service.runReport(body=request_body)
            
            metrics = response.get('rows', [{}])[0].get('metricValues', [])
            
            return {
                'sessions': int(metrics[0].get('value', 0)) if metrics else 0,
                'total_users': int(metrics[1].get('value', 0)) if len(metrics) > 1 else 0,
                'engagement_rate': float(metrics[2].get('value', 0)) if len(metrics) > 2 else 0,
                'avg_session_duration': float(metrics[3].get('value', 0)) if len(metrics) > 3 else 0,
                'screen_page_views': int(metrics[4].get('value', 0)) if len(metrics) > 4 else 0,
                'source': 'ga4'
            }
        
        except Exception as e:
            return {'error': str(e), 'source': 'ga4'}


async def get_page_traffic(property_id: str = None) -> Dict:
    """Standalone function for page traffic."""
    service = GA4Service(property_id)
    return await service.get_page_traffic()


async def get_content_performance(property_id: str = None) -> Dict:
    """Standalone function for content performance."""
    service = GA4Service(property_id)
    return await service.get_content_performance()