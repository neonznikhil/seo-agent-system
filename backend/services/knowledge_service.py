"""
Knowledge Service - Handles Grounded vs Deep Web modes.
Verified knowledge sources take precedence in combined mode.
"""

import os
import uuid
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

logger = logging.getLogger("backend.services.knowledge_service")

try:
    import PyMuPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


class KnowledgeSource(BaseModel):
    id: Optional[str] = None
    website_id: Optional[str] = None
    source_type: str
    title: str
    file_path: Optional[str] = None
    content_extracted: Optional[str] = None
    is_verified: bool = True
    created_at: Optional[str] = None


class KnowledgeService:
    """SINGLE SOURCE OF TRUTH for verified business knowledge."""
    
    SOURCE_TYPES = ['google_drive', 'notion', 'pdf', 'docx', 'url', 'brand_brief', 'founder_insights', 'customer_research']
    
    def __init__(self, website_id: str = None):
        self.website_id = website_id
        self.supabase = None
    
    def _get_supabase(self):
        if not self.supabase:
            from ..database import get_supabase
            self.supabase = get_supabase()
        return self.supabase
    
    async def upload_file(self, 
                          file_path: str, 
                          title: str,
                          file_type: str,
                          website_id: str) -> Dict[str, Any]:
        """Upload and parse PDF/DOCX/TXT files."""
        content = None
        
        if file_type == 'pdf' and PDF_AVAILABLE:
            try:
                doc = PyMuPDF.open(file_path)
                content = ""
                for page in doc:
                    content += page.get_text()
                doc.close()
            except Exception as e:
                logger.error(f"PDF parse error: {e}")
                return {"error": str(e), "status": "failed"}
        
        elif file_type == 'docx' and DOCX_AVAILABLE:
            try:
                doc = Document(file_path)
                content = "\n".join([p.text for p in doc.paragraphs])
            except Exception as e:
                logger.error(f"DOCX parse error: {e}")
                return {"error": str(e), "status": "failed"}
        
        elif file_type == 'txt':
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
            except Exception as e:
                return {"error": str(e), "status": "failed"}
        
        if not content:
            return {"error": "Could not extract content", "status": "failed"}
        
        from ..database import call_nim_llm
        embedding = await call_nim_llm(
            prompt=f"Generate embedding vector for this content (return as comma-separated list of floats): {content[:1000]}",
            website_id=website_id
        )
        
        source = {
            "id": str(uuid.uuid4()),
            "website_id": website_id,
            "source_type": "pdf" if file_type == 'pdf' else ('docx' if file_type == 'docx' else 'url'),
            "title": title,
            "file_path": file_path,
            "content_extracted": content[:50000],
            "embedding": content[:1000],
            "is_verified": True,
            "created_at": datetime.utcnow().isoformat()
        }
        
        supabase = self._get_supabase()
        supabase.table("knowledge_sources").insert(source).execute()
        
        return {"status": "success", "id": source["id"], "word_count": len(content.split())}
    
    async def add_url_content(self,
                              url: str,
                              title: str,
                              website_id: str) -> Dict[str, Any]:
        """Crawl URL and add as verified knowledge source."""
        from .crawlee_service import CrawleeService
        
        crawler = CrawleeService()
        result = await crawler.crawl_site_structure([url], max_requests=1)
        
        if not result:
            return {"error": "Could not crawl URL", "status": "failed"}
        
        page_data = result[0]
        content = f"Title: {page_data.get('title', '')}\n"
        content += f"H1s: {page_data.get('h1', [])}\n"
        content += f"H2s: {page_data.get('h2s', [])}\n"
        content += f"Content: {page_data.get('word_count', 0)} words\n"
        if page_data.get('meta_description'):
            content += f"Meta: {page_data.get('meta_description')}\n"
        
        source = {
            "id": str(uuid.uuid4()),
            "website_id": website_id,
            "source_type": "url",
            "title": title,
            "file_path": url,
            "content_extracted": content,
            "is_verified": True,
            "created_at": datetime.utcnow().isoformat()
        }
        
        supabase = self._get_supabase()
        supabase.table("knowledge_sources").insert(source).execute()
        
        return {"status": "success", "id": source["id"], "source_type": "url"}
    
    async def connect_google_drive(self,
                                   drive_file_ids: List[str],
                                   access_token: str,
                                   website_id: str) -> Dict[str, Any]:
        """Connect Google Drive files."""
        import requests
        
        added = []
        for file_id in drive_file_ids:
            try:
                headers = {"Authorization": f"Bearer {access_token}"}
                resp = requests.get(
                    f"https://www.googleapis.com/drive/v3/files/{file_id}",
                    headers=headers,
                    params={"fields": "name,mimeType,webContentLink"}
                )
                
                if resp.status_code == 200:
                    file_info = resp.json()
                    result = await self.add_url_content(
                        url=file_info.get("webContentLink", ""),
                        title=file_info.get("name", f"Drive file {file_id}"),
                        website_id=website_id
                    )
                    if result.get("status") == "success":
                        added.append(result)
            except Exception as e:
                logger.warning(f"Drive file {file_id} error: {e}")
        
        return {"status": "success", "files_added": len(added), "details": added}
    
    async def connect_notion(self,
                             notion_database_id: str,
                             api_key: str,
                             website_id: str) -> Dict[str, Any]:
        """Connect Notion database pages."""
        import requests
        
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28"
            }
            
            resp = requests.post(
                f"https://api.notion.com/v1/databases/{notion_database_id}/query",
                headers=headers,
                json={"page_size": 100}
            )
            
            if resp.status_code != 200:
                return {"error": f"Notion API error: {resp.status_code}", "status": "failed"}
            
            pages = resp.json().get("results", [])
            added = []
            
            for page in pages:
                title = page.get("properties", {}).get("title", [{}])[0].get("plain_text", "Untitled")
                url = page.get("url", "")
                
                result = await self.add_url_content(url=url, title=title, website_id=website_id)
                if result.get("status") == "success":
                    added.append(result)
            
            return {"status": "success", "pages_added": len(added)}
        
        except Exception as e:
            return {"error": str(e), "status": "failed"}
    
    async def get_knowledge_for_topic(self,
                                        topic: str,
                                        website_id: str,
                                        threshold: float = 0.75) -> List[Dict]:
        """Find verified knowledge sources relevant to topic using embedding similarity."""
        supabase = self._get_supabase()
        
        sources = supabase.table("knowledge_sources").select("*").eq("website_id", website_id).eq("is_verified", True).execute().data or []
        
        if not sources:
            return []
        
        relevant = []
        for source in sources:
            score = await self._calculate_similarity(topic, source.get("content_extracted", ""))
            if score >= threshold:
                relevant.append({
                    "source": source,
                    "similarity": score,
                    "confidence": "high" if score > 0.85 else "medium" if score > 0.75 else "low"
                })
        
        return sorted(relevant, key=lambda x: x["similarity"], reverse=True)
    
    async def _calculate_similarity(self, topic: str, content: str) -> float:
        """Calculate topic-content similarity using LLM."""
        from ..database import call_nim_llm
        
        if not content:
            return 0.0
        
        prompt = f"""Rate similarity 0-1 between topic and content.
Topic: {topic[:200]}
Content: {content[:500]}...
Return just the number."""
        
        try:
            result = await call_nim_llm(prompt)
            return float(result.strip().split()[0])
        except:
            return 0.5
    
    async def get_verified_facts(self, keyword: str, website_id: str) -> List[Dict]:
        """Get verified facts for keyword from knowledge sources."""
        relevant = await self.get_knowledge_for_topic(keyword, website_id)
        
        facts = []
        for item in relevant:
            source = item.get("source", {})
            content = source.get("content_extracted", "")
            
            if keyword.lower() in content.lower():
                facts.append({
                    "source": source.get("title"),
                    "source_type": source.get("source_type"),
                    "url": source.get("file_path"),
                    "content_snippet": content[:200],
                    "confidence": item.get("confidence"),
                    "verified": True
                })
        
        return facts


async def get_knowledge_for_topic(topic: str, website_id: str) -> List[Dict]:
    """Standalone function."""
    service = KnowledgeService(website_id)
    return await service.get_knowledge_for_topic(topic, website_id)


async def get_verified_facts(keyword: str, website_id: str) -> List[Dict]:
    """Standalone function."""
    service = KnowledgeService(website_id)
    return await service.get_verified_facts(keyword, website_id)