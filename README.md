# RANKFORGE - Autonomous SEO Agent System

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/neonznikhil/seo-agent-system)

> One-click deploy uses `render.yaml` (backend API). Set the env keys from
> the table below in the Render dashboard after deploy. Run the 5 SQL
> migration files in Supabase SQL Editor before first boot.

> [!WARNING]
> ### CRITICAL SECURITY & DEPLOYMENT NOTICE: ROTATE PREVIOUSLY USED SECRETS
> **Prior to production deployment, immediately rotate any credentials used during development:**
> 1. **Supabase Keys**: Rotate your Supabase Service Role and Anon keys via the Supabase Dashboard (`Project Settings > API > JWT Settings > Generate new secret`). Verify **Row Level Security (RLS)** is enabled on all tables. The Service Role key must **NEVER** be exposed to client-side code or public variables.
> 2. **WordPress Application Passwords**: Revoke and regenerate all Application Passwords in `WP Admin > Users > Profile > Application Passwords`.
> 3. **AI & API Keys**: Rotate your NVIDIA NIM API key (`build.nvidia.com`) and search keys (Serper, Tavily).
> 4. **Git History Notice**: If any secret was committed in earlier revisions, git history preserves those values. You must treat any previously committed development keys as compromised and rotate them immediately.

## Setup (verified working order)

### 0. Requirements
- **Python 3.11** (production Docker uses `python:3.11-slim`; local dev on 3.11 recommended — 3.14 works but `crewai` is unavailable there and the direct-NIM fallback is used instead)
- **Node.js 20+** for `frontend-next`
- Supabase project (free tier works), NVIDIA NIM API key (free tier), Serper API key
- Optional: WordPress site (publishing), Redis (rate limiting), GSC service account

### 1. Backend
```bash
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # then fill SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, NVIDIA_API_KEY, SERPER_API_KEY, ...
cd backend && uvicorn main:app --reload --port 8000
# Health check: http://localhost:8000/health
```

### 2. Database (Supabase SQL Editor, in this order — all idempotent)
1. `supabase_master_complete.sql` — base tables
2. `supabase_migration_missing.sql` — blogs, agent_memory, daily_searches, analytics_data, `knowledge_base.last_used`
3. `supabase_migration_aeo.sql` — AEO/GEO + backlink queue tables, content_log AEO flags
4. `supabase_migration_vectors.sql` — pgvector backfill + `match_knowledge` / `match_brain_memory` RPCs
5. `supabase_migration_rls.sql` — least-privilege RLS (anon locked out; backend uses service_role)
6. `supabase_migration_indexation_runs.sql` — `indexation_checks`, `runs`, `brand_voice_guides`, `fact_verifications` (SEO outcomes layer)

### 3. Frontend
```bash
cd frontend-next && npm install && npm run dev -- --port 3000
# Open: http://localhost:3000
```

### 4. Environment variables (root `.env`)
| Key | Required | Purpose |
|-----|----------|---------|
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | yes | backend DB access (service_role bypasses RLS) |
| `SUPABASE_KEY` (anon) | yes | frontend public client (RLS denies writes) |
| `NVIDIA_API_KEY` | yes | LLM + embeddings (`NIM_LLM_MODEL`, `NIM_EMBED_MODEL`) |
| `SERPER_API_KEY` | yes | SERP data (blog research, AEO citation checks) |
| `TAVILY_API_KEY` | no | SERP fallback |
| `WORDPRESS_SITE_URL`, `WORDPRESS_USERNAME`, `WORDPRESS_APP_PASSWORD` | no | publishing (preview-only mode without) |
| `ENCRYPTION_KEY`, `JWT_SECRET` | yes | credential encryption + auth (unique per environment) |
| `BUDGET_THRESHOLD_USD` | no | daily spend cap, default `150.0` |
| `NEXT_PUBLIC_API_URL` | frontend | backend base URL (default `http://127.0.0.1:8000`) |

## CTO Demo Script (RANKFORGE — all commands verified)

```bash
echo "=== 1. Health check ==="
curl http://localhost:8000/health

echo "=== 2. List websites ==="
curl http://localhost:8000/api/websites

echo "=== 3. AEO overview (schema coverage + AI readiness) ==="
curl "http://localhost:8000/api/aeo?website_id=YOUR_WEBSITE_ID"

echo "=== 4. AI-search llms.txt ==="
curl http://localhost:8000/llms.txt | head -20

echo "=== 5. Keyword plan for a website (sync call) ==="
python -c "from backend.agents.crew import plan_blogs_for_website; print(plan_blogs_for_website('YOUR_WEBSITE_ID'))"
```

Or run the full 9-step live walkthrough: `python backend/scripts/demo_e2e.py`

## Testing

```bash
# Fast per-commit suite (excludes live-API tests)
python -m pytest backend/tests/ -q -m "not slow"

# Full suite including live NIM/SERP/WordPress tests (slow, ~10+ min)
python -m pytest backend/tests/ -q
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
