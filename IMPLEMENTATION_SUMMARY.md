# SEO System - 5 Core Capabilities Implementation

## Overview
Complete implementation of Rank Tracking, Competitor Monitoring, Technical Audits, Keyword Research, and Content Optimization with WordPress + Supabase + GSC integration.

---

## CAPABILITY 1: Rank & Performance Tracking

### Database Schema (`supabase_schema_v2.sql`)
```sql
CREATE TABLE rank_tracking (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id),
  keyword TEXT,
  location TEXT DEFAULT 'global',
  device TEXT DEFAULT 'desktop',
  current_position INT,
  previous_position INT,
  url_ranking TEXT,
  search_volume INT,
  visibility_score FLOAT,
  impressions INT,
  clicks INT,
  ctr FLOAT,
  tracked_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE rank_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rank_id UUID REFERENCES rank_tracking(id),
  position INT,
  recorded_at DATE DEFAULT CURRENT_DATE
);
CREATE INDEX idx_rank_website_keyword ON rank_tracking(website_id, keyword);
```

### Tools (`backend/agents/tools/rank_tools.py`)
- `fetch_gsc_performance()` - Get 30-day GSC data
- `get_serp_position(keyword, domain)` - Check current ranking
- `calculate_visibility_score()` - Compute 0-100 visibility metric

### Router (`backend/routers/rank_tracking.py`)
- `GET /api/rank/{website_id}?location=global&device=desktop`
- `GET /api/rank/{website_id}/history?keyword=...`
- `POST /api/rank/{website_id}/track-now`
- `GET /api/rank/{website_id}/visibility`

---

## CAPABILITY 2: Competitor Monitoring

### Database Schema
```sql
CREATE TABLE competitors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id),
  competitor_domain TEXT,
  competitor_name TEXT,
  pricing_page_url TEXT,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE competitor_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  competitor_id UUID REFERENCES competitors(id),
  page_url TEXT,
  content_hash TEXT,
  pricing_data JSONB,
  title TEXT,
  meta_description TEXT,
  h1 TEXT,
  snapshot_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE competitor_changes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  competitor_id UUID REFERENCES competitors(id),
  change_type TEXT,
  old_value TEXT,
  new_value TEXT,
  detected_at TIMESTAMPTZ DEFAULT NOW(),
  is_read BOOLEAN DEFAULT false
);
```

### Tools (`backend/agents/tools/competitor_tools.py`)
- `add_competitor()` - Crawlee domain analysis
- `daily_scrape()` - Scrape pricing pages
- `detect_changes()` - Hash comparison + pricing diff
- `market_trend()` - Aggregate changes summary

### Router (`backend/routers/competitors.py`)
- `GET /api/competitors/{website_id}`
- `POST /api/competitors/{website_id}`
- `GET /api/competitors/{website_id}/changes`
- `GET /api/competitors/{website_id}/trends`

---

## CAPABILITY 3: Technical Audits

### Enhanced Issue Types
- `broken_link` - 404 errors from crawl
- `crawl_error` - Server errors
- `slow_page` - Core Web Vitals issues
- `mobile_usability` - Responsive problems

### Tools (`backend/agents/tools/tech_tools.py`)
- `scan_broken_links()` - Check all hrefs status
- `scan_crawl_errors()` - GSC crawl issue check
- `full_site_audit()` - Run all 6 pillars

---

## CAPABILITY 4: Keyword Research

### Database Schema
```sql
CREATE TABLE keyword_opportunities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id),
  keyword TEXT,
  search_volume INT,
  difficulty FLOAT,
  opportunity_score FLOAT,
  intent TEXT,
  trend TEXT,
  source TEXT,
  is_targeted BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Tools (`backend/agents/tools/keyword_tools.py`)
- `gsc_gap_analysis()` - Striking distance keywords (pos 11-30)
- `competitor_gap()` - Keywords competitors rank for
- `trending_topics()` - Rising search terms
- `calculate_opportunity()` - Score = (volume × 1/pos × ctr) / difficulty

### Router (`backend/routers/keyword_research.py`)
- `GET /api/keywords/{website_id}/opportunities`
- `GET /api/keywords/{website_id}/striking-distance`
- `POST /api/keywords/{website_id}/target/{opp_id}`
- `POST /api/keywords/{website_id}/research-now`

---

## CAPABILITY 5: Content Optimization

### Database Schema
```sql
CREATE TABLE content_optimizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id),
  page_url TEXT,
  current_content_hash TEXT,
  suggestions JSONB,
  optimization_score FLOAT,
  applied BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Tools (`backend/agents/tools/content_optimizer_tools.py`)
- `analyze_page()` - Check keyword placement, length, readability
- `generate_suggestions()` - Use NIM to produce fixes
- `calculate_optimization_score()` - 100 - penalties
- `apply_fix()` - WordPress REST API updates

---

## API Integration

### Dashboard Updates
```javascript
// 5 capability cards with live counts
- Rank Tracking: visibility 73 ↑ 2.1%
- Competitor: 2 new changes
- Tech Audits: health 82
- Keyword Research: 12 opportunities
- Content Optimizer: 5 pages need work
```

### WordPress Integration
All content updates require:
- `X-User-Id` header for approval tracking
- Logging to `critical_action_logs`
- Safety gate for homepage edits

---

## Running the System

```bash
# Backend
cd backend
venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000

# Frontend  
cd frontend-next
node node_modules\next\dist\bin\next dev --port 3000
```

### One-Time Setup
Run migrations:
```sql
-- Copy schema definitions to Supabase SQL Editor
-- Enable vector extension: create extension if not exists vector;
```

Set environment variables in `.env`:
- `SUPABASE_URL`, `SUPABASE_KEY`
- `NVIDIA_API_KEY`
- `Crawlee_API_KEY`
- `WORDPRESS_URL`, `WORDPRESS_USER`, `WORDPRESS_APP_PASSWORD`

---

## Next Steps

1. Apply database migrations to Supabase
2. Run: `python -m backend.agents.scheduler` for daily jobs
3. Access frontend at http://localhost:3000
4. APIs available at http://localhost:8000/api
