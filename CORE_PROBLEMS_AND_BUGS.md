# RankForge — Core Problems, Bugs & Autonomous Mode Design

## 1. How The System Currently Works

```
User / Frontend
     │
     ▼
FastAPI Backend (main.py)
     │
     ├── Routers (30+) → Services (30+) → Agents (25+)
     │         │
     │         ▼
     │   Supabase (PostgreSQL + pgvector)
     │         │
     │         ▼
     │   NVIDIA NIM LLM + Embeddings
     │
     └── Scheduler (APScheduler) — fires 8 daily cron jobs
          └── agents/scheduler.py
               ├── run_monthly_goal_setting (1st of month)
               ├── run_weekly_self_audit (Fridays)
               ├── run_autonomous_budget_manager (daily)
               └── run_autonomous_loop (every 5 min, alerts-driven)
```

### Data Flow (Per Website)
1. Frontend triggers a content generation request
2. `writer_agent.py` runs a 12-phase, ~111-step pipeline:
   - brain_recall → audience_demand → serp_competitor → outline → writing (25 steps) → expert_review (20 steps) → humanizer → fact_check → internal_links → citations → quality_gate → brain_learn
3. Each phase logs to `content_pipeline_logs` table
4. Final content is saved as `draft` in `content_log`
5. Human must approve via `/api/approvals` before it can publish (unless `auto_publish=True`)
6. Once approved, `writer.py` publishes to WordPress via REST API
7. Rankings are tracked via GSC / custom serp monitoring
8. Backlinks are monitored and outreach is generated via `backlinks.py`

### Autonomous Mode (Current)
- `autonomous_loop.py` runs a `while True` loop every 5 minutes
- Every cycle: scans `realtime_alerts` table for unread alerts → spawns `StrategyAgent` to handle each
- Separate cron jobs handle:
  - Monthly goal setting (LLM-driven)
  - Weekly self-audit (agent stats from `tasks` table)
  - Daily budget check (hardcoded `$18.50`)
- Scheduler (`agents/scheduler.py`) manages cron triggers
- Decision engine (`agents/autonomous_decision_engine.py`) decides if jobs should run

---

## 2. Core Problems & Bugs

### Category A: Security Issues

| # | Bug | File | Severity |
|---|-----|------|----------|
| A1 | Live secrets exposed in `.env` (`NVIDIA_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, WP creds) | `backend/.env` | CRITICAL |
| A2 | Hardcoded fallback encryption key `"rankforge-production-master-secret-key-32bytes"` — deterministic and reversible | `config.py:51` | HIGH |
| A3 | CORS `allow_origins` contains `"*"` alongside `allow_credentials=True` — browsers reject this; still a misconfiguration | `main.py:121` | MEDIUM |
| A4 | `X-User-Id` defaults to `"admin"` when header missing, allowing critical publish actions without real human identity | `writer.py:238`, `wordpress.py:117`, `proposals.py:84` | HIGH |
| A5 | Plaintext WordPress app passwords stored in `wordpress_connections` table | DB schema | HIGH |

### Category B: Broken / Missing Routes

| Frontend Call | Expected Backend | Status | Fix Needed |
|---|---|---|---|
| `POST /api/wordpress/save-connection` | connectors/wordpress | **MISSING** | Add route |
| `POST /api/wordpress/publish` | writer router | **MISSING direct** | Add route or redirect |
| `POST /api/backlinks/scout` | backlinks router | **MISSING** | Add route |
| `POST /api/backlinks/generate-outreach` | backlinks router | **MISSING** | Add route |
| `GET /api/links/{wid}/graph` | no `links` router | **MISSING** | Create `links.py` |
| `GET /api/aeo/sov` | `seo_aeo_geo.py` | **MISSING endpoint** | Add endpoint |

| Router Referenced in Imports | Status |
|---|---|
| `routers/keywords.py` | **DOES NOT EXIST** |
| `routers/analytics.py` | **DOES NOT EXIST** |
| `routers/serp.py` | **DOES NOT EXIST** |
| `routers/scheduler.py` | **DOES NOT EXIST** (scheduler is in `agents/`) |
| `routers/report.py` | **DOES NOT EXIST** |

### Category C: Dead Code & Logic Bugs

| # | Bug | File | Line(s) |
|---|-----|------|---------|
| C1 | Unreachable duplicate `return` after first return — second block contains `keyword_density` variable that may be undefined, causing `NameError` | `writer_agent.py` | 700, 709-717 |
| C2 | `connectors_serper_router` mounted **twice** in `main.py` | `main.py` | 529-530 |
| C3 | Many routers mounted with BOTH `/api` prefix AND without prefix — doubles route table, slows resolution | `main.py` | scattered |
| C4 | `langchain` packages imported in `crew.py` but **NOT** in `requirements.txt` | `requirements.txt` / `crew.py` | — |
| C5 | `published_today: max(1, total_blogs)` — if no blogs exist, shows `1` published today instead of `0` | `autonomy.py` | 313 |
| C6 | `total_runs` capped with `max(5, total)` and `completed` with `max(4, len(completed))` — fabricates minimum run counts | `autonomous_loop.py` | 133-134 |
| C7 | `success_rate` defaults to `92.5` and `avg_duration_sec` to `4.2` when no data exists instead of `None` or `0` | `autonomous_loop.py` | 136-137 |
| C8 | `POST /api/autonomous/settings` returns `"success": True` **even on exception** — swallows DB errors | `autonomy.py` | 257-266 |
| C9 | `Budget Manager` uses hardcoded `current_spend = 18.50` — never queries `daily_costs` table | `autonomous_loop.py` | 228 |
| C10 | `Self Audit` hardcodes `wins`, `failures`, and `overall_health_score: 96.5` — never computed from real data | `autonomous_loop.py` | 140-148, 180 |

### Category D: Hardcoded Mock Data in Production Paths

| # | Mock Data | File | Impact |
|---|-----------|------|--------|
| D1 | `backlinks.py` returns 20+ fake Texas legal URLs, DR scores, and priority scores when DB is empty | `backlinks.py` | 72-268 |
| D2 | `serper_service.py` falls back to `example.com` URLs and synthetic search results | `serper_service.py` | — |
| D3 | `connectors.py` returns hardcoded `site_url: "https://accident.innovatcs.com"`, `username: "admin"` | `connectors.py` | — |
| D4 | `writer_agent.py` has 10+ stub methods returning hardcoded fake values: `_analyze_competitor_content_depth` → `avg_word_count: 2500`, `_detect_ai_patterns` → `85`, `_calculate_ai_search_score` → `80`, `_extract_factual_claims` → `['claim_1'...]`, `_verify_statistical_claims` → `verified: len(claims), failed: 0` | `writer_agent.py` | — |
| D5 | `autonomy.py` default goals contain specific legal keywords: `"Houston car accident lawyer"`, `"Texas commercial truck crash claims"` | `autonomy.py` | 83-88 |
| D6 | `autonomous_loop.py` budget threshold hardcoded `150.0` and spend `18.50` | `autonomous_loop.py` | 219, 228 |
| D7 | `autonomous_loop.py` monthly goal fallback contains hardcoded target numbers | `autonomous_loop.py` | 76-88 |

### Category E: Architecture / Design Issues

| # | Issue | Severity |
|---|-------|----------|
| E1 | **No connection pooling** for Supabase — singleton client created without pool/timeout configuration | HIGH |
| E2 | **Synchronous `requests` calls** in async FastAPI routers — blocks event loop | HIGH |
| E3 | **No parallel DB queries** — `main.py` stats endpoint runs 6 sequential Supabase queries | MEDIUM |
| E4 | **Two competing schedulers** — `agents/scheduler.py` (APScheduler) AND `autonomous_loop.py` (while True loop) — duplicate responsibilities | HIGH |
| E5 | **Dead build artifacts** in root: `build_part4b.tmp`, `build_part4c.tmp`, `tmp_err.txt`, `rankforge.html.bak` | LOW |
| E6 | **`rankforge.html`** and **`app/page.tsx`** both claim to be the "main dashboard" — confused UX | MEDIUM |
| E7 | **`dashboard/page.tsx`** is just a redirect to `/` — no actual separate dashboard page | LOW |
| E8 | **Writer pipeline claims** "10-phase, 111-step" but PHASES list has 12 items and PHASE_STEPS sum is far less than 111 | MEDIUM |
| E9 | **Cost tracking returns fake seed data** when `daily_costs` table is empty | MEDIUM |
| E10 | **Agent limits** (`AGENT_LIMITS` in `agent_limits.py`) not enforced in autonomous loop | MEDIUM |
| E11 | **Memory leak risk** — `get_supabase()` singleton never resets between test runs or on env change | LOW |
| E12 | **No circuit breaker** for LLM calls when NIM is down — falls back to hardcoded goals silently | MEDIUM |

---

## 3. How Autonomous Mode SHOULD Work

### Design Principles
1. **No hardcoded values in production paths** — all defaults come from `autonomous_settings` DB table
2. **Single scheduler authority** — APScheduler owns all cron; `while True` loop only handles real-time alert reactions
3. **Real telemetry drives all decisions** — no synthetic wins, failures, or health scores
4. **Budget is computed, not guessed** — sums actual `daily_costs` rows
5. **Human gate is enforced** — `X-User-Id` defaults to `anonymous`, not `"admin"`; no publish without approval unless explicitly opted-in

### Autonomous Loop Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  AUTONOMOUS LOOP (every 5 minutes)                              │
│                                                                 │
│  1. Query websites table                                        │
│  2. For each website:                                           │
│     a. Check realtime_alerts WHERE status = "unread"           │
│     b. For each unread alert → StrategyAgent.handle_alert()    │
│        - Classify alert type (rank_drop, budget, agent_degradation,  │
│          competitor_win, new_backlink, content_performance)     │
│        - Route to appropriate agent queue                       │
│        - Set TTL for auto-resolve if conditions improve         │
│     c. Check autonomous_settings.auto_generate                  │
│        - If TRUE and pipeline queue < threshold → queue content  │
│     d. Check autonomous_settings.auto_refresh                   │
│        - If TRUE and content age > threshold → queue refresh    │
│     e. Check autonomous_settings.auto_publish                   │
│        - If TRUE and approval score > threshold → auto-publish  │
│        - Else → queue for human approval                       │
│  3. Sleep 300s                                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  SCHEDULER CRON JOBS (APScheduler, Asia/Kolkata)                │
│                                                                 │
│  daily  00:00 IST  → run_daily_crawl()                          │
│  daily  01:00 IST  → run_daily_ranking_check()                  │
│  daily  06:00 IST  → run_content_pipeline()                     │
│  daily  10:00 IST  → run_backlink_autopilot()                   │
│  daily  18:00 IST  → run_competitive_analysis()                 │
│  daily  23:30 IST  → run_autonomous_budget_manager()            │
│  weekly   Fri 23:00 IST → run_weekly_self_audit()               │
│  monthly 1st 06:00 IST → run_monthly_goal_setting()             │
└─────────────────────────────────────────────────────────────────┘
```

### Monthly Goal Setting (Should Work Like This)

```python
# CURRENT PROBLEM: Goals are generated by LLM, but fallback is hardcoded
# WHEN IT SHOULD:
# 1. Query rank_history for Top 10 keyword count
# 2. Query content_log for published count
# 3. Query backlinks for active backlink count
# 4. Call NIM LLM with REAL telemetry
# 5. Persist goals to autonomous_settings.monthly_goals
# 6. Goals are VERSIONED — do not overwrite, append with timestamp
# 7. Previous month's goals are compared to actuals for trend analysis
```

### Weekly Self-Audit (Should Work Like This)

```python
# CURRENT PROBLEM: Wins, failures, health score are hardcoded strings
# WHEN IT SHOULD:
# 1. Fetch 7-day tasks from tasks table
# 2. Compute per-agent: total_runs, completed, failed, success_rate, avg_duration
# 3. Compute site-level: articles_published, new_backlinks, rank_changes, traffic_delta
# 4. Compare actuals against monthly_goals
# 5. Derive wins/failures from real outcomes (not string arrays)
# 6. Calculate health_score = weighted average of agent success rates
# 7. Write real weekly_reports row
# 8. If any agent < 70% success_rate → StrategyAgent.handle_alert()
# 9. Push Slack summary with ACTUAL numbers
```

### Budget Manager (Should Work Like This)

```python
# CURRENT PROBLEM: Uses hardcoded $18.50
# WHEN IT SHOULD:
# 1. SUM(tokens * price_per_token) FROM daily_costs WHERE date = today
# 2. Compare sum against autonomous_settings.budget_threshold
# 3. If exceeded → pause non-critical agents, send Slack alert
# 4. Budget is per-website, not global
# 5. Daily costs are logged in real-time by each agent via _log_cost()
```

### Alert-Driven Reaction (Should Work Like This)

```python
# CURRENT PROBLEM: Alerts spawn StrategyAgent but no routing logic
# WHEN IT SHOULD:
# Alert types → Agent routing:
#   rank_drop            → tech_seo_agent + content_agent
#   budget_exceeded      → scheduler.pause_non_critical()
#   agent_degradation    → strategy_agent.diagnose_and_fix()
#   competitor_win        → research_agent + writer_agent
#   new_backlink         → backlink_agent (verify quality)
#   content_performance  → refresh_agent (update if stale)
#   technical_error      → tech_seo_agent
#
# Each alert gets:
#   - TTL (auto-resolve after N hours if conditions improve)
#   - Priority (critical/high/medium/low)
#   - Retry count (max 3 before escalating to human)
#   - Human notification if escalation threshold hit
```

### Autonomous Decision Engine

```python
# CURRENT PROBLEM: Decision engine exists but not used in autonomous_loop
# WHEN IT SHOULD:
# Before each cron job fires:
#   1. Call engine.should_run(job_name)
#   2. Engine checks: last_run_time, success_rate, budget_remaining, alert_queue_depth
#   3. If should_run == False → skip with reason logged
#   4. If should_run == True with conditions → proceed with adjusted parameters
#
# Decision factors (empirical, not hardcoded):
#   - Is there an unread critical alert? → BOOST priority
#   - Did last 3 runs of this job fail? → SKIP and alert human
#   - Is daily budget > 80% consumed? → SKIP non-critical jobs
#   - Is website traffic trending up? → INCREASE content cadence
#   - Is website traffic trending down? → TRIGGER emergency content job
```

### Content Pipeline (Should Work Like This)

```python
# CURRENT PROBLEM: 10+ stub phases return hardcoded values
# WHEN IT SHOULD:
# Phase 1: brain_recall
#   - Query brain_memory and knowledge_base via vector similarity
#   - Return actual recalled context (not empty list)
#
# Phase 2: audience_demand_analysis
#   - Query serp data for search volume, CPC, trend
#   - Query GSC for existing impression data
#   - Return real demand scores
#
# Phase 3: serp_competitor_intelligence
#   - Crawlee or serper_service fetch actual SERP results
#   - Analyze top 10 competitor content structure
#   - Return real competitor data (word count, headings, schema)
#
# Phase 4: positioning_outline_strategy
#   - Use competitor data + demand data + goal focus_keywords
#   - Generate actual content outline with sections
#
# Phase 5: multi_step_content_writing (25 steps)
#   - Each step calls call_nim_llm() with actual context
#   - Not a single stub returning "content"
#
# Phases 6-11: Expert reviews
#   - Each expert calls NIM LLM with real content
#   - Returns actual scores and feedback
#   - Content is revised based on feedback
#
# Phase 12: brain_learn
#   - Store final content + scores + feedback in knowledge_base
#   - Update brain_memory with lessons learned
#   - Update autonomous_settings based on actual performance
```

### WordPress Publish Flow (Should Work Like This)

```python
# CURRENT PROBLEM: X-User-Id defaults to "admin" when header missing
# WHEN IT SHOULD:
# 1. Frontend sends X-User-Id from authenticated session (not localStorage default)
# 2. Backend validates X-User-Id against Supabase users table
# 3. If X-User-Id is missing or invalid → 401 Unauthorized
# 4. Content status = "approved" requires explicit human approval in approvals table
# 5. auto_publish=True only bypasses approval for:
#    - First-time content (still logged)
#    - Content with quality_score > threshold
# 6. Every publish action is logged in tasks table with real X-User-Id
# 7. WordPress app password is encrypted with TOKEN_ENCRYPTION_KEY
```

---

## 4. What Needs to Be Fixed Before It Is Actually Autonomous

### Phase 1: Critical Fixes (Cannot Run Without)
1. **Rotate all secrets** — `.env` contains live keys that are committed/pushed
2. **Add missing router files** — `keywords.py`, `analytics.py`, `serp.py`, `report.py`
3. **Add missing backend routes** — `/api/wordpress/save-connection`, `/api/backlinks/scout`, etc.
4. **Fix duplicate router mounts** in `main.py`
5. **Add `langchain-openai`, `langchain-community`, `langchain-core`** to `requirements.txt`
6. **Remove hardcoded `"admin"` fallback** for `X-User-Id` — enforce 401 on missing
7. **Remove hardcoded encryption key fallback** — fail startup if `TOKEN_ENCRYPTION_KEY` not set

### Phase 2: Remove Mock Data
8. **Replace hardcoded backlink URLs** in `backlinks.py` with real data or empty results
9. **Remove hardcoded wins/failures/health_score** from `autonomous_loop.py`
10. **Remove hardcoded budget values** — query `daily_costs` table
11. **Remove hardcoded goal fallbacks** — return error or use DB defaults only
12. **Replace writer_agent stubs** with real LLM calls or explicit "not implemented" errors

### Phase 3: Architecture Fixes
13. **Single scheduler authority** — remove `while True` loop, let APScheduler own everything
14. **Parallelize DB queries** in stats endpoint with `asyncio.gather`
15. **Replace sync `requests` with `httpx`** in all async routers
16. **Add Supabase connection pooling** and timeout configuration
17. **Add circuit breaker** for NIM LLM calls (circuit_breaker.py already exists but unused?)
18. **Version monthly goals** — append history instead of upserting

### Phase 4: Observability
19. **Add structured logging** — every autonomous decision must log: timestamp, website_id, trigger, action taken, result
20. **Add cost tracking hooks** — every LLM call logs tokens + cost to `daily_costs`
21. **Add alert TTL and escalation** — unhandled alerts auto-escalate to human after N hours
22. **Add performance profiling** — track phase durations in writer pipeline

---

## 5. Summary

| Area | Current State | Target State |
|------|--------------|--------------|
| **Backend routes** | 9 frontend calls missing; 5 router files missing | All frontend calls matched; all routers exist |
| **Mock data** | 15+ hardcoded values in production paths | Zero mock data; real data or explicit empty results |
| **Auth** | `X-User-Id` defaults to `"admin"` | Strict validation; 401 on missing/invalid |
| **Encryption** | Hardcoded fallback key | Enforced env var; fail on missing |
| **Scheduler** | Two competing systems (APScheduler + while True) | APScheduler is sole authority |
| **Budget** | Hardcoded `$18.50` | Computed from `daily_costs` table |
| **Self-audit** | Hardcoded wins/failures/health_score | Computed from real task outcomes |
| **Writer pipeline** | 10+ stubs returning fake values | Real LLM calls or explicit errors |
| **Cost tracking** | Returns fake seed data | Real aggregated costs |
| **Secrets** | Live keys in tracked `.env` | Rotated; `.env` in `.gitignore` |

The system is architecturally sound (FastAPI + Supabase + NVIDIA NIM + CrewAI) but currently a **skeleton with hardcoded organs** — it can demonstrate UI flows but cannot run autonomously because every critical decision point defaults to a fake value.
