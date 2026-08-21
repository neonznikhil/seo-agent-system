# PRESENTATION_GUIDE.md

## How to Present Real Results

### 1. Environment Setup

Copy `.env.example` to `.env` and fill in real values:

```bash
cp backend/.env.example backend/.env
```

Required variables:
- `SUPABASE_URL=https://your-project.supabase.co`
- `SUPABASE_KEY=your-anon-key`
- `NVIDIA_API_KEY=your-nim-api-key`
- `GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}`
- `GA4_PROPERTY_ID=properties/123456`
- `REDIS_URL=redis://localhost:6379/0`
- `ALLOWED_CORS_ORIGINS=http://localhost:3000`

### 2. Start Backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Verify:
- `http://localhost:8000/health` returns `{"status": "ok", "checks": {...}}`
- Logs show `[Startup] All monitors initialized`
- Crawlee + Playwright installed

### 3. Start Frontend

```bash
cd frontend-next
npm install
npm run dev
```

Open `http://localhost:3000`

Verify:
- CSS loads (not dry HTML)
- Dark mode toggle works
- Sidebar navigation works
- All 22 pages render

### 4. Presentation Flow (Real Data Only)

#### Step 1: Settings (`/settings`)
- Click "Test Supabase" → green dot if SUPABASE_URL + SUPABASE_KEY valid
- Click "Test GSC" → green dot if GOOGLE_CREDENTIALS_JSON valid
- Click "Test GA4" → green dot if GA4_PROPERTY_ID valid
- Click "Test WP" → green dot if CMS URL + app password valid
- Click "Test Crawlee" → green dot if crawlee installed
- Check `.env` status section shows missing_keys real list

#### Step 2: Research (`/research`)
- Enter keyword: `best crm for saas startups`
- Click "Analyze"
- Real SERP top 10 scraped via Crawlee with:
  - H1, H2s, word_count, has_table, has_faq badges
  - Gaps (missing H2s where 60%+ top have, we don't)
  - PAA questions
  - Featured snippet opportunity
- GSC keywords table real with clicks, impressions, position, CTR

#### Step 3: Clusters (`/clusters`)
- Click "Build Clusters"
- Real GSC keywords clustered via NIM embeddings cosine >0.82
- 3+ clusters with authority_score progress bar
- Click cluster → articles table with priority_score = business_potential * impressions * (1/position)
- Status badges: opportunity / queued / writing / draft_ready

#### Step 4: Writer (`/writer`)
- Topic: `Best CRM for SaaS startups`
- Primary keyword auto-suggested from GSC striking distance (pos 11-20)
- Mode badge: grounded (uses knowledge base) / deep (full research) / combined
- Click "Generate"
- Live stepper shows 10 phases 111 steps via SSE:
  - Phase 1: Audience demand analysis
  - Phase 2: SERP competitor intelligence
  - Phase 3: Positioning outline strategy
  - Phase 4-6: Content writing with real LLM calls
  - Phase 7-9: Internal links, EEAT, citations
  - Phase 10: Final quality gate
- 11 expert circles with real scores (SEO, EEAT, AI Search, Info Gain, Business, Humanizer, etc.)
- All scores >=70 (green) or <70 (red)
- Preview draft HTML with:
  - Author box (real name from tone profile)
  - Schema JSON-LD viewer
  - 3 internal links from GA4 high-traffic pages
  - Comparison table with real competitor pricing from Crawlee
  - FAQ 4 Q/A answer-first 40-60 words each
- Approve & Publish modal:
  - Requires X-User-Id header (set in localStorage as `userId`)
  - Without X-User-Id → 403 "Human approval required"
  - With X-User-Id → real WP publish via REST API
  - Original URL preserved if refresh mode

#### Step 5: Content (`/content`)
- Table of all content_log entries
- Filters: status, mode, business_potential, is_refresh
- Click entry → detail view with:
  - 111 pipeline logs
  - 11 expert reviews with scores
  - Citations verified with source URLs
  - EEAT: author, reviewer, last-updated, schema JSON-LD
  - Diff view for refresh content

#### Step 6: Monitoring (`/monitoring`)
- SSE live feed from `/api/monitoring/{id}/live`
- Auto-reconnect on disconnect
- Filter by type: rank_drop, tech_broken_link, content_decay, competitor_price, geo_visibility, backlink_lost
- Filter by severity: critical, major, minor
- Approval Queue tabs:
  - Content Drafts (pending_approval)
  - Fixes (pending)
  - Decay Drafts (draft_ready)
  - Backlink Prospects (opportunity)
- Mark Read → real update
- Approve Fix → requires X-User-Id

#### Step 7: Decay (`/decay`)
- Click "Detect Now"
- Real GSC data: positions 3-10 dropped to 11+ with clicks -30%
- Table: URL, keyword, old_pos → new_pos, clicks change, decay_reason
- Diagnose → real Crawlee crawl of top 3 competitors + original page
- Gap analysis: missing H2s, missing table, word_count_gap, new_competitors
- Refresh → 10-phase pipeline (is_refresh=true)
- Updates original WP post ID, not new draft
- Diff viewer: original Crawlee extract vs refreshed

#### Step 8: Links (`/links`)
- Internal Link Graph: D3 force layout
- Nodes sized by PageRank (real networkx calculation)
- Orphan nodes: red highlight (no incoming links)
- High-traffic nodes: green highlight (GA4 data)
- Click node → details
- Backlink Prospects table:
  - DR (Domain Rating)
  - Contact strategy: broken_link / resource_page / competitor_gap / guest_post
  - Reason + anchor suggestion
- Monitor table: status active/broken/redirected/lost, checked_at real timestamp
- Buttons: "Find Prospects" → real crawl, "Check" → real monitor run

#### Step 9: Knowledge (`/knowledge`)
- Drag-drop PDF/DOCX upload → `/api/knowledge/{id}/upload`
- Real PyMuPDF parse
- URL input → real Crawlee crawl
- Drive file ID / Notion DB ID inputs
- Table: knowledge_sources with title, source_type, is_verified, content_extracted preview, embedding exists
- Search: real similarity >0.75 via NIM embeddings
- Delete real

#### Step 10: Dashboard (`/`)
- 6 KPI cards real from APIs:
  - SEO Score: avg from tech_audits health_score
  - AEO Opportunities: count from GSC keywords pos 11-20
  - GEO Readiness: avg from geo_visibility_logs was_cited %
  - AI Citations: % from geo_visibility_logs
  - Decayed Pages: count from decay_logs
  - Topic Authority: avg authority_score from clusters
- Live Agent Activity: SSE from `/api/monitoring/{id}/live`
- ROI Trend: real GSC clicks last 7 days bar chart
- Content Calendar: real content_log items
- Technical Health: real alerts from monitoring
- Footer marquee: real status from /health

### 5. Real Results to Show

#### Before (Mock Data)
- Dashboard showed hardcoded: 24.8K impressions, 1,342 keywords, 87/100 SEO score
- Writer returned fake 85 scores
- Connectors showed 147 posts, 84.2K impressions fake
- No real API calls

#### After (Real Data)
- Dashboard shows real GSC impressions from `gsc_data` table
- Writer generates real content via NVIDIA LLM, real scores from 11 experts
- Connectors show real post count from `content_log`, real GSC stats from API
- All data from: Supabase, GSC API, GA4 API, Crawlee, WordPress REST, NIM LLM

### 6. Human Gate Enforcement

- `POST /api/writer/{id}/{content_id}/publish` requires `X-User-Id` header
- Without header → 403 "Human approval required"
- With header → real WordPress publish via Basic auth
- `POST /api/writer/{id}/{content_id}/approve-draft` requires `X-User-Id`
- All approval actions logged to `critical_action_logs`

### 7. Security

- CORS: `ALLOWED_CORS_ORIGINS` from env, not `*`
- No `eval()` or `exec()`
- No hardcoded secrets
- X-User-Id mandatory for write operations
- WordPress auth: Basic auth with app password (not plaintext)
- Supabase: parameterized queries only

### 8. Common Issues

| Issue | Solution |
|-------|----------|
| Backend offline | Run `uvicorn main:app --reload --port 8000` |
| CSS not loading | Check `globals.css` has `@tailwind` at top, `layout.tsx` imports it |
| GSC not connected | Add `GOOGLE_CREDENTIALS_JSON` in `.env`, test in `/settings` |
| WP publish fails | Check `cms_url`, `cms_user`, `app_password` in websites table |
| NIM LLM timeout | Check `NVIDIA_API_KEY` in `.env` |
| No GSC data | Run GSC sync first: `POST /api/gsc/sync/{website_id}` |

### 9. Key Metrics to Highlight

- **Zero mock data**: Every number comes from real API or database
- **10-phase pipeline**: 111 steps logged to `content_pipeline_logs`
- **11 expert reviews**: Real LLM-based scoring, not hardcoded
- **Human gate**: X-User-Id required for publish, no auto-publish
- **Real connectors**: GSC, GA4, Crawlee, Supabase, WordPress all real implementations
- **Production build**: 0 TS errors, 22 pages prerendered
- **CSS fixed**: Tailwind loads, dark mode works, no dry HTML
