# LAUNCH CHECKLIST - Lightweight (No Docker)

Minimal prerequisites for deploying RankForge. All items checked before going live.

## Pre-Launch Checklist

- [ ] **Supabase Schema** - `supabase_schema.sql` + `supabase_schema_v2.sql` run in SQL Editor
- [ ] **Vector Extension** - `create extension if not exists vector;` enabled
- [ ] **RPC Functions** - `match_content`, `match_pages`, `match_knowledge` functions created
- [ ] **Environment Variables** - `backend/.env` created from `.env.example` with real values
- [ ] **Frontend Environment** - `frontend-next/.env.local` created with `NEXT_PUBLIC_API_URL=http://localhost:8000`
- [ ] **Supabase Connection** - Test connection with `curl http://localhost:8000/health` returns 200
- [ ] **Supabase Tables** - All tables created with correct columns

## Backend Verification

- [ ] **Backend Starts** - `uvicorn main:app --reload --port 8000` starts without errors
- [ ] **Health Endpoint** - `GET /health` returns 200 with `{"status": "ok"}`
- [ ] **API Routes** - All routes accessible:
  - `/api/websites` - GET/POST
  - `/api/proposals` - GET/POST
  - `/api/roi/{website_id}` - GET
  - `/api/calendar/{website_id}` - GET
  - `/api/backlinks/{website_id}` - GET
  - `/api/memory/{website_id}` - GET

## Frontend Verification

- [ ] **Frontend Starts** - `npm run dev -- --port 3000` starts without errors
- [ ] **Dashboard Loads** - `/dashboard` shows 4 KPIs with real API data
- [ ] **No Mock Data** - All pages use `lib/api.ts` not hardcoded arrays
- [ ] **Brutalist Design** - No glossy styles (grep for gradients, shadows, blur returns 0)
- [ ] **Fonts Load** - DotGothic16 and IBM Plex Mono loaded from Google Fonts
- [ ] **Colors Match** - paper #F6F4EF, stone #EDEBE6, ink #111, accent #FF4D12
- [ ] **Build Passes** - `npm run build` returns 0 errors

## WordPress Integration (Optional)

- [ ] **WP Credentials** - `WORDPRESS_URL`, `WORDPRESS_USER`, `WORDPRESS_APP_PASSWORD` set
- [ ] **WP Connection** - `POST /wp/v2/posts` works with app password auth
- [ ] **Publish Flow** - Approve blog via API → WP posts live with 200 status

## API Credentials

- [ ] **NVIDIA API Key** - Set and tested (embedding 1024-dim vectors)
- [ ] **Crawlee API Key** - Set and tested (crawl web pages)
- [ ] **GSC Credentials** - `gsc-service.json` placed or fallback mock confirmed
- [ ] **Redis (Optional)** - Running on localhost:6379 or system works without

## Safety Verification

- [ ] **7 Safety Tests PASS** - `pytest backend/tests/test_safety_gate.py -v` all pass
- [ ] **No Auto-Publish** - Grep result: `backend/agents/` shows 0 direct publish calls
- [ ] **Critical Action Logs** - Dashboard `/safety` shows recent blocked/allowed actions
- [ ] **Approval Required** - All WordPress actions require `status="approved"` + `human_user_id`

## Functionality Tests

- [ ] **E2E 10 Steps PASS** - `pytest backend/tests/test_e2e_full_flow.py -v` all pass
- [ ] **ROI Dashboard** - Data shows real metrics from database
- [ ] **Calendar View** - 7-day grid with blog dots shows correct status colors
- [ ] **Quality Gate** - Blogs blocked until quality check passes (tone >0.75, spell <3 errors)
- [ ] **Knowledge Base** - 20+ pages crawled before any work begins

## Production Readiness

- [ ] **Logging Enabled** - All critical actions logged to `tasks` table
- [ ] **Error Handling** - Graceful fallback when backend offline (dashed empty states)
- [ ] **Rate Limits** - Approval rate limit 5/min per website enforced
- [ ] **Homepage Protection** - 14-day cooldown on homepage edits
- [ ] **Delete Blocked** - `delete_page` always raises CriticalActionBlockedError

## Final Build

- [ ] **npm run build** - Returns 0 errors, no warnings
- [ ] **TypeScript Check** - No type errors (`tsc --noEmit`)
- [ ] **Lint Passes** - `npm run lint` passes
- [ ] **Assets Optimized** - No large bundles, fonts loaded externally

## Deploy Options (Render)

When ready for production:

**Render Blueprint Deployment (`render.yaml`):**
- Deploy via Render Blueprints using `render.yaml`
- **Backend:** `rankforge-backend` (Docker runtime via root `Dockerfile`, health check at `/health`)
- **Frontend:** `rankforge-frontend` (Node runtime, rootDir `frontend-next`, build `npm install && npm run build`, start `npm start`)
- **Redis:** `rankforge-redis` (managed Redis cache)

**Database:** Continue using Supabase (free tier sufficient for most sites)

---

## Quick Start Commands

```bash
# Terminal 1 - Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2 - Frontend  
cd frontend-next
npm install
npm run dev -- --port 3000

# Terminal 3 - Run tests (when env vars set)
pytest backend/tests/test_safety_gate.py -v
```
