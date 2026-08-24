# RankForge — Complete System Overview (100% Design Vision)

## 1. System Mission

RankForge is a **fully autonomous, self-healing, self-improving SEO / AEO / GEO content engine**. After a user connects their website URL and WordPress credentials once, the system runs 24/7 without further manual triggers. It continuously researches keywords, writes publication-ready content, audits technical SEO, prospects backlinks, monitors rankings, and pushes WordPress drafts — all gated behind a human approval queue so nothing publishes without a human click.

---

## 2. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Next.js 14 (App Router) + TypeScript + Tailwind CSS | Dashboard, approvals, connectors, settings |
| **Backend** | FastAPI (Python 3.10+) | REST API, SSE, WebSocket, lifespan hooks |
| **Database** | Supabase (PostgreSQL + pgvector) | All persistent data + vector embeddings |
| **LLM** | NVIDIA NIM — `meta/llama-3.1-70b-instruct` | Content generation, strategy, decisions |
| **Embeddings** | NVIDIA NIM — `nv-embedqa-e5-v5` (1024-dim) | Knowledge recall, brain memory, similarity |
| **Scheduler** | APScheduler (Asia/Kolkata timezone) | 20+ cron jobs for autonomous routines |
| **Crawling** | Crawlee (Playwright + BeautifulSoup) | Competitor SERP crawling, content extraction |
| **Auth** | WordPress OAuth2 PKCE + Application Passwords | WordPress integration only |
| **Monitoring** | 6 always-running async loops | Rank, SERP, competitor, tech, GEO, structure |

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          FRONTEND (Next.js 14)                      │
│  / → Dashboard  /writer → Pipeline  /approvals → Queue             │
│  /connectors → Integrations  /settings → Config  /backlinks → Links │
│  SSE Live Updates ←───────────────────────────────┐                │
└──────────────────────────────────────────────────┼────────────────┘
                                                   │ HTTP/REST + SSE
┌──────────────────────────────────────────────────▼────────────────┐
│                      BACKEND (FastAPI)                             │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │
│  │   30+       │  │   30+        │  │     25+ AGENTS          │  │
│  │  ROUTERS    │→ │  SERVICES    │→ │  + 25+ TOOLS           │  │
│  └─────────────┘  └──────────────┘  └─────────────────────────┘  │
│         ↑                 ↑                      ↑                │
│         └─────── LIFESPAN / SCHEDULER / AUTONOMOUS LOOP ─────────┘  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    MIDDLEWARE STACK                          │  │
│  │  CORS | Request Logging | X-Request-ID | X-Process-Time     │  │
│  │  Human Gate (publish requires X-User-Id) | RBAC (3 roles)   │  │
│  └─────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
         │                    │                    │
    ┌────▼────┐         ┌─────▼─────┐       ┌─────▼─────┐
    │ Supabase│         │  NVIDIA   │       │ External  │
    │(Postgres│         │   NIM     │       │  APIs     │
    │+pgvector)│         │  LLM/Emb  │       │(WP,GSC,   │
    │         │         │           │       │ GA4, etc) │
    └─────────┘         └───────────┘       └───────────┘
```

---

## 4. User Journey: From Zero to Autonomous

### Step 1: Connect Website (One-Time Setup)
**Route**: `/connectors`

The user enters:
1. **Website URL** — e.g., `https://mybusiness.com`
2. **WordPress Credentials** — either Application Password or OAuth2 PKCE
3. **Google Credentials** — GSC + GA4 OAuth (optional but recommended)
4. **Slack Webhook** — for daily briefs (optional)

Behind the scenes:
- `ConnectorsService` validates all connections
- WordPress app passwords are **Fernet-encrypted** before storage in `wordpress_connections`
- OAuth tokens are encrypted in `wordpress_oauth_tokens`
- A `websites` row is created with `website_id`
- KnowledgeAgent immediately crawls the sitemap and populates `knowledge_base`
- Continuous monitors start: rank_monitor, serp_monitor, competitor_monitor, tech_monitor, geo_monitor, structure_monitor

### Step 2: Set Goals (Optional but Recommended)
**Route**: `/settings` → Autonomous Goals tab

User sets:
- `target_articles_per_week`: 5
- `target_traffic_growth`: 15.0 (%)
- `focus_keywords`: ["Houston car accident lawyer", "Texas truck crash claims", ...]

These are stored in `autonomous_settings.goals` and drive the `AutonomousDecisionEngine`.

### Step 3: Dashboard (Autonomous Operation)
**Route**: `/`

The dashboard shows:
- **Autonomous Health Score** (0-100) from health checks
- **Today's Jobs**: due / completed / failed
- **Approval Queue**: pending human approvals
- **Recent Alerts**: unread realtime alerts
- **Agent Status**: idle / running / failed for each agent
- **Cost Tracking**: today's token spend vs budget
- **Content Pipeline**: active generation phases

Everything updates live via **SSE** from `backend/services/event_bus.py`.

### Step 4: Human Approval (The Only Manual Step)
**Route**: `/approvals`

When WriterPipeline generates content:
1. Article is saved to `blog_approvals` with `status=pending`
2. Dashboard shows it in the Approval Queue
3. Human clicks **Approve** or **Reject**
4. `X-User-Id` header is validated (no default "admin" fallback)
5. On approve: `WordPressService.publish_post()` pushes to WordPress
6. `critical_action_logs` records the action with real user identity

---

## 5. The 7 Core Agents & Their Roles

### 5.1 KnowledgeAgent (The Memory Builder)
**Schedule**: Daily at 08:30 and 09:30 IST

**What it does**:
1. Crawls the user's website sitemap
2. Parses HTML pages, extracts text content
3. Splits into 3200-char chunks with 400-char overlap
4. Generates 1536-dim embeddings via NVIDIA NIM
5. Extracts entities: people, orgs, locations, laws, services, keywords
6. Stores in `knowledge_base` with `freshness_score` and `credibility_score`
7. Applies freshness decay: `exp(-days/90) * credibility_score`
8. Auto-consolidates duplicates (cosine similarity > 0.92)

**Memory lifecycle**: Acts as the system's long-term memory. Every other agent queries this before acting.

### 5.2 ResearchAgent (The Market Scout)
**Schedule**: Daily at 09:00 IST

**What it does**:
1. Queries `focus_keywords` from `autonomous_settings.goals`
2. Calls Serper.dev for live SERP landscape
3. Extracts top 10 competitor outlines, PAA questions, featured snippets
4. Identifies content gaps (what's missing from top results)
5. Persists findings to `research` table and `brain_memory`
6. Outputs: `keyword_opportunities`, `serp_landscape`, `daily_searches`

**Decision trigger**: `AutonomousDecisionEngine.should_run("daily_search")` checks knowledge freshness < 0.70 or < 5 KB records.

### 5.3 WriterPipeline (The Content Engine)
**Schedule**: Daily at 11:00 IST (or when `auto_generate=True` and queue < threshold)

**The 12-Phase, ~111-Step Pipeline**:

| Phase | Steps | What Happens |
|-------|-------|-------------|
| 1. brain_recall | 1 | Recall brand facts, preferences, failures via vector similarity |
| 2. audience_demand_analysis | 10 | Business potential, intent mapping, CPC trends |
| 3. serp_competitor_intelligence | 12 | Top 10 SERP, PAA, featured snippets, competitor structure |
| 4. positioning_outline_strategy | 10 | Unique angle, H2/H3 structure, E-E-A-T plan |
| 5. multi_step_content_writing | 25 | H1, meta, intro, 10+ H2 sections, table, FAQ, conclusion |
| 6. multi_expert_review | 20 | 11 experts review content (see below) |
| 7. humanizer_gate | 15 | Banned phrase removal, readability, sentence variation |
| 8. fact_check_verification | 8 | Statistical claims, date-sensitive claims, source citations |
| 9. internal_link_optimization | 5 | 3+ high-traffic page links |
| 10. citation_reference_audit | 3 | Verified sources, schema validation |
| 11. final_quality_gate | 3 | SEO ≥85, validation ≥0.80, knowledge grounding ≥0.75 |
| 12. brain_learn | 1 | Post-generation memory persistence |

**11 Expert Reviewers** (Phase 6):
1. **SEO Expert** — keyword density, meta tags, schema
2. **EEAT Expert** — author credentials, citations, trust signals
3. **Helpful Content Expert** — user intent coverage, depth
4. **AI Search Expert** — AEO/GEO optimization (citations, entities, FAQ schema)
5. **Brand Voice Expert** — tone consistency with `preference` memories
6. **Business Impact Expert** — conversion potential, CTAs
7. **Editorial Expert** — grammar, flow, readability
8. **Fact Check Expert** — claims verification against knowledge base
9. **Internal Link Expert** — link relevance, anchor text
10. **Citation Expert** — source quality, attribution
11. **Humanizer Expert** — AI pattern detection, readability

**Quality Gates**:
- No duplicate titles (checked against `content_log`)
- Anti-hallucination: Knowledge Base verification before generation
- LLM hallucination check after generation
- Anti-plagiarism: uniqueness score computed
- AI pattern detection: banned phrase removal

**Output**: `blog_approvals` row (status=pending) + `blogs` mirror + WordPress draft via `WordPressService.draft_post()`.

### 5.4 TechSEOAgent (The Health Checker)
**Schedule**: Daily at 12:00 IST

**What it does**:
1. Crawls website for Core Web Vitals (LCP, FID, CLS)
2. Checks XML sitemap validity and coverage
3. Detects redirect chains (301 → 302 → 301)
4. Identifies orphan pages (no internal links)
5. Validates indexability (noindex tags, robots.txt)
6. Checks mobile usability
7. Generates `pending_fixes` proposals for human approval
8. Outputs: `technical_audits` table + `realtime_alerts` for critical issues

### 5.5 BacklinkAgent (The Authority Builder)
**Schedule**: Daily at 11:30 IST

**4-Module Live Prospecting**:

| Module | Method | What It Does |
|--------|--------|--------------|
| **Broken Link** | Crawls competitor backlinks, finds 404s | Suggests "hey, you linked to a dead page, link to mine instead" |
| **Resource Page** | Finds "best resources" pages in niche | Suggests addition to curated lists |
| **Competitor Gap** | Analyzes competitor backlink profiles | Finds sites linking to competitors but not user |
| **Guest Post** | Identifies accepting blogs in niche | Outreach pitch generation |

**Output**: `backlink_opportunities` with `anchor_text`, `strategy`, `contact_email`, `priority_score`.

### 5.6 StrategyAgent (The Problem Solver)
**Trigger**: Alert-driven (rank drop, budget exceeded, agent degradation, competitor win)

**What it does**:
1. Receives `realtime_alerts` from autonomous loop
2. Classifies alert type
3. Generates remediation strategy:
   - **Rank drop**: Topic cluster expansion + on-page optimization suggestions
   - **Competitor win**: Gap keyword identification + content brief
   - **Tech issue**: Pending fix proposal with priority
   - **Agent degradation**: Diagnoses root cause, queues parameter override
4. If agent fails ≥2 times: generates **alternative execution path** (fallback connectors, reduced batch sizes, segmented execution)
5. Writes strategy to `brain_memory` and `realtime_alerts`

### 5.7 SupervisorAgent (The Orchestrator)
**Schedule**: Daily at 10:00 IST (14-day outcome synthesis)

**What it does**:
1. Fetches top-performing content + human rejections from last 14 days
2. Analyzes patterns: what content ranks, what gets approved, what gets rejected
3. Codifies patterns as **preference rules** in `brain_memory`
4. Updates `autonomous_settings.success_rate` based on empirical outcomes
5. Adjusts `trigger_weights` in `autonomous_settings` if certain agents are over/under-performing

**The full pipeline** it can orchestrate:
```
Research → Keyword → Outline → Writer → SEO → Elementor → WordPress → Backlinks
```

---

## 6. Autonomous Operation: The Complete Flow

### 6.1 The Autonomous Decision Engine
**File**: `backend/agents/autonomous_decision_engine.py`

This is the **brain of self-triggering behavior**. Before every cron job fires, it evaluates empirical conditions:

```python
# Example: should_run("daily_search")
if knowledge_freshness < 0.70 or kb_record_count < 5:
    return {"should_run": True, "reason": "knowledge stale"}
else:
    return {"should_run": False, "reason": "knowledge fresh"}

# Example: should_run("auto_new_page")
if target_keyword_available and knowledge_grounding_hits > 0:
    return {"should_run": True, "priority": "high"}
else:
    return {"should_run": False, "reason": "no targets"}

# Example: should_run("backlink_prospecting")
if pending_opportunities < 5:
    return {"should_run": True}
else:
    return {"should_run": False, "reason": "queue full"}
```

**Key methods**:
- `should_run(job_name)` — Empirical trigger evaluation
- `get_next_target_keyword()` — Selects from `focus_keywords` not yet published
- `check_quality_gate()` — 5-vector gate before publish
- `track_cost()` — Records token usage to `daily_costs`
- `learn_from_result()` — Updates `brain_memory` and `success_rate`
- `queue_job_for_retry()` — Local JSON fallback for Supabase failures

### 6.2 The Autonomous Loop (5-Minute Cycle)
**File**: `backend/agents/autonomous_loop.py`

```
Every 5 minutes:
  1. Query all websites
  2. For each website:
     a. Check realtime_alerts WHERE status = "unread"
     b. For each alert → StrategyAgent.handle_alert()
     c. Check autonomous_settings.auto_generate
        - If TRUE and pipeline queue < threshold → queue content
     d. Check autonomous_settings.auto_refresh
        - If TRUE and content age > threshold → queue refresh
     e. Check autonomous_settings.auto_publish
        - If TRUE and approval score > threshold → auto-publish
        - Else → queue for human approval
  3. Sleep 300s
```

### 6.3 The Scheduler (Cron Authority)
**File**: `backend/agents/scheduler.py`

**20+ Cron Jobs** (Asia/Kolkata timezone):

| Time | Job | Agent |
|------|-----|-------|
| 03:00 IST | Knowledge Evolution | KnowledgeEvolutionService |
| 08:00 IST | Slack Morning Brief | slack_intelligence_service |
| 08:30 IST | Business Website Watch | KnowledgeAgent |
| 09:00 IST | Daily Search | ResearchAgent |
| 09:30 IST | Knowledge Sync | KnowledgeAgent |
| 10:00 IST | Brain Learn | SupervisorAgent |
| 10:30 IST | Content Refresh | RefreshAgent |
| 11:00 IST | Auto New Page | WriterPipeline |
| 11:30 IST | Backlink Prospecting | BacklinkAgent |
| 12:00 IST | Tech SEO Audit | TechSEOAgent |
| 20:00 IST | Slack Evening Summary | slack_intelligence_service |
| Mon 07:00 | Opportunity Scout | OpportunityScoutAgent |
| Mon 10:00 | Asset Engineer | AssetEngineerAgent |
| Thu 09:00 | Acquisition Monitor | AcquisitionMonitorAgent |
| Sun 01:00 | Niche Harvest | RankingSignalHarvester |
| Sun 03:00 | Self Training | SelfTrainingService |
| Sun 21:00 | Authority Calibration | AuthorityCalibrationAgent |
| Every 5 min | Reactive Alerts | autonomous_loop |
| Every 10 min | Stuck Content Cleanup | scheduler |
| Every 6h | SERP Volatility | SerpVolatilityService |
| Daily 23:30 | Budget Manager | autonomous_loop |
| Fri 23:00 | Weekly Self Audit | autonomous_loop |
| 1st of month 06:00 | Monthly Goals | autonomous_loop |

**Startup Catch-up**: `run_pending_daily_jobs()` runs any missed daily jobs on startup using `brain_daily_jobs` records to prevent double execution.

---

## 7. Self-Learning Brain Memory
**File**: `backend/services/brain_service.py`

### 7 Memory Types

| Type | Purpose | Example |
|------|---------|---------|
| `fact` | Verified knowledge | "Tech SEO Health Score: 88/100" |
| `experience` | Learned patterns | "Mined 5 trends for keyword X" |
| `failure` | Error contexts | "NIM rate limit hit, backoff 5 min" |
| `preference` | User/system preferences | "Tone: professional, banned phrases: [...]" |
| `entity` | Named entities | People, orgs, locations, laws, services, keywords |
| `relationship` | Knowledge graph edges | "Houston Lawyer → practices in → Texas" |
| `outcome` | Post-publish performance | "Article X: 2.3K views, 5% CTR, ranked #3 in 14 days" |

### Memory Architecture
- **1536-dim vector embeddings** via NVIDIA NIM
- **Hybrid recall**: vector similarity (60%) + keyword (10%) + freshness (20%) + credibility (10%) + validation (10%)
- **LLM cross-encoder reranking** for best results
- **Adaptive dimension recovery** for legacy embeddings
- **Usage counters**: `times_used`, `times_successful` for preference weighting

### 14-Day Outcome Learning
Every day at 10:00 IST, `SupervisorAgent`:
1. Fetches top-performing content + human rejections from last 14 days
2. Analyzes patterns: what ranks, what gets approved, what gets rejected
3. Codifies patterns as preference rules
4. Updates `autonomous_settings.success_rate` empirically

---

## 8. SEO, AEO, and GEO Workflows

### 8.1 SEO (Search Engine Optimization)
**Traditional Google ranking optimization**:

1. **Keyword Research**: ResearchAgent queries SERP, identifies opportunities with intent classification
2. **Content Creation**: WriterPipeline generates content optimized for target keywords
3. **Technical SEO**: TechSEOAgent audits and fixes Core Web Vitals, sitemaps, redirects
4. **Backlinks**: BacklinkAgent prospects and tracks link acquisitions
5. **Rank Monitoring**: `rank_monitor` runs every 15 min, tracks position changes
6. **Content Refresh**: `RefreshAgent` updates decaying articles based on `content_decay_logs`
7. **Competitor Tracking**: `competitor_monitor` runs every 60 min, detects new content/pricing changes

**Topic Cluster Architecture**:
- `topic_clusters` table defines pillar pages
- `cluster_articles` links supporting articles to pillars
- Internal linking optimized across cluster

### 8.2 AEO (Answer Engine Optimization)
**Optimizing for AI answer engines like Perplexity, ChatGPT, Google AI Overview**:

1. **Entity-Rich Content**: WriterPipeline extracts and tags entities (people, orgs, laws, services)
2. **FAQ Schema**: Every article includes structured FAQ with `FAQPage` schema
3. **Citation Architecture**: Numbered citations [1][2][3] link to authoritative sources
4. **Conciseness**: Content structured for snippet extraction (40-60 word answers)
5. **GEO Visibility Tracking**: `geo_visibility_logs` table tracks AI citations across platforms
6. **AEO Agent**: Dedicated phase in writer pipeline optimizes for AI search patterns
7. **Real-time Monitoring**: `geo_monitor` checks AI platform visibility every 30 min

**AEO Outputs**:
- `faq_schema` in `content_log`
- `citations` array with verified sources
- `geo_visibility_logs` entries per platform (ChatGPT, Perplexity, Google AI Overview)
- `aeo_citations` table tracking citation frequency

### 8.3 GEO (Generative Engine Optimization)
**Optimizing for Google's AI Overviews and generative search**:

1. **Structured Data**: JSON-LD schemas for `Article`, `FAQPage`, `HowTo`, `Organization`
2. **Entity Consolidation**: Knowledge graph ensures consistent entity representation
3. **Freshness Signals**: `freshness_score` in `knowledge_base` prioritizes recent content
4. **Multi-format Content**: Text + tables + lists + FAQ for varied AI extraction
5. **Authority Signals**: Backlink profile quality, EEAT signals, citation density
6. **GEO Monitoring**: `geo_monitor` detects AI Overview inclusion/exclusion
7. **Adaptive Strategy**: StrategyAgent adjusts content strategy based on GEO visibility trends

---

## 9. The 6 Continuous Monitoring Loops

**File**: `backend/services/continuous_monitor.py`

| Monitor | Cadence | Detects | Action |
|---------|---------|---------|--------|
| `rank_monitor` | Every 15 min | Keyword rank drops (≥3 positions) and jumps | Creates `realtime_alerts` + SSE + Slack |
| `serp_monitor` | Every 30 min | Global/local/mobile SERP differences | Alerts on volatility |
| `competitor_monitor` | Every 60 min | Pricing changes, new content, rank gains | Creates `realtime_alerts` for strategy |
| `tech_monitor` | Every 60 min | Broken links, speed degradation, mobile issues | Creates `pending_fixes` proposals |
| `geo_monitor` | Every 30 min | Local SEO opportunities, NAP issues | Creates `realtime_alerts` |
| `structure_monitor` | Every 6 hours | Orphan pages, redirect chains, duplicate titles | Creates `pending_fixes` proposals |

**Alert Flow**:
```
Monitor detects issue
  → report_problem()
    → Creates realtime_alerts row
    → push_sse_alert() → Dashboard updates live
    → send_slack_alert() / send_email_alert() for critical/high
      → autonomous_loop picks up alert
        → StrategyAgent.handle_alert()
          → Generates remediation strategy
            → Queues agent action or human approval
```

---

## 10. Human Approval & Oversight Model

### The Human Gate
**File**: `backend/middleware/human_gate.py`

**Rule**: Every WordPress publish and tech fix requires explicit human approval.

**Enforcement**:
1. `require_human()` decorator on all publish routes
2. `human_approval_required()` dependency checks `X-User-Id` header
3. Missing/invalid `X-User-Id` → **403 Forbidden** + log to `critical_action_logs`
4. No default `"admin"` fallback — strict validation against `users` table

### Approval Workflow

```
WriterPipeline generates content
  → blog_approvals row created (status=pending)
    → Dashboard shows in Approval Queue
      → Human clicks Approve
        → X-User-Id validated
          → WordPressService.publish_post()
            → critical_action_logs records action
              → SSE push to dashboard
      → Human clicks Reject
        → blog_approvals status=rejected
          → Reason logged
          → WriterPipeline analyzes rejection for learning
```

### RBAC (Role-Based Access Control)
**File**: `backend/middleware/rbac.py`

| Role | Level | Permissions |
|------|-------|-------------|
| `owner` | 3 | Full access: publish, delete, config, users |
| `editor` | 2 | Can approve/reject content, view analytics |
| `viewer` | 1 | Read-only: dashboard, reports, approvals queue |

**Bypass**: `system`, `admin`, `dev_user`, `owner_1` bypass RBAC for development.

---

## 11. Agent Communication Patterns

### Recall-Act-Write-Back (All Agents)

```
1. RECALL FIRST:
   brain.recall_facts(website_id, query, top_k)
   brain.recall_experiences(website_id, query, top_k)
   brain.recall_preferences(website_id, query, top_k)
   brain.recall_failures(website_id, query, top_k)
   brain.recall_outcomes(website_id, query, top_k)
   KnowledgeService.retrieve_relevant_hybrid(keyword, top_k)

2. ACT SECOND:
   Execute primary function (crawl, write, audit, prospect)

3. WRITE BACK AFTER:
   brain.remember(website_id, memory_type, title, content, source_type, confidence)
   brain.record_failure(website_id, agent_name, error_context, task_payload, backoff_minutes)
```

### Inter-Agent Communication via Database
Agents communicate through Supabase tables:
- `realtime_alerts` → StrategyAgent alert handling
- `blog_approvals` → Human approval queue
- `pending_fixes` → Tech fix proposals
- `brain_daily_jobs` → Job execution tracking
- `tasks` → Agent task execution log
- `content_log` → Generated content pipeline status
- `backlink_opportunities` → Backlink prospecting queue

### Event Bus (SSE Live Updates)
**File**: `backend/services/event_bus.py`

Publishes real-time events to connected dashboard clients:
- Content generation progress
- Approval queue changes
- Alert notifications
- Agent status changes
- Cost tracking updates

---

## 12. Database Schema (40+ Tables)

### Core Tables

| Table | Purpose |
|-------|---------|
| `websites` | Root entity: domain, CMS URL, credentials, GSC property, niche |
| `users` | User accounts with RBAC roles |
| `settings` | Key-value settings per website |
| `wordpress_connections` | WP Basic Auth credentials (encrypted) |
| `wordpress_oauth_tokens` | OAuth2 PKCE tokens (Fernet encrypted) |

### Content Tables

| Table | Purpose |
|-------|---------|
| `blogs` | Published blog mirror (title, content, seo_score, wp_post_id) |
| `blog_approvals` | Human approval queue (pending → approved → rejected → published) |
| `content_log` | All generated content with pipeline_status, final_scores |
| `content_pipeline_logs` | 100+ step audit trail for WriterPipeline |
| `content_expert_reviews` | 11-expert review scores and feedback |

### Knowledge & Brain Tables

| Table | Purpose |
|-------|---------|
| `knowledge_base` | Business facts with 1536-dim embeddings, freshness, credibility |
| `knowledge_relations` | Knowledge graph edges |
| `brain_memory` | Vector memory (7 types) with 1536-dim embeddings |
| `brain_daily_jobs` | Daily job execution log |
| `brain_content_performance` | Post-publish performance (14-day learning) |
| `brain_auto_pages_queue` | Auto-suggested pages awaiting approval |

### SEO & Monitoring Tables

| Table | Purpose |
|-------|---------|
| `keyword_opportunities` | Discovered keyword opportunities |
| `serp_landscape` | SERP analysis cache |
| `seo_reports` | SEO report data |
| `daily_searches` | Daily SERP trend data |
| `monitoring_alerts` | All monitoring alerts |
| `realtime_alerts` | Live alerts for dashboard |
| `geo_visibility_logs` | AI citation tracking (ChatGPT, Perplexity, AI Overview) |
| `content_decay_logs` | Content decay detection |

### Backlink Tables

| Table | Purpose |
|-------|---------|
| `backlinks` | Backlink inventory |
| `backlink_opportunities` | Qualified prospects with strategy, anchor suggestions |
| `backlink_monitor` | Live backlink status tracking |

### Agent & System Tables

| Table | Purpose |
|-------|---------|
| `tasks` | Agent task execution log |
| `daily_costs` | Token/cost tracking per agent per day |
| `autonomous_settings` | auto_publish, auto_generate, auto_refresh, goals, success_rate |
| `aeo_citations` | AEO citation tracking |
| `pending_fixes` | Tech fixes awaiting human approval |
| `critical_action_logs` | Audit trail for blocked/published actions |
| `topic_clusters` / `cluster_articles` | Pillar/cluster architecture |
| `rag_conversations` / `rag_evaluations` | RAG evaluation data |
| `analytics_data` | GSC/GA4 analytics |

### Vector Functions
- `match_knowledge()` — Cosine similarity on `knowledge_base.embedding`
- `match_brain_memory()` — Cosine similarity on `brain_memory.embedding`
- IVFFlat indexes on all embedding columns for fast similarity search

---

## 13. Self-Healing & Self-Improving Guarantees

### Self-Healing
When any agent fails **≥2 consecutive times**:
1. `StrategyAgent.generate_alternative_strategy()` is invoked
2. Generates parameter overrides:
   - Fallback connectors (e.g., Serper → direct crawl)
   - Reduced batch sizes (e.g., 10 articles → 2 articles)
   - Segmented execution (e.g., split keyword list into chunks)
3. Retries with overrides
4. If still failing → alerts human via Slack/Email

### Self-Improving
Every day at 10:00 IST:
1. `SupervisorAgent` runs 14-day outcome synthesis
2. Fetches top-performing content + human rejections
3. Analyzes patterns: what ranks, what gets approved, what gets rejected
4. Codifies patterns as **preference rules** in `brain_memory`
5. Updates `autonomous_settings.success_rate` based on empirical outcomes
6. Adjusts `trigger_weights` if agents are over/under-performing

Every Friday at 23:00 IST:
1. `run_weekly_self_audit()` computes real agent success rates from `tasks` table
2. Derives wins/failures from actual task outcomes (not hardcoded strings)
3. Calculates `overall_health_score` as weighted average of agent success rates
4. Writes real `weekly_reports` row
5. Pushes Slack summary with actual numbers

Every 1st of month at 06:00 IST:
1. `run_monthly_goal_setting()` queries real telemetry (rank_history, content_log, backlinks)
2. Calls NIM LLM with real data
3. Persists versioned goals to `autonomous_settings.monthly_goals`
4. Compares previous month's goals to actuals for trend analysis

---

## 14. Budget Management

### Daily Cost Tracking
Every LLM call logs to `daily_costs`:
```python
{
    "date": "2026-08-24",
    "agent_name": "WriterPipeline",
    "tokens": 142000,
    "cost_usd": 0.284
}
```

### Budget Manager (Daily 23:30 IST)
1. SUM(`tokens * price_per_token`) FROM `daily_costs` WHERE `date = today`
2. Compare against `autonomous_settings.budget_threshold`
3. If exceeded:
   - Pause non-critical agents
   - Send Slack alert
   - Log to `brain_memory` as experience
4. Budget is **per-website**, not global

### Cost Tracking Dashboard
Route: `/api/autonomous/costs`
- Total tokens tracked (30-day rolling)
- Total cost USD
- Per-agent breakdown
- Daily trend chart

---

## 15. Security Model

### Credential Security
- **Fernet encryption** for all secrets before Supabase storage
- `decrypt_secret()` only called inside outbound API calls
- `sanitize_website_row()` / `sanitize_dict()` strip raw credentials from API responses
- Status endpoints return only `is_configured: true/false` booleans

### Token Encryption
```python
# config.py
_raw_secret = os.getenv("TOKEN_ENCRYPTION_KEY")  # REQUIRED, no fallback
TOKEN_ENCRYPTION_KEY = base64.urlsafe_b64encode(
    hashlib.sha256(_raw_secret.encode()).digest()
).decode()
```
- **No hardcoded fallback** — startup fails if `TOKEN_ENCRYPTION_KEY` is missing
- Used to encrypt WordPress app passwords and OAuth tokens

### CORS
```python
ALLOWED_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    # Production domains only — NO wildcard
]
allow_credentials=True
```

### RBAC
- 3 roles: `owner` (level 3), `editor` (level 2), `viewer` (level 1)
- `require_role()` dependency checks `workspace_members` table
- Service/dev bypass for `system`, `admin`, `dev_user`, `owner_1`

### Human Gate
- `require_human()` decorator on all publish routes
- `X-User-Id` header required
- Missing/invalid → 403 + log to `critical_action_logs`
- No default `"admin"` fallback

### Secrets Management
- `.env` in `.gitignore` — never committed
- Live secrets rotated immediately if exposed
- All API keys stored as environment variables, never in code

---

## 16. Frontend Routes & UX

| Route | Page | Purpose |
|-------|------|---------|
| `/` | Dashboard | Autonomous health, jobs, approvals, alerts, agent status |
| `/dashboard` | Dashboard | Alias for `/` |
| `/websites` | Websites | Add/edit/remove websites |
| `/writer` | Autonomous Writer | Trigger content generation, view pipeline |
| `/content` | Content Studio | Browse all content, filter by status |
| `/approvals` | Approval Queue | Approve/reject pending content |
| `/brain` | Brand Brain & Memory | View knowledge base, brain memories, preferences |
| `/knowledge` | Knowledge Base | Browse and manage knowledge chunks |
| `/wordpress` | WordPress Manager | View connected sites, drafts, published posts |
| `/backlinks` | Backlinks & Authority | Backlink opportunities, monitoring, outreach |
| `/tech-seo` | Technical SEO | Technical audits, pending fixes, site health |
| `/monitoring` | 24/7 Monitoring | Live rank tracker, SERP monitor, alerts |
| `/workforce` | Autonomous Workforce | Agent status, decisions, costs, retry queue |
| `/calendar` | Publishing Calendar | Scheduled posts, content calendar |
| `/llms-txt` | LLMs.txt & GEO | LLMs.txt config, GEO visibility, AEO citations |
| `/connectors` | Connectors & Integrations | WordPress, GSC, GA4, Slack, Serper setup |
| `/settings` | System Settings | Goals, budget, autonomous toggles, account |
| `/onboarding` | Setup Wizard | First-time setup guide |

---

## 17. Complete Data Flow Example: Content Generation

```
1. Scheduler triggers job_auto_new_page at 11:00 IST
2. AutonomousDecisionEngine.should_run("auto_new_page")
   → Checks: target keyword available? knowledge grounding hits > 0?
   → Returns: {"should_run": True, "priority": "high"}
3. WriterPipeline.generate(topic, primary_keyword)
   Phase 1: brain_recall
     → brain.recall_facts() + brain.recall_preferences()
     → Returns: brand facts, tone profile, banned phrases
   Phase 2: audience_demand_analysis
     → Queries serp_landscape for CPC, trend, intent
     → Returns: business_potential_score = 85
   Phase 3: serp_competitor_intelligence
     → Serper.dev fetches top 10 SERP
     → Returns: competitor outlines, PAA, featured snippets
   Phase 4: positioning_outline_strategy
     → Generates unique angle, H2/H3 structure
     → Returns: content outline
   Phases 5-11: multi_step_content_writing → expert_reviews → humanizer → fact_check → ...
     → Each phase calls NIM LLM with actual context
     → Each phase logs to content_pipeline_logs
     → Content revised based on expert feedback
   Phase 12: brain_learn
     → Stores final content + scores in knowledge_base
     → Updates brain_memory with lessons learned
4. Final content saved to content_log (pipeline_status=completed)
5. blog_approvals row created (status=pending)
6. Dashboard shows in Approval Queue via SSE
7. Human clicks Approve
   → X-User-Id validated
   → WordPressService.publish_post()
   → critical_action_logs records action
   → SSE push to dashboard
8. Rank monitor starts tracking new article
9. 14-day outcome learning evaluates performance
10. Patterns fed back into brain_memory for next generation
```

---

## 18. Complete Data Flow Example: Autonomous Self-Healing

```
1. rank_monitor detects keyword dropped from #5 to #12
2. report_problem() creates realtime_alerts row
3. push_sse_alert() → Dashboard updates live
4. send_slack_alert() → "Rank drop detected: keyword X, -7 positions"
5. autonomous_loop picks up alert (5-min cycle)
6. StrategyAgent.handle_alert(alert)
   → Classifies: rank_drop
   → Generates strategy: "Create topic cluster around keyword X, optimize existing article Y"
7. StrategyAgent queues:
   a. content_refresh for article Y (update + optimize)
   b. auto_new_page for new cluster article
8. AutonomousDecisionEngine.should_run("content_refresh")
   → Checks: article age > threshold? decay_score > threshold?
   → Returns: True
9. WriterPipeline generates refreshed content
10. Human approves → WordPress publish
11. Rank monitor tracks recovery
12. 14-day outcome learning evaluates if strategy worked
13. If successful → brain.remember(outcome_type="success")
    If failed → brain.record_failure() + StrategyAgent generates alternative
```

---

## 19. Observability & Alerting

### Health Checks
Route: `/api/health/autonomous`

Returns:
```json
{
  "health_score": 94,
  "checks": {
    "supabase": "ok",
    "nvidia_nim": "ok",
    "serper": "ok",
    "wordpress": "ok",
    "slack": "ok",
    "scheduler": "ok"
  },
  "jobs_today": {
    "due": 8,
    "completed": 8,
    "failed": 0
  },
  "auto_fixes_applied": 0,
  "last_check": "2026-08-24T20:00:00Z",
  "next_check": "2026-08-24T20:15:00Z",
  "issues": [],
  "auto_fixed": []
}
```

### SSE Live Feed
- Content generation progress (phase by phase)
- Approval queue changes
- New alerts
- Agent status changes
- Cost tracking updates

### Slack Integration
- Daily morning brief (08:00 IST): yesterday's results, today's schedule
- Daily evening summary (20:00 IST): day outcome, issues, wins
- Real-time alerts for critical issues
- Weekly self-audit report (Friday 23:00 IST)

### Weekly Self-Audit Report
Generated every Friday at 23:00 IST:
- Agent success rates (computed from `tasks` table)
- Wins/failures derived from real outcomes
- Overall health score (weighted average)
- Goals achieved vs in-progress
- Next week plan
- Slack summary with actual numbers

---

## 20. Multi-Tenancy & Data Isolation

Every entity carries `website_id`:
- All queries filter by `website_id`
- All agents receive `website_id` context
- All brain memories scoped to `website_id`
- All costs tracked per `website_id`
- All alerts scoped to `website_id`

**Strict isolation**: No cross-website data leakage. Each website operates as an independent tenant.

---

## 21. Performance & Scalability

### Connection Pooling
- Supabase client with connection pool configuration
- Timeout settings for all external API calls
- Retry logic with exponential backoff (tenacity)

### Parallel DB Queries
- Stats endpoint uses `asyncio.gather()` for parallel queries
- Writer pipeline phases run async where possible
- Continuous monitors run in separate async loops

### Caching
- `serp_landscape` table caches SERP results (24h TTL)
- `research` table caches competitor analysis
- Knowledge base freshness prevents stale recall

### Cost Optimization
- Budget manager pauses non-critical agents if budget exceeded
- Token tracking per agent per day
- Decision engine skips jobs if conditions not met
- LLM call retry with model fallback (70B → 8B)

---

## 22. The Complete Picture: 24 Hours in the Life of RankForge

```
03:00 IST — Knowledge Evolution Service checks freshness decay
08:00 IST — Slack morning brief sent
08:30 IST — KnowledgeAgent crawls sitemap, updates knowledge_base
09:00 IST — ResearchAgent queries SERP, finds new opportunities
09:30 IST — KnowledgeAgent syncs freshness, detects stale records
10:00 IST — SupervisorAgent runs 14-day outcome synthesis
10:30 IST — RefreshAgent updates decaying articles
11:00 IST — WriterPipeline generates new content (if auto_generate=True)
11:30 IST — BacklinkAgent prospects new opportunities
12:00 IST — TechSEOAgent runs technical audit
14:00 IST — [Continuous] rank_monitor checks rankings every 15 min
14:30 IST — [Continuous] serp_monitor checks SERP volatility every 30 min
15:00 IST — [Continuous] competitor_monitor checks competitors every 60 min
15:30 IST — [Continuous] geo_monitor checks AI visibility every 30 min
16:00 IST — [Continuous] tech_monitor checks site health every 60 min
17:00 IST — [Continuous] structure_monitor checks orphans/redirects every 6h
18:00 IST — [Autonomous Loop] processes unread alerts every 5 min
20:00 IST — Slack evening summary sent
22:00 IST — [Autonomous Loop] checks budget, auto-refresh, auto-generate
23:00 IST — Weekly self-audit (Fridays only)
23:30 IST — Budget manager aggregates daily costs
           └── If budget exceeded → pause non-critical agents
```

**All day**: Dashboard updates live via SSE, humans approve/reject content, StrategyAgent handles alerts, brain learns from outcomes.

---

## 23. Zero-Mock Mandate

**Rule**: All production paths use real data. Empty tables render informative empty states, never fake data.

- `backlinks.py` → returns `[]` if DB empty, not fake Texas URLs
- `autonomous_loop.py` → queries `daily_costs` for real spend, not `$18.50`
- `writer_agent.py` → calls NIM LLM for all phases, no hardcoded stubs
- `autonomy.py` → returns DB goals or error, not hardcoded legal keywords
- `backlinks.py` → returns real prospects, not fake DR scores

---

## 24. Summary: What Makes RankForge Unique

| Feature | RankForge | Traditional SEO Tools |
|---------|-----------|----------------------|
| **Autonomy** | 24/7 self-triggering based on empirical state | Manual campaign setup |
| **Content Quality** | 12-phase, 111-step pipeline with 11 expert reviewers | Template-based generators |
| **Memory** | 7-type vector brain that learns from outcomes | No persistent memory |
| **Self-Healing** | Alternative strategies on failure | Static workflows |
| **Human Gate** | Approval queue with identity enforcement | Auto-publish or nothing |
| **AEO/GEO** | Native optimization for AI search engines | Afterthought |
| **Cost Control** | Per-agent daily tracking with budget enforcement | Flat monthly fees |
| **Observability** | 6 monitors, SSE live feed, Slack alerts | Weekly reports |
| **Multi-Tenancy** | Strict website_id isolation | Single-site tools |

RankForge is not just another SEO tool — it is an **autonomous SEO operating system** that thinks, learns, and acts on behalf of the user while maintaining strict human oversight on publish decisions.
