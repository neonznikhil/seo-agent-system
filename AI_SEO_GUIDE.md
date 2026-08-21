# AI-SEO, AEO, and GEO Optimization Guide

This document describes the enhanced SEO Agent System with AI/LLM optimization capabilities.

## Overview

The system now optimizes for three key visibility dimensions:

### 1. SEO (Search Engine Optimization)
Traditional keyword ranking through:
- Technical audits (crawlability, speed, schema)
- On-page optimization (titles, content, internal linking)
- Backlink analysis and building

### 2. AEO (Answer Engine Optimization)
Content designed for featured snippets, People Also Ask, and search result answers:
- Direct answer paragraphs (40-50 words)
- Structured FAQ sections
- Comparison tables and data visualizations
- Statistics and citations from authoritative sources

### 3. GEO (Generative Engine Optimization)
Content designed for AI/LLM citations and training data:
- Entity recognition and markup
- Verifiable data points with source citations
- Clear conclusions for AI summarization
- Structured data for passage indexing

## New Tools and Features

### SEO/AEO/GEO Analyzer Tool
Analyzes URLs for:
- Traditional SEO issues
- Featured snippet opportunities
- AI/LLM visibility barriers
- E-E-A-T signals

### SERP Analyzer Tool
Analyzes search results for:
- Featured snippet opportunities
- People Also Ask questions
- Knowledge panel triggers
- Competitor gaps

### Content Optimizer Tool
Analyzes content for:
- Keyword density and LSI usage
- AEO optimization (direct answers, tables, FAQ)
- GEO readiness (entities, citations, verifiability)
- E-E-A-T score calculation

### New API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/seo-analysis/{website_id}/{url}` | GET | Full SEO/AEO/GEO site analysis |
| `/api/serp-analysis/{website_id}?query=` | GET | SERP feature analysis |
| `/api/optimize-content/{website_id}` | POST | Content optimization suggestions |
| `/api/aeo-score/{website_id}` | GET | AEO readiness score |
| `/api/geo-readiness/{website_id}` | GET | GEO/LLM citation readiness |
| `/api/content-aeo-optimize/{website_id}` | POST | Optimize existing content for answers |
| `/api/content-geo-optimize/{website_id}` | POST | Optimize for AI citation |

## Agent Improvements

### Auditor Agent (SEO/AEO/GEO Auditor)
- Identifies ranking-blocking issues
- Finds featured snippet opportunities
- Detects AI/LLM visibility barriers
- Prioritizes by AI impact score

### Writer Agent (AI-First SEO Content Strategist)
- Creates content for both search AND AI
- Optimizes for E-E-A-T signals
- Structures for passage indexing
- Targets featured snippets and AI citations

### Technical SEO Agent (AI-Ready Technical SEO Specialist)
- Implements FAQ/HowTo schema
- Optimizes for Core Web Vitals
- Prepares for LLM accessibility
- Implements entity markup

## Content Optimization Pattern

AI-read content now follows:

```
1. Direct Answer (50 words or less)
2. Structured Data (tables, lists)
3. Data Points (statistics with citations)
4. FAQ Section (4+ questions)
5. Key Takeaways
6. Internal Links
```

## Running Locally

```bash
# Backend
venv\Scripts\python.exe -m uvicorn backend.mock_main:app --port 8000

# Frontend
cd frontend-next
node node_modules\next\dist\bin\next dev --port 3000
```

## Environment Variables

Required for full functionality:
- `SUPABASE_URL` / `SUPABASE_KEY`
- `NVIDIA_API_KEY` (for NIM LLM calls)
- `Crawlee_API_KEY`
- `GSC_CREDENTIALS_PATH`

## Dashboard Improvements

The dashboard now shows:
- **SEO Score** (0-100)
- **AEO Opportunities** count
- **GEO Readiness** score
- **AI Citation Potential** percentage
- Real-time agent activity for AI optimization tasks

## Best Practices

1. **Always include a direct answer** at the beginning of content
2. **Use structured data** (FAQ, HowTo, Table schema)
3. **Add verifiably citations** from authoritative sources
4. **Include 4+ FAQ questions** for People Also Ask
5. **Add data tables** with clear headers
6. **Include statistics** with source attributions
7. **Optimize for Core Web Vitals**
8. **Implement entity markup** for brand/products

## Safety Features

The system maintains all critical safety gates:
- Human approval required for all publishing
- 14-day homepage update cooldown
- Rate limiting (5 approvals/minute)
- Deletion blocked for safety
- All actions logged to Supabase tasks table
