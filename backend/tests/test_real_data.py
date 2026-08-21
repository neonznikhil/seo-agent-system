import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock


class TestRealDataService:
    """Test real data integration - NO HALLUCINATIONS."""
    
    @pytest.mark.asyncio
    async def test_no_hallucinated_metrics_without_gsc(self):
        """Test that missing GSC returns error, not fake data."""
        from backend.services.real_data_service import RealDataService
        
        service = RealDataService()
        
        result = await service.get_keyword_data("fake keyword")
        
        assert 'error' in result or result.get('data', {}).get('gsc', {}).get('note') is not None
    
    @pytest.mark.asyncio
    async def test_crawlee_serp_returns_real_data(self):
        """Test Crawlee SERP extraction."""
        from backend.services.crawlee_service import CrawleeService
        
        service = CrawleeService()
        
        try:
            result = await service.extract_serp_landscape("seo best practices")
            
            assert result.get('keyword') == 'seo best practices'
            assert result.get('source') == 'crawlee_serp'
            assert result.get('no_hallucination') == True
            
            if result.get('top_pages'):
                for page in result['top_pages']:
                    assert 'url' in page
                    assert 'title' in page
        except ImportError:
            pytest.skip("Crawlee not installed")
    
    @pytest.mark.asyncio
    async def test_gsc_keyword_data_has_sources(self):
        """Test GSC data has proper source attribution."""
        from backend.services.gsc_service import GSCService
        
        service = GSCService()
        
        if not service.is_connected():
            pytest.skip("GSC credentials not configured")
        
        result = await service.get_keyword_performance(row_limit=10)
        
        assert 'source' in result
        assert result['source'] == 'gsc'
        
        if result.get('keywords'):
            for kw in result['keywords']:
                assert 'keyword' in kw
                assert 'impressions' in kw
                assert 'clicks' in kw
                assert 'data_source' in kw


class TestResearchTools:
    """Test research tools using real data."""
    
    @pytest.mark.asyncio
    async def test_serp_winning_patterns_no_hallucination(self):
        """Test SERP winning patterns are from real data."""
        from backend.agents.tools.research_tools import ResearchTools
        
        tools = ResearchTools()
        
        try:
            result = await tools.analyze_serp_winning_patterns("content marketing")
            
            assert result.get('verified_real_data') == True
            assert result.get('keyword') == 'content marketing'
            assert 'avg_word_count' in result
            assert 'common_h2_structures' in result
            
            assert isinstance(result['avg_word_count'], (int, float))
            assert isinstance(result['common_h2_structures'], list)
        
        except Exception as e:
            if "Crawlee not installed" in str(e):
                pytest.skip("Crawlee not installed")
            raise


class TestNoFirecrawlImports:
    """Verify Firecrawl imports have been removed."""
    
    def test_no_firecrawl_imports(self):
        """Ensure no firecrawl imports remain in codebase."""
        import os
        import re
        
        firecrawl_patterns = [
            r'from firecrawl',
            r'import firecrawl',
            r'firecrawl\.',
        ]
        
        for root, dirs, files in os.walk('backend'):
            dirs[:] = [d for d in dirs if d not in ['venv', '__pycache__', '.venv']]
            
            for f in files:
                if f.endswith('.py'):
                    filepath = os.path.join(root, f)
                    with open(filepath, 'r') as rf:
                        content = rf.read()
                    
                    for pattern in firecrawl_patterns:
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        assert len(matches) == 0, f"Firecrawl import found in {filepath}: {matches}"


class TestContentPipelineSchema:
    """Test database schema for content pipeline."""
    
    def test_schema_has_required_tables(self):
        """Verify database schema has all required tables."""
        from pathlib import Path
        
        schema_file = Path('backend/supabase_real_data_schema.sql')
        assert schema_file.exists(), "Schema file missing"
        
        content = schema_file.read_text()
        
        required_tables = [
            'serp_landscape',
            'content_pipeline_logs',
            'content_expert_reviews',
            'internal_link_suggestions',
            'data_source_alerts'
        ]
        
        for table in required_tables:
            assert f'CREATE TABLE IF NOT EXISTS {table}' in content or f'CREATE TABLE {table}' in content, f"Table {table} missing from schema"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])