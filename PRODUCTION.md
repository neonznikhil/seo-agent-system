# RankForge Production Deployment & System Guide

## System Architecture

RankForge is an autonomous SEO, AEO, and GEO engine operating 25+ specialized AI agents with continuous scheduling, zero mock data, and deep business context integration.

### Core Architecture Components
1. **FastAPI Backend (`./backend/`)**:
   - High-throughput asynchronous API handling agent execution, Supabase pgvector integration, NVIDIA NIM LLM/Embeddings inference, WordPress REST publishing, and automated cron scheduling.
2. **Next.js 14 Frontend (`./frontend-next/`)**:
   - Modern Tailwind dark-mode UI with ReactFlow agent canvas (`/workforce`), deep knowledge base manager (`/knowledge`), real connector setup (`/connectors`), backlink outreach pipeline (`/backlinks`), and AEO/LLM citation engine (`/aeo`).
3. **Storage & Vector Database (Supabase + pgvector)**:
   - 10+ core production tables, cosine vector search RPCs (`match_knowledge`, `match_brain_memory`), and autonomous task logging.
4. **Scheduler (APScheduler Asia/Kolkata)**:
   - 7 autonomous daily/hourly jobs (research, knowledge sync, brain learning, content refresh, auto new page publishing, backlink prospecting, AEO citation tracking).

---

## Quick Start (Local Development)

### 1. Backend Setup
```bash
# Windows
start-backend.bat

# Linux / Mac / Manual
cd backend
python -m pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend Setup
```bash
# Windows
start-frontend.bat

# Linux / Mac / Manual
cd frontend-next
npm install
npm run dev
```

---

## Production Docker Deployment

```bash
# 1. Configure environment
cp backend/.env.example backend/.env
cp frontend-next/.env.example frontend-next/.env.local

# 2. Build and launch all containers
docker-compose up --build -d

# 3. View running logs
docker-compose logs -f
```

---

## Required Environment Variables

| Variable | Description | Source |
|---|---|---|
| `NVIDIA_API_KEY` | NVIDIA NIM LLM & Embeddings API key | https://build.nvidia.com/account/api-keys |
| `SUPABASE_URL` | Supabase project URL | https://supabase.com/dashboard |
| `SUPABASE_KEY` / `SUPABASE_SERVICE_KEY` | Supabase Service Role Key | Supabase Settings -> API |
| `DATABASE_URL` | PostgreSQL direct connection string | Supabase Settings -> Database |
| `TAVILY_API_KEY` | Real-time web search and competitor analysis | https://tavily.com |
| `SERPER_API_KEY` | Google SERP & backlink data | https://serper.dev |

---

## Autonomous Operations Schedule (Asia/Kolkata)

- **09:00 AM** - `daily_search`: Web & competitor trends extraction (ResearchAgent)
- **09:30 AM** - `knowledge_sync`: Knowledge base freshness sync, law statutes, and competitor doc refresh
- **10:00 AM** - `brain_learn`: Auto-learning from live WordPress analytics and performance metrics
- **10:30 AM** - `content_refresh`: Automated refresh of decaying articles (< 30 days freshness)
- **11:00 AM** - `auto_new_page`: Automated creation & publication of high-volume keywords (> 500 volume)
- **11:30 AM** - `backlink_prospecting`: 4-module backlink outreach prospecting and qualification
- **12:00 PM** - `seo_report_aeo_tracking`: LLM citation tracking and automated schema markup injection
