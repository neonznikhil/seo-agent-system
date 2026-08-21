# RANKFORGE - Autonomous SEO Agent System

## Setup

1. Clone repo
2. Create venv: `python -m venv venv && source venv/bin/activate` (Windows: `venv\\Scripts\\activate`)
3. Install deps: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill values
5. Run Supabase SQL schemas: `supabase_schema.sql` then `supabase_schema_v2.sql`
6. Start backend: `uvicorn backend.main:app --reload`
7. Start frontend: `cd frontend-next && npm install && npm run dev`

## WordPress Integration (Application Passwords)

The WordPress integration talks to the real WordPress REST API (`/wp-json/wp/v2`) using
Application Passwords over HTTP Basic Auth. No plugin and no WordPress premium plan required.

### 1. Create an Application Password

`WP Admin > Users > Your User > Application Passwords > New > Copy`

Copy the generated password (spaces are fine, they are part of the password).

### 2. Connect a site

Either set the defaults in `.env`:

```bash
WORDPRESS_URL=https://yoursite.com
WORDPRESS_USERNAME=your-wp-user
WORDPRESS_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
```

...or connect from the UI: open http://localhost:3000/connectors (or `/websites`),
enter the site URL, username and Application Password, click **Test Connection**, then **Connect Site**.
Connected sites are stored in Supabase when configured, otherwise in a local JSON file
(`.data/wordpress_sites.json`, override with `WP_SITES_FILE`).

### 3. Publish

On http://localhost:3000/writer use **Publish to WordPress (Draft)**, or call the API directly:

```bash
curl -X POST http://localhost:8000/api/wordpress/test \
  -H 'Content-Type: application/json' \
  -d '{"site_url":"https://yoursite.com","username":"user","app_password":"xxxx xxxx"}'

curl -X POST http://localhost:8000/api/wordpress/publish \
  -H 'Content-Type: application/json' \
  -d '{"title":"Hello","content":"<p>Draft body</p>","status":"draft"}'
```

Endpoints: `POST /api/wordpress/test`, `POST /api/wordpress/connect`,
`GET /api/wordpress/sites`, `DELETE /api/wordpress/sites/{id}`, `POST /api/wordpress/publish`,
`GET /api/wordpress/posts`. OAuth (WordPress.com) remains available under
`/api/wordpress/oauth/*` when the OAuth env vars are set.

## Docker Deployment

```bash
cp .env.example .env   # fill in what you have; missing keys degrade gracefully
docker compose up --build
# backend  -> http://localhost:8000/docs
# frontend -> http://localhost:3000
```

`render.yaml` deploys the backend (free plan, health check `/health`) and `vercel.json`
builds the Next.js frontend from `frontend-next/`. Set `NEXT_PUBLIC_API_URL` on Vercel to the
backend URL and `FRONTEND_URL` on Render to the Vercel URL (`*.vercel.app` origins are already
allowed by CORS).

## Lightweight Deployment (No Docker)

This system is designed to run lightweight without Docker or heavy infrastructure. All you need is:

### Backend Requirements
- Python 3.8+
- Supabase account (free tier works)
- NVIDIA API key for NIM models (free tier available)
- Crawlee API key (free tier available)
- Optional: Redis for rate limiting (system works without it with warning logs)
- Optional: WordPress site for publishing (system works in preview-only mode)

### Frontend Requirements
- Node.js 16+
- Modern browser

### Running Locally

**Backend:**
```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
# Health check: http://localhost:8000/health
```

**Frontend:**
```bash
cd frontend-next
npm install
npm run dev -- --port 3000
# Open: http://localhost:3000/dashboard
```

**Redis (Optional - for queue locks):**
- Download Redis from https://redis.io/download
- Run `redis-server` locally
- Or skip - system works without Redis with warning log

**Supabase Setup:**
1. Create a new Supabase project
2. Run `supabase_schema.sql` in the SQL Editor
3. Run `supabase_schema_v2.sql` in the SQL Editor
4. Enable the vector extension if not already enabled

### Environment Variables

Copy `.env.example` to `.env` and fill in:
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_KEY`: Your Supabase anon key
- `SUPABASE_SERVICE_KEY`: Your Supabase service role key
- `NVIDIA_API_KEY`: Your NVIDIA API key for NIM models
- `Crawlee_API_KEY`: Your Crawlee API key
- `WORDPRESS_URL`: Your WordPress site URL (optional)
- `WORDPRESS_USER`: WordPress username (optional)
- `WORDPRESS_APP_PASSWORD`: WordPress application password (optional)
- `GSC_CREDENTIALS_PATH`: Path to Google Service Account JSON (optional)
- `REDIS_URL`: Redis connection string (defaults to localhost:6379)
- `NEXT_PUBLIC_API_URL`: Frontend API URL (defaults to http://localhost:8000)

## Boss Demo Script (RANKFORGE)

```bash
echo "=== RANKFORGE DEMO ==="
echo "1. Health check"
curl http://localhost:8000/health

echo "2. List websites"
curl http://localhost:8000/api/websites

echo "3. Kickoff crew"
python -c "import asyncio; from backend.agents.crew import plan_blogs_for_website; print(asyncio.run(plan_blogs_for_website('demo-wid')))"
```

## Testing

```bash
python -m pytest backend/tests/ -v
```

## AI Web Browsing & Real-Time Data Collection

The system now includes powerful browsing and data collection capabilities for AI agents:

### Tools Available

1. **Web Browser Tool** (`backend/agents/tools/web_browser_tool.py`)
   - Full browser automation with Playwright
   - JavaScript rendering support
   - Extract: content, links, images, tables, SEO data
   - Max 10 URLs per request

2. **Real-Time Data Tool** (`backend/agents/tools/real_time_data_tool.py`)
   - News aggregation
   - Social media sentiment analysis
   - Public API data fetching
   - Trend detection

3. **Competitor Analysis Tool** (`backend/agents/tools/competitor_analysis_tool.py`)
   - Full site rendering and analysis
   - SEO benchmark comparison
   - Content gap identification
   - Opportunity scoring

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/browse` | POST | Browse URLs and extract content/data |
| `/api/serp` | POST | SERP analysis and feature extraction |
| `/api/real-time` | POST | Fetch real-time news/social data |
| `/api/competitor-analysis` | POST | Analyze competitor sites |
| `/api/analyze` | POST | Single URL SEO analysis |
| `/api/trend-research` | POST | Market trend research |
| `/api/content-hydra-analysis` | POST | AI training data potential |
| `/api/market-research` | POST | Comprehensive market research |

### Usage Example

```python
from backend.agents.tools.web_browser_tool import WebBrowserTool
from backend.agents.tools.real_time_data_tool import RealTimeDataTool

# Browse competitor sites
browser = WebBrowserTool()
browser.set_website_id("my-website")
result = browser._run("https://competitor.com", wait_time=5, extract="content")

# Fetch real-time market data  
data = RealTimeDataTool()
data.set_website_id("my-website")
news = data._run("AI SEO trends", source="news", count=5)
```

### AI Content Strategy with Web Data

Agents can now:
- Research competitor content depth and structure
- Identify trending topics in real-time
- Collect statistics and data points from authoritative sources
- Analyze competitor technical SEO
- Detect broken links and opportunities
- Fetch current market data for citations

## Continuous Monitoring System (ALWAYS REPORT TO DASHBOARD)

This system provides 24/7 automated monitoring with real-time alerts and human approval workflows.

### Database Tables (run `supabase_schema_enhanced.sql`)

| Table | Purpose |
|-------|---------|
| `realtime_alerts` | All incidents, drops, bugs, opportunities (always reported) |
| `monitoring_logs` | Monitor execution logging for metrics |
| `topic_clusters` | Auto-generated content strategy from alerts |
| `pending_fixes` | Manual fixes awaiting human approval |

### Monitoring Loops (start automatically on app startup)

| Loop | Frequency | What it monitors |
|------|-----------|------------------|
| `rank_monitor` | Every 15 min | Keyword rank drops/jumps (>3 positions), striking distance (11-20) |
| `serp_monitor` | Every 30 min | Global vs Local vs Mobile SERP differences |
| `competitor_monitor` | Every 60 min | Pricing changes, new content, blog posts |
| `tech_monitor` | Every 60 min | Broken links, speed degradation, mobile issues |
| `structure_monitor` | Every 6 hours | Orphan pages, redirect chains, duplicate titles |

### API Endpoints (Dashboard Integration)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/monitoring/{website_id}/alerts` | GET | Get alerts by filter (unread/critical/all) |
| `/api/monitoring/{website_id}/alerts/{id}/read` | POST | Mark alert as read (requires X-User-Id) |
| `/api/monitoring/{website_id}/alerts/{id}/approve` | POST | Approve alert + generate strategy |
| `/api/monitoring/{website_id}/live` | GET | SSE stream for real-time alerts |
| `/api/monitoring/{website_id}/stats` | GET | Monitor status and alert counts |
| `/api/monitoring/{website_id}/logs` | GET | Recent monitoring logs |
| `/api/monitoring/{website_id}/pending-fixes` | GET | Queue of fixes awaiting approval |
| `/api/monitoring/{website_id}/topic-clusters` | GET | Generated topic clusters |

### Human Approval Flow

Every issue requires human approval before publishing:

1. **Alert appears in dashboard** - Real-time via SSE
2. **Click "Approve"** - Sends X-User-Id header
3. **Strategy auto-generated** - Topic clusters, optimization suggestions
4. **Content created as draft** - Never auto-publishes
5. **Human reviews and publishes** - Via WordPress dashboard

### Frontend Dashboard

Access at `/monitoring`:

- **Stats bar**: Critical/High/Opportunities counts, Monitor status
- **Live feed**: Auto-updating timeline of all alerts
- **Approval queue**: Pending fixes, content, topic clusters
- **Integration status**: WordPress, GSC, PageSpeed, Slack

### WordPress Integration

- Creates drafts only (`status: "draft"`)
- Publishing requires `X-User-Id` header
- Safe fixes via API: alt text, schema, redirects
- Never auto-publishes live content

### Testing

```bash
# Run monitoring tests
python -m pytest backend/tests/test_reporting.py -v

# Verify system
python verify_monitoring.py
```

## Agentic Content Pipeline (Writesonic-Level)

The `WriterPipeline` provides a 6-step, multi-phase content generation system optimized for Google SEO + AI Search (ChatGPT/Perplexity).

### Pipeline Phases

| Phase | Steps | Purpose |
|-------|-------|---------|
| **Audience & Demand** | 1-15 | Business potential scoring, keyword mapping, intent analysis |
| **SERP & Competitors** | 16-40 | Top 10 results, content gaps, AI questions, first-party data verification |
| **Positioning & Outline** | 41-55 | Unique angle, H2 structure, internal linking plan, E-E-A-T plan, schema |
| **Multi-Step Writing** | 56-80 | Section-by-section writing with human rules, tables, FAQs, citations |
| **Multi-Expert Review** | 81-95 | 11 experts review (SEO, EEAT, AI Search, Business, Editorial, etc.) |
| **Humanizer & Gate** | 96-110 | Final humanization, WP draft export (never auto-publish) |

### Database Tables

```sql
-- content_pipeline_logs - Full audit trail (100+ steps)
-- content_expert_reviews - 11 expert scores (0-100 each)
-- content_log additions: pipeline_status, eeat_data, ai_search_score, wp_draft_id
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/writer/{website_id}/generate` | POST | Start content pipeline (topic, keyword) |
| `/api/writer/{website_id}/pipeline/{content_id}` | GET | Get all 100+ pipeline logs |
| `/api/writer/{website_id}/content` | GET | List content with pipeline status |
| `/api/writer/{website_id}/content/{content_id}/preview` | GET | Preview draft content |
| `/api/writer/{website_id}/content/{content_id}/publish` | POST | **Human-gated WP publish** |
| `/api/writer/{website_id}/content/{content_id}/approve-draft` | POST | Mark draft approved |
| `/api/writer/{website_id}/expert-reviews/{content_id}` | GET | Get expert review breakdown |

### Human-in-the-Loop Flow

1. **Generate content** -> Pipeline creates draft
2. **Dashboard shows** -> Phase progress + 11 expert scores
3. **Click "Publish"** -> Sends X-User-Id header
4. **Without X-User-Id** -> 403 blocked + alert logged
5. **With X-User-Id** -> WordPress draft published

### Usage Example

```python
import asyncio
from backend.agents.writer_agent import generate_content

result = await generate_content(
    website_id="my-website",
    topic="How to choose CRM for startups",
    primary_keyword="startup CRM comparison"
)

print(result)
# {'status': 'completed', 'content_id': 'uuid', 'pipeline_status': 'completed', 
#  'wordpress_draft_id': 123, 'final_scores': {...}}
```

### Humanization Rules

The pipeline ensures 100% human-like output:

- **No banned phrases**: "leverage", "comprehensive guide", "in conclusion", etc.
- **No em dashes**: — always replaced with comma
- **Varied sentence length**: Mix of short and long sentences
- **Contractions**: Used naturally
- **And/But/So**: Start sentences where appropriate
- **Business-first**: Business potential scoring 0-3 must be ≥2

### Expert Review Criteria

Each of 11 experts scores 0-100:

- **SEO Expert**: Keywords, meta, URL, density
- **EEAT Expert**: Author profile, reviewer, dates, schema
- **Helpful Content**: Original analysis, no fluff
- **AI Search**: Question H2s, answer-first, tables, citations
- **Brand Voice**: Tone match, example phrases
- **Business Impact**: Business relevance, CTAs
- **Editorial**: Grammar, burstiness, flow
- **Fact Check**: First-party data only
- **Internal Link**: 3 links, high-traffic pages
- **Citation**: Verified sources, schema valid
- **Humanizer**: AI pattern detection, banned phrase check
