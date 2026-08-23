# RankForge — Complete Software Overview

## 1. What Is RankForge

RankForge is an autonomous SEO/AEO/GEO content engine. It continuously researches keywords, writes publication-ready content, audits technical SEO, prospects backlinks, monitors rankings, and pushes WordPress drafts — all gated behind a human approval queue so nothing publishes without a human click.

It is built for **real data only**: every alert, ranking, and content record is stored in Supabase. There are no mock pipelines in production paths.

---

## 2. Architecture

### Backend
- **Framework**: FastAPI (Python 3.10-3.13)
- **Entry point**: `backend/main.py`
  - Lifespan hooks start monitors and background autopilot loops
  - CORS enabled for local frontend
  - Request logging with `X-Request-ID` and `X-Process-Time`
  - Global exception handler logs to Supabase `tasks` table
  - Health endpoint checks Supabase, NVIDIA NIM, Redis, and WordPress connections

### Frontend
- **Framework**: Next.js 14 (App Router, React 18, TypeScript)
- **Styling**: Tailwind CSS + PostCSS
- **Charts**: D3.js, ReactFlow
- **Icons**: lucide-react
- **File upload**: react-dropzone
- **Standalone prototype**: `rankforge.html` (embedded CSS/JS, no framework) also served at `/` and `/dashboard`

### Database
- **Provider**: Supabase (PostgreSQL + pgvector)
- **Client**: `supabase` Python package
- **Embeddings**: 1024-dim and 1536-dim vectors with IVFFlat indexes
- **Vector functions**: `match_content`, `match_pages`, `match_knowledge`, `match_brain_memory`

### AI/LLM
- **Primary LLM**: NVIDIA NIM — `meta/llama-3.1-70b-instruct`
- **Embedding model**: NVIDIA NIM — `nv-embedqa-e5-v5`
- **Agent framework**: CrewAI 0.5.x + LangChain
- **Scheduler**: APScheduler (Asia/Kolkata timezone)

---

## 3. Backend Structure

### Core Files
| File | Role |
|------|------|
| `backend/main.py` | FastAPI app, lifespan, CORS, logging, health, `/` and `/dashboard` serving `rankforge.html` |
| `backend/config.py` | Loads env vars: `SUPABASE_URL`, `SUPABASE_KEY`, `NVIDIA_API_KEY`, WP creds, GSC/GA4 paths, Redis |
| `backend/database.py` | Supabase client singleton, NIM LLM/embedding HTTP clients, `tenacity` retry logic |

### Routers (30+)
All mounted under `/api` prefix:

| Router | Prefix | Purpose |
|--------|--------|---------|
| `websites` | `/api/websites` | Website CRUD |
| `writer` | `/api/writer` | 10-phase content pipeline |
| `monitoring` | `/api/monitoring` | Alerts, SSE live feed, approval queue |
| `autonomy` | `/api/autonomy` | Decision engine, scheduler status/goals/costs |
| `brain` | `/api/brain` | Memory recall/learn, brand brain, auto-queue |
| `approvals` | `/api/approvals` | Human-gated WordPress publish approvals |
| `gsc` | `/api/gsc` | Google Search Console data |
| `tech_seo` | `/api/tech-seo` | Technical SEO audits |
| `wordpress` | `/api/wordpress` | WP connect, drafts, posts, OAuth |
| `backlinks` | `/api/backlinks` | Backlink monitoring, prospects, outreach |
| `research` | `/api/research` | Research tasks & competitors |
| `clusters` | `/api/clusters` | Topic cluster management |
| `knowledge` | `/api/knowledge` | Knowledge base & RAG |
| `content` | `/api/content` | Content log management |
| `decay` | `/api/decay` | Content decay detection & refresh |
| `rag` | `/api/rag` | RAG query endpoints |
| `chat` | `/api/chat` | AI chat interface |
| `connectors` | `/api/connectors` | Integration status |
| `workforce` | `/api/workforce` | Agent management dashboard |
| `calendar` | `/api/calendar` | Content calendar |
| `roi` | `/api/roi` | ROI tracking |
| `seo_aeo_geo` | `/api/seo-analysis`, `/api/aeo-score`, `/api/geo-readiness` | SEO/AEO/GEO analysis |
| `memory` | `/api/memory` | Brain memory |
| `llms_txt` | `/api/llms-txt` | LLMs.txt generation |
| `settings` | `/api/settings` | Global settings |
| `setup` | `/api/setup` | Supabase bootstrap |
| `wordpress_oauth` | `/api/wordpress/oauth` | WP OAuth2 flows |
| `wordpress_connect` | `/api/wordpress` | WP connection proxy |
| `api_web_browsing` | `/api/browse`, `/api/serp`, `/api/analyze` | SERP, competitor, real-time data |

### Services (30+)
| Service | Purpose |
|---------|---------|
| `wordpress_service.py` | WP REST API client (draft, publish, posts, pages) |
| `wordpress_oauth_service.py` | OAuth2 PKCE flow with Fernet token encryption |
| `gsc_service.py` | Google Search Console API (keywords, top pages, sitemaps) |
| `ga4_service.py` | Google Analytics 4 Data API (page traffic, engagement) |
| `brain_service.py` | Memory store/recall, auto-learning from analytics, brand brain |
| `knowledge_service.py` | 11-step knowledge graph: chunking, embedding, entity extraction, freshness decay, consolidation |
| `rag_service.py` | Hybrid vector+keyword search, LLM cross-encoder reranking, citation-grounded generation |
| `crawlee_service.py` | Real web crawling (BeautifulSoup + Playwright) |
| `continuous_monitor.py` | 6 monitoring loops (rank, SERP, competitor, tech, geo, structure) |
| `reporting_service.py` | `report_problem()` — always reports to `realtime_alerts` + SSE + Slack + Email |
| `sse_service.py` | Server-Sent Events for live dashboard alerts |
| `slack_service.py` | Slack webhook alerts with severity colors |
| `email_service.py` | Resend API email alerts |
| `daily_search_service.py` | Daily GSC mining, SERP analysis, backlink checks, new page suggestions |
| `content_refresher_service.py` | Daily content refresh with human approval gate |
| `auto_publisher_service.py` | Auto-generates from `brain_auto_pages_queue` → quality gate → `blog_approvals` |
| `cluster_service.py` | Topic cluster building from GSC keyword embeddings |
| `backlink_prospect_service.py` | 4-module backlink prospecting (broken link, resource page, competitor gap, guest post) |
| `analytics_service.py` | GSC sync, content gaps, decaying content detection |
| `seo_quality_gate.py` | Deterministic SEO validation (title length, meta, keyword density, internal links, Elementor-safe HTML) |
| `approval_store.py` | Supabase-first with memory fallback for `blog_approvals` |
| `brain_backlink_service.py` | Brain-memory-backed backlink intelligence |
| `decay_detector_service.py` / `decay_diagnosis_service.py` | Content decay detection & diagnosis |
| `business_scorer_service.py` | Business potential scoring |
| `outreach_draft_service.py` | Outreach email drafting |
| `internal_link_service.py` | Internal link graph building |

---

## 4. Frontend Structure (Next.js)

### App Router Pages
| Page | Route | Purpose |
|------|-------|---------|
| `app/page.tsx` | `/` | Root redirect |
| `app/layout.tsx` | — | Root layout with Sidebar + Topbar |
| `app/dashboard/page.jsx` | `/dashboard` | Autonomous overview, analytics tabs, goals, cost tracking |
| `app/approvals/page.tsx` | `/approvals` | Human approval queue for content |
| `app/generate/page.tsx` | `/generate` | Content generation UI |
| `app/content/page.tsx` | `/content` | Content log browser |
| `app/backlinks/page.jsx` | `/backlinks` | Backlink dashboard |
| `app/tech-seo/page.tsx` | `/tech-seo` | Technical SEO audit results |
| `app/monitoring/page.tsx` | `/monitoring` | Live 24/7 monitoring feed with SSE |
| `app/brain/page.tsx` | `/brain` | Brain memory browser |
| `app/knowledge/page.jsx` | `/knowledge` | Knowledge base |
| `app/wordpress/page.tsx` | `/wordpress` | WordPress management |
| `app/research/page.tsx` | `/research` | SERP research |
| `app/clusters/page.tsx` | `/clusters` | Topic clusters |
| `app/calendar/page.tsx` | `/calendar` | Content calendar |
| `app/settings/page.tsx` | `/settings` | Settings |
| `app/connectors/page.jsx` | `/connectors` | Connection status (NVIDIA, Supabase, WP) |
| `app/rag/page.jsx` | `/rag` | RAG knowledge query lab |
| `app/workforce/page.jsx` | `/workforce` | 25+ agent management |
| `app/proposals/page.tsx` | `/proposals` | SEO proposals |
| `app/decay/page.tsx` | `/decay` | Content decay tracker |
| `app/links/page.tsx` | `/links` | Link management |
| `app/aeo/page.jsx` | `/aeo` | AEO tracking |
| `app/memory/page.tsx` | `/memory` | Agent memory |
| `app/llms-txt/page.tsx` | `/llms-txt` | LLMs.txt generator |
| `app/websites/page.tsx` | `/websites` | Website management |
| `app/setup/page.tsx` | `/setup` | Supabase setup wizard |
| `app/auth/wordpress/callback/page.tsx` | — | WP OAuth callback |

### Key Components
| Component | Purpose |
|-----------|---------|
| `Sidebar.tsx` | Navigation: Core, SEO Studio, AI Intelligence, Integrations + theme toggle |
| `Topbar.tsx` | Header bar |
| `ApprovalCard.tsx` | Approval queue item |
| `BlogPreview.tsx` | Blog preview |
| `ConnectWordPress.tsx` | WP connection form |
| `ContentCalendar.tsx` | Calendar view |
| `ROILineChart.tsx` | ROI chart (D3) |
| `StatusPieChart.tsx` | Status chart (D3) |

---

## 5. Database Schema (Supabase)

### Core Tables
| Table | Purpose |
|-------|---------|
| `websites` | Root entity — domain, CMS URL, credentials, GSC property |
| `pages` | Crawled page index with vector embeddings (1024-dim) |
| `website_knowledge` | Extracted website content with embeddings |
| `tone_profiles` | Brand tone descriptions, vocabulary, forbidden words |
| `knowledge_base` | Business facts, services, pricing, statutes with 1536-dim embeddings, freshness_score, credibility_score, validation |
| `content_log` | All generated content (draft, pending_approval, published) with pipeline_status, expert scores, faq_schema, internal_links |
| `audits` | SEO audit issues |
| `quality_checks` | Content quality validation records |
| `agent_thoughts` | Agent reasoning logs |
| `agent_feedback` | Human feedback on agent decisions |
| `tasks` | Agent task execution log |
| `technical_audits` | Technical SEO audit results |
| `backlinks` | Backlink inventory |
| `llms_txt_log` | LLMs.txt generation history |
| `critical_action_logs` | Audit trail for blocked/published actions |

### Brain & Memory Tables
| Table | Purpose |
|-------|---------|
| `brain_memory` | Vector memory (1536-dim) with types: fact, experience, failure, preference, entity, relationship, outcome |
| `brain_daily_jobs` | Daily job execution log |
| `brain_content_performance` | Post-publish performance tracking (14-day learning cycle) |
| `brain_auto_pages_queue` | Auto-suggested pages awaiting human approval |

### Agentic Tables
| Table | Purpose |
|-------|---------|
| `topic_clusters` | Pillar/cluster keyword architecture |
| `cluster_articles` | Individual cluster article opportunities |
| `serp_landscape` | SERP analysis cache |
| `backlink_prospects` | Qualified backlink opportunities with strategy, anchor suggestions |
| `backlink_monitor` | Live backlink status tracking |
| `geo_visibility_logs` | AI citation tracking (ChatGPT, Perplexity, Google AI Overview) |
| `content_decay_logs` | Content decay detection and refresh pipeline |
| `content_pipeline_logs` | 100+ step audit trail for WriterPipeline |
| `content_expert_reviews` | 11-expert review scores |
| `daily_costs` | Token/cost tracking per agent per day |
| `autonomous_settings` | Auto_publish, auto_generate, auto_refresh flags + goals |
| `realtime_alerts` | All monitoring alerts (always reported to user) |
| `monitoring_logs` | Monitor execution metrics |
| `pending_fixes` | Fixes awaiting human approval |
| `blog_approvals` | Central approval queue (Supabase or memory fallback) |

### Vector Functions & Indexes
- `match_content()` — cosine similarity on `content_log.embedding`
- `match_pages()` — cosine similarity on `pages.embedding`
- `match_knowledge()` — cosine similarity on `knowledge_base.embedding`
- `match_brain_memory()` — cosine similarity on `brain_memory.embedding`
- IVFFlat indexes on all embedding columns

---

## 6. AI Agents & Their Roles

### Pipeline Agents
| Agent | File | Role |
|-------|------|------|
| **WriterPipeline** | `backend/agents/writer_agent.py` | 10-phase, 111-step autonomous content pipeline |
| **HumanWriterAgent** | `backend/agents/human_writer.py` | Professional human-quality writer with banned phrase filtering |
| **ResearchAgent** | `backend/agents/research_agent.py` | Topic research via NIM + Crawlee SERP |
| **KeywordAgent** | `backend/agents/keyword_agent.py` | Primary/secondary keywords, difficulty, clustering |
| **OutlineAgent** | `backend/agents/outline_agent.py` | H1/H2/FAQ outline generation |
| **SEOAgent** | `backend/agents/seo_agent.py` | Meta tags, slug, keyword density, internal links |
| **ElementorAgent** | `backend/agents/elementor_agent.py` | Elementor-safe HTML conversion |
| **TechSEOAgent** | `backend/agents/tech_seo_agent.py` | Sitemap, robots.txt, schema, Core Web Vitals |
| **BacklinkAgent** | `backend/agents/backlink_agent.py` | 4-module backlink prospecting |
| **KnowledgeAgent** | `backend/agents/knowledge_agent.py` | Crawls website, extracts knowledge, builds tone profile |
| **StrategyAgent** | `backend/agents/strategy_agent.py` | Alert-driven strategy generation |
| **SupervisorAgent** | `backend/agents/supervisor_agent.py` | Full pipeline orchestrator |
| **SetupAgent** | `backend/agents/setup_agent.py` | Website onboarding (orphaned) |
| **RefreshAgent** | `backend/agents/refresh_agent.py` | Auto-refreshes decaying content |

### Autonomous Loop Agents
| Agent | File | Role |
|-------|------|------|
| **BrainAutopilotAgent** | `backend/agents/brain_autopilot_agent.py` | 6 daily jobs: search, cluster, geo check, refresh, backlink, new page |
| **BacklinkAutopilotAgent** | `backend/agents/backlink_autopilot_agent.py` | Internal link graph + backlink monitoring |
| **AutonomousLoop** | `backend/agents/autonomous_loop.py` | Hourly loop: alerts → auditor → content gen → tech check → brain update |

### CrewAI Agents
| Agent | File | Role |
|-------|------|------|
| **AuditorAgent** | `backend/agents/crew.py` | SEO/AEO/GEO auditor (proposal only) |
| **EditorAgent** | `backend/agents/crew.py` | Content strategy editor (proposes fixes) |
| **WriterAgent** | `backend/agents/crew.py` | AI-first content writer (creates pending_approval) |
| **TechSEOCrewAgent** | `backend/agents/crew.py` | Technical SEO analysis |
| **SEOBacklinkAgent** | `backend/agents/crew.py` | Backlink analysis |
| **ManagerAgent** | `backend/agents/crew.py` | Portfolio manager |

### CrewAI Tools (25+)
| Tool | Purpose |
|------|---------|
| `CrawleeTool` | Real web crawling |
| `SEOAEOGEOTool` | SEO/AEO/GEO page analysis |
| `SERPAnalyzerTool` | SERP landscape extraction |
| `ContentOptimizerTool` | Content optimization suggestions |
| `QualityGateTool` | 5-vector quality gate |
| `KnowledgeExtractorTool` | Knowledge extraction |
| `ToneAnalyzerTool` | Brand tone analysis |
| `LlmsTxtTool` | LLMs.txt generation |
| `VectorMemoryTool` | Vector memory operations |
| `ThinkAndLogTool` | Agent thought logging |
| `WebBrowserTool` | Playwright browser automation |
| `RealTimeDataTool` | News/social/trend data |
| `CompetitorAnalysisTool` | Full competitor site analysis |
| `AntiAIPenTool` | AI pattern detection/humanization |
| `GscTools` | GSC data fetching |
| `RankTools` | Rank tracking |
| `ProspectResearchTool` | Backlink prospect research |
| `OutreachTool` | Outreach email generation |
| `Humanizer` | Content humanization |

### Supporting Modules
| Module | Purpose |
|--------|---------|
| `personas.py` | CrewAI agent personas |
| `pipeline_config.py` | 10-phase pipeline config, expert names, banned phrases |
| `rules.py` | Critical action blocking, human approval requirements |
| `agent_limits.py` | Agent execution limits and rate controls |
| `scheduler.py` | APScheduler cron jobs, Asia/Kolkata timezone |

---

## 7. Key Features

### 10-Phase WriterPipeline
1. **Brain Recall** — Recalls brand brain + topic memories
2. **Audience & Demand Analysis** — Business potential scoring, intent mapping
3. **SERP & Competitor Intelligence** — Top 10 SERP, PAA, featured snippets
4. **Positioning & Outline Strategy** — Unique angle, H2/H3 structure, E-E-A-T plan
5. **Multi-Step Content Writing** — 25 steps: H1, meta, intro, 10+ H2 sections, table, FAQ, conclusion
6. **Multi-Expert Review** — 11 experts (SEO, EEAT, Helpful Content, AI Search, Brand Voice, Business Impact, Editorial, Fact Check, Internal Link, Citation, Humanizer)
7. **Humanizer Gate** — Banned phrase removal, readability, sentence variation
8. **Fact-Check Verification** — Statistical claims, date-sensitive claims, source citations
9. **Internal Link Optimization** — 3+ high-traffic page links
10. **Citation & Reference Audit** — Verified sources, schema validation
11. **Final Quality Gate** — SEO ≥85, validation ≥0.80, knowledge grounding ≥0.75
12. **Brain Learn** — Post-publish 14-day learning cycle

### Continuous Monitoring
6 always-running loops:
- **rank_monitor** (every 15 min) — Keyword rank drops/jumps
- **serp_monitor** (every 30 min) — Global/local/mobile SERP differences
- **competitor_monitor** (every 60 min) — Pricing changes, new content
- **tech_monitor** (every 60 min) — Broken links, speed degradation, mobile issues
- **geo_monitor** (every 30 min) — Local SEO opportunities, NAP issues
- **structure_monitor** (every 6 hours) — Orphan pages, redirect chains, duplicate titles

### Autonomous Decision Engine
- Empirical trigger evaluation before each job
- Goal-driven keyword selection
- Multi-vector quality gate
- Self-healing retries with exponential backoff
- Token/cost tracking per agent per day

### Knowledge Graph & RAG
- Heading-aware chunking (3200 chars, 400 overlap)
- Batch embeddings via NVIDIA NIM
- Entity extraction (people, orgs, locations, laws, services, keywords)
- Freshness decay: `exp(-days/90) * credibility`
- Auto-consolidation of duplicates (cosine similarity >0.92)
- Hybrid search: vector (60%) + keyword (10%) + freshness (20%) + credibility (10%) + validation (10%)
- LLM cross-encoder reranking
- Citation-grounded generation with numbered citations [1][2]

### Human-in-the-Loop Approval
- All WordPress write operations go through `/api/approvals`
- `X-User-Id` header required for approve/read/publish
- Critical action logging to `critical_action_logs`
- Blog approvals: Supabase-first with memory fallback
- Monitoring alerts require human approval before any auto-fix executes

---

## 8. Integrations

| Integration | Service File | Details |
|-------------|-------------|---------|
| **WordPress** | `wordpress_service.py`, `wordpress_oauth_service.py` | REST API (Basic Auth + Application Passwords), OAuth2 PKCE with Fernet token encryption. Drafts only; publish requires human approval. |
| **Google Search Console** | `gsc_service.py` | Service Account auth, keyword performance, top pages, sitemaps, crawl errors |
| **Google Analytics 4** | `ga4_service.py` | Service Account auth, page traffic, content performance, user engagement |
| **Ahrefs** | `backlink_prospect_service.py` | Domain Rating lookup via API v2 |
| **Semrush/Moz** | `backlink_prospect_service.py` | Domain Authority fallback |
| **Slack** | `slack_service.py` | Webhook alerts with severity colors, action buttons |
| **Email (Resend)** | `email_service.py` | Critical/high severity email alerts |
| **NVIDIA NIM** | `database.py` | Llama 3.1/3.3 Nemotron LLM + nv-embedqa-e5-v5 embeddings |
| **Crawlee** | `crawlee_service.py` | Playwright + BeautifulSoup web crawling |
| **Redis** | `config.py`, `wordpress_oauth_service.py` | Optional queue locks, OAuth state storage |
| **Tavily/Serper** | `backlink_agent.py`, `daily_search_service.py` | SERP/search API fallbacks |

---

## 9. Technology Stack

| Layer | Technology |
|-------|-----------|
| **Backend Framework** | FastAPI (Python) |
| **AI/LLM** | NVIDIA NIM (Llama 3.1/3.3 Nemotron, nv-embedqa-e5-v5) |
| **Agent Framework** | CrewAI 0.5.x + LangChain |
| **Database** | Supabase (PostgreSQL + pgvector) |
| **Task Scheduling** | APScheduler (AsyncIOScheduler, Asia/Kolkata timezone) |
| **Web Crawling** | Crawlee (PlaywrightCrawler + BeautifulSoupCrawler) |
| **HTTP Client** | httpx, aiohttp, requests |
| **Frontend** | Next.js 14 (App Router), React 18, TypeScript |
| **Frontend Styling** | Tailwind CSS 3, PostCSS |
| **Charts** | D3.js, ReactFlow |
| **Icons** | lucide-react |
| **File Upload** | react-dropzone |
| **Auth** | WordPress OAuth2 PKCE + Application Passwords |
| **Encryption** | cryptography (Fernet for WP OAuth tokens) |
| **Email** | Resend API |
| **Real-time** | Server-Sent Events (SSE) |
| **Testing** | pytest, pytest-asyncio |
| **Deployment** | Docker Compose (backend + frontend + redis) or lightweight standalone |

---

## 10. Data Flow

```
User Action / Scheduled Job
         │
         ▼
┌─────────────────┐
│   FastAPI App   │
│   (main.py)     │
│                 │
│  ┌────────────┐ │
│  │  Routers   │ │ ←── 30+ routers
│  └─────┬──────┘ │
│        │        │
│  ┌─────▼──────┐ │
│  │  Services  │ │ ←── 30+ services
│  └─────┬──────┘ │
│        │        │
│  ┌─────▼──────┐ │
│  │   Agents   │ │ ←── 25+ agents + 25+ tools
│  └─────┬──────┘ │
│        │        │
│  ┌─────▼──────┐ │
│  │ Supabase   │ │ ←── PostgreSQL + pgvector (40+ tables)
│  └────────────┘ │
└─────────────────┘
         │
    ┌────┴────┬──────────┬──────────┐
    ▼         ▼          ▼          ▼
 WordPress  GSC/GA4   NVIDIA NIM  Slack/Email
```

### Content Generation Flow
1. Scheduler triggers `job_auto_new_page`
2. `AutonomousDecisionEngine.should_run()` evaluates triggers
3. `WriterPipeline.generate()` runs 10 phases
4. Each phase logs to `content_pipeline_logs`
5. Final content stored in `content_log` with `pipeline_status='completed'`
6. `blog_approvals` row created (status=pending)
7. Dashboard shows Approvals queue
8. Human clicks Approve → `X-User-Id` header sent
9. `approvals.py` calls `WordPressService.create_draft()` → `publish_post()`
10. `critical_action_logs` records the publish action

### Monitoring Flow
1. `rank_monitor_loop()` runs every 15 minutes
2. Fetches GSC keywords, checks SERP positions
3. On rank drop/jump → `report_problem()` creates `realtime_alerts` row
4. `push_sse_alert()` pushes to connected dashboard clients
5. `send_slack_alert()` + `send_email_alert()` fire for critical/high
6. Dashboard auto-updates via SSE
7. Human clicks Approve → `StrategyAgent.handle_alert()` generates topic clusters
8. Content queued for generation

### Brain Learning Flow
1. `job_brain_learn` at 10:00 IST
2. `BrainService.auto_learn_from_analytics()` fetches top-performing content + human rejections
3. Patterns codified as `brain_memory` rows
4. Mirrored to `knowledge_base` for RAG grounding
5. Next content generation recalls these memories via `brain.recall()`

---

## 11. How the Autonomous System Works

### Phase 1: Bootstrap & Startup
1. FastAPI app starts, validates env vars
2. APScheduler initialized in **Asia/Kolkata timezone**
3. `BrainAutopilotAgent.run_daily_autopilot()` starts
4. `BacklinkAutopilotAgent.run_backlink_daily_jobs()` starts
5. All 6 monitoring loops start as background tasks

### Phase 2: Daily Scheduled Cadence
| Time (IST) | Job | Agent | Purpose |
|------------|-----|-------|---------|
| 08:30 | `business_website_watch` | KnowledgeAgent | Crawls sitemap for new/changed pages |
| 09:00 | `daily_search` | ResearchAgent | SERP trends + competitor gaps |
| 09:30 | `knowledge_sync` | KnowledgeAgent | Freshness decay + statute sync |
| 10:00 | `brain_learn` | BrainAutopilotAgent | Analyzes analytics + human rejections → memory rules |
| 10:30 | `content_refresh` | SupervisorAgent | Refreshes decaying articles |
| 11:00 | `auto_new_page` | WriterPipeline | Goal-driven article generation + quality gate |
| 11:30 | `backlink_prospecting` | BacklinkAgent | 4-module backlink qualification |
| 12:00 | `seo_report_aeo` | AEOAgent | LLM citation tracking + schema injection |

### Phase 3: Decision Engine
Before each job runs, `AutonomousDecisionEngine.should_run()` evaluates:
- Knowledge base freshness (< 0.70 → run daily_search)
- Stale records count (< 0.40 → run knowledge_sync)
- Analytics activity (records > 0 → run brain_learn)
- Decaying articles detected → run content_refresh
- Target keyword available + knowledge hits → run auto_new_page
- Backlink queue depth < 5 → run backlink_prospecting

### Phase 4: Quality Gates
Every generated piece passes through:
1. **SEO Score ≥ 85**
2. **Validation Score ≥ 0.80**
3. **Hallucination Check** — NIM LLM verifies no unsupported claims
4. **Plagiarism Check** — Unique content verification
5. **11-Expert Review** — Each scores 0-100, minimum 70 required

### Phase 5: Human Approval Gate
- All content staged as `pending_approval` in `blog_approvals`
- Dashboard shows Approvals queue
- Human clicks Approve → sends `X-User-Id` header
- Backend verifies header via `require_human_for_request()`
- Only then does `WordPressService.publish_post()` execute
- Every publish logged to `critical_action_logs`

### Phase 6: Continuous Monitoring
- 6 monitoring loops run forever in background
- Issues reported via `report_problem()` → `realtime_alerts` + SSE + Slack + Email
- Dashboard subscribes to SSE endpoint `/api/monitoring/{website_id}/live`
- Human can approve fixes directly from alert cards

---

## 12. Safety Mechanisms

1. **No auto-publish without human approval** — WordPress `publish` only via `approvals.py` with `X-User-Id`
2. **Human gate middleware** — `require_human()` decorator + `human_approval_required()` dependency
3. **Critical action logging** — Every blocked/published action in `critical_action_logs`
4. **Quality gates** — 5-vector autonomous gate + 11-expert review
5. **Anti-hallucination** — Knowledge-grounded RAG + LLM verification prompts
6. **Local retry queue** — Failed jobs persisted for exponential backoff
7. **Graceful degradation** — Memory fallback for approvals if Supabase table missing

---

## 13. Current Status

### What Works
- Backend is fully structured with 30+ routers and 30+ services
- 25+ AI agents wired into the pipeline
- Frontend Next.js app with 25+ pages
- Supabase schema with 40+ tables
- All API routes are registered and connected
- `rankforge.html` standalone prototype also available

### Known Gaps
- Some orphaned agents (`SetupAgent`, `crew_manager`) not wired into routers
- Frontend-backend API mismatches were fixed in recent commits
- Full end-to-end testing not yet completed
- Backend requires Supabase credentials and NVIDIA API key to run

---

## 14. File Structure

```
seo-agent-system/
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Environment config
│   ├── database.py                # Supabase + NIM clients
│   ├── requirements.txt           # Python dependencies
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── writer_agent.py        # 10-phase WriterPipeline
│   │   ├── human_writer.py        # Human-quality writer
│   │   ├── research_agent.py      # Topic research
│   │   ├── keyword_agent.py       # Keyword extraction
│   │   ├── outline_agent.py       # Outline generation
│   │   ├── seo_agent.py           # SEO metadata
│   │   ├── elementor_agent.py     # HTML cleaning
│   │   ├── wordpress_publisher_agent.py
│   │   ├── tech_seo_agent.py      # Technical SEO
│   │   ├── backlink_agent.py      # Backlink analysis
│   │   ├── knowledge_agent.py     # Knowledge extraction
│   │   ├── refresh_agent.py       # Content refresh
│   │   ├── strategy_agent.py      # Alert strategy
│   │   ├── supervisor_agent.py    # Pipeline orchestrator
│   │   ├── setup_agent.py         # Website onboarding
│   │   ├── brain_autopilot_agent.py
│   │   ├── backlink_autopilot_agent.py
│   │   ├── autonomous_loop.py
│   │   ├── crew.py                # CrewAI agents
│   │   ├── crew_manager.py        # Crew manager functions
│   │   ├── scheduler.py           # APScheduler cron jobs
│   │   ├── agent_limits.py        # Rate controls
│   │   ├── rules.py               # Safety rules
│   │   ├── personas.py            # CrewAI personas
│   │   ├── pipeline_config.py     # Pipeline config
│   │   └── tools/
│   │       ├── crawlee_tool.py
│   │       ├── seo_aeo_geo_tool.py
│   │       ├── serp_analyzer_tool.py
│   │       ├── content_optimizer_tool.py
│   │       ├── quality_gate_tool.py
│   │       ├── knowledge_extractor_tool.py
│   │       ├── tone_analyzer_tool.py
│   │       ├── llms_txt_tool.py
│   │       ├── vector_memory_tool.py
│   │       ├── think_and_log_tool.py
│   │       ├── web_browser_tool.py
│   │       ├── competitor_analysis_tool.py
│   │       ├── anti_ai_pen_tool.py
│   │       ├── gsc_tools.py
│   │       ├── rank_tools.py
│   │       ├── cms_tools.py
│   │       ├── outreach_tool.py
│   │       ├── prospect_research_tool.py
│   │       ├── humanizer.py
│   │       └── ...
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── websites.py
│   │   ├── writer.py
│   │   ├── monitoring.py
│   │   ├── brain.py
│   │   ├── approvals.py
│   │   ├── autonomy.py
│   │   ├── gsc.py
│   │   ├── tech_seo.py
│   │   ├── backlinks.py
│   │   ├── research.py
│   │   ├── clusters.py
│   │   ├── knowledge.py
│   │   ├── content.py
│   │   ├── decay.py
│   │   ├── rag.py
│   │   ├── chat.py
│   │   ├── connectors.py
│   │   ├── workforce.py
│   │   ├── calendar.py
│   │   ├── roi.py
│   │   ├── seo_aeo_geo.py
│   │   ├── memory.py
│   │   ├── llms_txt.py
│   │   ├── settings.py
│   │   ├── setup.py
│   │   ├── wordpress.py
│   │   ├── wordpress_oauth.py
│   │   ├── wordpress_connect.py
│   │   └── proposals.py
│   ├── services/
│   │   ├── wordpress_service.py
│   │   ├── wordpress_oauth_service.py
│   │   ├── gsc_service.py
│   │   ├── ga4_service.py
│   │   ├── brain_service.py
│   │   ├── knowledge_service.py
│   │   ├── rag_service.py
│   │   ├── crawlee_service.py
│   │   ├── continuous_monitor.py
│   │   ├── reporting_service.py
│   │   ├── sse_service.py
│   │   ├── slack_service.py
│   │   ├── email_service.py
│   │   ├── daily_search_service.py
│   │   ├── content_refresher_service.py
│   │   ├── auto_publisher_service.py
│   │   ├── cluster_service.py
│   │   ├── backlink_prospect_service.py
│   │   ├── analytics_service.py
│   │   ├── seo_quality_gate.py
│   │   ├── approval_store.py
│   │   ├── brain_backlink_service.py
│   │   ├── decay_detector_service.py
│   │   ├── decay_diagnosis_service.py
│   │   ├── business_scorer_service.py
│   │   ├── outreach_draft_service.py
│   │   ├── internal_link_service.py
│   │   └── monitors/
│   │       ├── rank_monitor.py
│   │       ├── serp_monitor.py
│   │       ├── competitor_monitor.py
│   │       ├── tech_monitor.py
│   │       ├── geo_monitor.py
│   │       └── structure_monitor.py
│   └── schemas/
│       ├── supabase_schema.sql
│       ├── supabase_schema_v2.sql
│       ├── supabase_schema_brain.sql
│       ├── supabase_schema_agents.sql
│       └── fix_missing_columns.sql
├── frontend-next/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── dashboard/page.jsx
│   │   ├── approvals/page.tsx
│   │   ├── generate/page.tsx
│   │   ├── content/page.tsx
│   │   ├── backlinks/page.jsx
│   │   ├── tech-seo/page.tsx
│   │   ├── monitoring/page.tsx
│   │   ├── brain/page.tsx
│   │   ├── knowledge/page.jsx
│   │   ├── wordpress/page.tsx
│   │   ├── research/page.tsx
│   │   ├── clusters/page.tsx
│   │   ├── calendar/page.tsx
│   │   ├── settings/page.tsx
│   │   ├── connectors/page.jsx
│   │   ├── rag/page.jsx
│   │   ├── workforce/page.jsx
│   │   ├── proposals/page.tsx
│   │   ├── decay/page.tsx
│   │   ├── links/page.tsx
│   │   ├── aeo/page.jsx
│   │   ├── memory/page.tsx
│   │   ├── llms-txt/page.tsx
│   │   ├── websites/page.tsx
│   │   ├── setup/page.tsx
│   │   └── auth/wordpress/callback/page.tsx
│   ├── components/
│   │   ├── Sidebar.tsx
│   │   ├── Topbar.tsx
│   │   ├── ApprovalCard.tsx
│   │   ├── BlogPreview.tsx
│   │   ├── ConnectWordPress.tsx
│   │   ├── ContentCalendar.tsx
│   │   ├── KeywordBadge.tsx
│   │   ├── ROILineChart.tsx
│   │   └── StatusPieChart.tsx
│   ├── lib/
│   │   ├── api.ts
│   │   └── website.ts
│   ├── package.json
│   └── next.config.js
├── rankforge.html                 # Standalone HTML prototype
├── docker-compose.yml
├── backend/Dockerfile
├── frontend-next/Dockerfile
└── start-servers.py
```

---

## 15. Environment Variables

### Backend (`backend/.env`)
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
NVIDIA_API_KEY=your-nvidia-api-key
WP_SITE_URL=https://your-site.com
WP_OAUTH_CLIENT_ID=your-client-id
WP_OAUTH_CLIENT_SECRET=your-client-secret
WP_OAUTH_AUTHORIZE_URL=https://your-site.com/oauth/authorize
WP_OAUTH_TOKEN_URL=https://your-site.com/oauth/token
TOKEN_ENCRYPTION_KEY=your-fernet-key
GSC_CREDENTIALS_PATH=path/to/gsc-credentials.json
GA4_CREDENTIALS_PATH=path/to/ga4-credentials.json
REDIS_URL=redis://localhost:6379/0
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
RESEND_API_KEY=your-resend-key
```

### Frontend (`frontend-next/.env.local`)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_KEY=your-anon-key
```

---

## 16. Deployment

### Docker Compose
- `backend/Dockerfile` — Python 3.11-slim, uvicorn
- `frontend-next/Dockerfile` — Node 20-alpine, next build
- `docker-compose.yml` — backend + frontend + redis
- `start-backend.bat` / `start-frontend.bat` — Windows quick-start scripts

### Standalone
```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend-next
npm install
npm run dev
```

---

## 17. Current State

### Working
- Backend fully structured with 30+ routers and 30+ services
- 25+ AI agents wired into pipeline
- Frontend Next.js app with 25+ pages
- Supabase schema with 40+ tables
- All API routes registered and connected
- `rankforge.html` standalone prototype served at `/`

### Needs Attention
- Some orphaned agents (`SetupAgent`, `crew_manager`) not wired into routers
- Full end-to-end testing not yet completed
- Backend requires Supabase credentials and NVIDIA API key to run
- PowerShell execution policy may block npm scripts on Windows
