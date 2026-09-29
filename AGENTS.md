# AGENTS.md

## Architecture
- `backend/` — FastAPI app (`main:app`). Run: `cd backend && uvicorn main:app --host 127.0.0.1 --port 8000`.
- `frontend-next/` — Next.js app. All browser API calls go through the same-origin
  Next proxy (`frontend-next/app/api/_lib/proxy.ts`, base URL `BACKEND_URL`), never
  directly to the backend, so CORS cannot break connectors. `lib/api.ts buildUrl()`
  returns a same-origin `/api/...` path in the browser.

## Durable-degradation pattern (important)
Every endpoint that reads from Supabase must wrap the read in try/except and fall
back to a local durable store instead of raising a 500. The sandbox has no real
Supabase, so a raw `.table(...).execute()` call 500s. Precedent:
`backend/routers/memory.py`, `backend/routers/decay.py`, `backend/routers/content.py`,
`backend/main.py get_blogs`, `backend/wordpress_oauth.py`, `backend/services/internal_link_service.py`.

## Error classification (500 vs 503)
`backend/utils/errors.py` is the single source of truth:
- `is_connectivity_error(exc)` — true for `ConnectError`, DNS failures
  ("name or service not known"), timeouts, connection refused/reset.
- `raise_db_or_500(exc, fallback_detail)` — raise a retryable **503** with
  `Retry-After` when the dependency is unreachable, else a 500.
- `main.py` has a global `Exception` handler and a `FastAPIHTTPException`
  handler that both reclassify connectivity-caused failures into 503. Routes
  that wrap DB errors in `HTTPException(500, ...)` are reclassified automatically,
  so a DB outage never shows up as an opaque 500.

## Read helpers
`backend/utils/safe_query.py` (`safe_rows`, `safe_value`) must be used for any
Supabase read that isn't already try/except-guarded. Note the Supabase Python
client exposes `is_(col, "null")`, **not** `isnull(col)`.

## Optional dependencies
`crawlee` is optional. Code that imports it must guard with `except ImportError` and
use a dependency-free fallback (see `_crawl_pages_fallback` in
`backend/services/internal_link_service.py`).

## WordPress credentials
- `PLACEHOLDER_WP_USERNAMES` / `is_placeholder_wp_username()` / `resolve_wp_username()`
  live in `backend/services/connector_credentials.py`. `admin` is a placeholder and
  must be rejected — never invent a fallback username.
- Placeholder/invalid credentials return HTTP 400 with an actionable message.

## Browser credential cache
`frontend-next/lib/credentials.ts` persists connector credentials to `localStorage`
(`StoredConnectorCredentials`, `saveConnectorCredentials`, `loadConnectorCredentials`).
Handlers must call `saveConnectorCredentials` **before** the network call so an
unreachable backend never loses the user's typed credentials. Legacy key
`rankforge_wp_credentials` is preserved for backward compatibility.

## Testing
- Backend: `cd backend && python -m pytest tests/ -q` (requires JWT_SECRET,
  ENCRYPTION_KEY, SUPABASE_URL, SUPABASE_KEY, TESTING=1).
- Frontend: `cd frontend-next && npx tsc --noEmit && npm run build`.
- Connector tests that hit NVIDIA/Supabase/Serper live endpoints fail without real
  credentials; that is expected in the sandbox.

## Background jobs
- **Every** detached task must go through `backend/utils/job_queue.py`:
  `spawn_background(coro, name=...)` keeps a strong reference and logs the real
  exception. Never use bare `asyncio.create_task` (it can be GC'd and swallows errors).
- Durable jobs use `register_job(kind, payload, job_id=...)` + `mark_running/done/failed`.
  The queue lives at `data/background_jobs.json` (git-ignored) and is re-dispatched on
  startup from `backend/main.py` lifespan (`_recover_interrupted_jobs`).
- Single scheduler authority: `backend/agents/scheduler.py` `AsyncIOScheduler`.
  `start_all_monitors()` is idempotent — do not remove the guard (it was previously
  double-registering 12 monitor loops instead of 6).
- Connecting a website (`POST /api/websites`) fires `dispatch_onboarding`
  (`agents.scheduler`) → the first-time setup pipeline (KB crawl → research → first
  article → tech audit → backlinks), plus a default auto-blog schedule for WordPress
  sites. Idempotent per website id.
- Logging is configured once in `backend/main.py` via `logging.basicConfig`
  (`LOG_LEVEL` env, default INFO). Without it, background-job `logger.info` output is
  invisible because the root logger defaults to WARNING.

## Network resilience (Supabase / LLM outages)
The first-article pipeline (`agents/writer_agent.py`) previously **aborted whenever a
single Supabase call failed** — a DNS blip discarded a fully-planned article. Rules:
- Telemetry writes (`content_pipeline_logs`, `content_expert_reviews`, `content_log`
  updates) are best-effort: wrap in try/except and log at debug. They must never raise.
- Reads that feed generation (`_fetch_website_knowledge`, `_fetch_knowledge_base`,
  `_fetch_gsc_keywords`) degrade gracefully: catch the error, fall back to the
  local store (`services/local_store.py`), and return an empty list if all fail.
- Any local-store fallback must be **outside** the remote `try/except`; if it sits
  inside the same try block, an exception jumps past it and the fallback never runs
  (this exact bug existed in `agents/aeo_agent.generate_and_inject_schema`).
- `WriterPipeline(website_id=...)` takes **only** `website_id`; `topic` and
  `primary_keyword` are arguments to `await generate(...)`. Passing `topic` to the
  constructor raises `TypeError` (this silently killed onboarding article generation).

## Sanitization
- `backend/security.py::sanitize_html` uses `bleach.clean(..., css_sanitizer=CSSSanitizer(...))`
  on bleach 6.x (the old `styles=` kwarg is gone). A regex fallback strips
  `script/iframe/object/embed/applet/style/svg`, `on*` handlers and `javascript:` URIs.
- `ALLOWED_HTML_TAGS` must never contain `script`, `style`, `svg` or `path` — bleach
  only removes *disallowed* tags, so listing them lets XSS through.
- `backend/middleware/sanitize_response.py` sanitizes **only** keys in
  `HTML_FIELD_NAMES`; do not sanitize every HTML-looking string (it corrupts diffs
  and code payloads).
