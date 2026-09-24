# RankForge — agent notes

## Layout
- `backend/` FastAPI app. `main.py` mounts ~40 routers under `/api`.
- `frontend-next/` Next.js app. Pages under `app/`, shared components in `components/`.
- Run backend: `JWT_SECRET=... ENCRYPTION_KEY=... python -m uvicorn main:app --port 8000`
- Run frontend: `npm run dev` (port 3000). It calls the API at port 8000.
- Tests: `python tests/test_intelligence_e2e.py http://127.0.0.1:8000` (needs a running backend).

## Portfolio intelligence (the 6 capabilities)
Backend: `routers/intelligence.py`, `services/intelligence_service.py`,
`services/intelligence_store.py`, `services/conversion_intelligence_service.py`.
Tables: `action_items`, `change_events`, `competitor_rankings`, `competitor_new_pages`,
`conversions`, `effort_costs`, `keyword_lead_attribution`, `measurement_snapshots`,
`measurement_windows`, `site_metrics_daily`, `sov_snapshots`, `ymyl_classifications`.

Frontend: `/portfolio`, `/actions`, `/competitors`, `/guardrails`, `/proof`;
`lib/intelligence.ts` + the matching `components/*Panel.tsx`.

Hard rule: **never invent data**. With no stored rows the endpoints return empty
arrays and a `note` / `has_data:false`, and the UI renders "not connected" or "—".
`test_intelligence_e2e.py` asserts this. Do not add fallback sample values.

## Known gap: nothing ingests real per-site metrics
`action_items` and `site_metrics_daily` are the shape the capabilities read, but no
collector writes to them. Real GSC/SERP data lands in different places:

| Real data | Written to | Capability that needs it |
|---|---|---|
| GSC per-query clicks/impressions/position | `gsc_keywords` | `/actions` volume+position, `/proof`, competitor gaps |
| Indexation runs | `indexation_checks` (`submitted_pages`, `indexed_pages`) | `/portfolio` indexation column, `site_metrics_daily` |
| Competitor SERP positions | nothing persistent (fetched on demand via Serper) | `competitor_rankings` |
| GA4 conversions | nothing yet (`conversion_intelligence_service` reads `conversions`) | `/actions` CPL, `/proof` leads |

So the capabilities are correct and honest but currently render empty on a fresh
install. Closing this is a read-mapping / scheduler job, not a rewrite of the
services. `agents/scheduler.py` already has ~12 APScheduler jobs (incl.
`job_indexation_check`) — an ingestion job belongs alongside them. Note the
indexation job writes via Supabase only, so it needs a local-store path too.

## Pitfalls hit before
- `middleware/cors.py` must import `ALLOWED_CORS_ORIGINS` from `config`. Reading the
  env var directly allows no origin when it is unset, which blocks the whole UI.
- `routers/websites.py` `list_websites`: `get_supabase()` raises without credentials,
  so resolve it inside the `try` or a no-Supabase deploy 500s instead of falling back
  to `services/local_store.py`.
- `local_json` storage lives in `data/intelligence_store.json`; `data/` is gitignored.
- Tests / `measurement` endpoints are POST for `leads/cpl`, `guardrails/preview`,
  `guardrails/changes/{id}/apply|undo`; GET for the rest.
