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

## Datetime arithmetic (naive vs aware)
Supabase `created_at` values are stored ISO strings. When converting with
`datetime.fromisoformat`, **keep the offset** (`.replace("Z", "+00:00")` only).
Callers subtract the result from `datetime.now(timezone.utc)`; a `.replace(tzinfo=None)`
made it naive and raised `TypeError: can't subtract offset-naive and offset-aware
datetimes`, which surfaced as a 500 on `GET /api/autonomous/blog-settings`.
`agents/scheduler.py::get_last_blog_time` returns aware datetimes; keep caller-side
`if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)` guards for safety.

## Embedding dimensions (knowledge_base)
`knowledge_base.embedding` is `vector(1024)` but NVIDIA NIM returns 1536-dim
vectors. Always route writes through `_adapt_embedding_1024()` before an insert or
update, or Postgres rejects the row with code `22000` ("expected 1024 dimensions,
not 1536"). This bit `POST /api/knowledge/reindex` and the crawl/ingest paths.

## knowledge_base has no `type` column
The fact classifier column is **`fact_type`**, not `type` (values: `product_name`,
`pricing`, `feature`, `company_info`, `tone_rule`; legacy `business_info` maps to
`company_info`). Querying `.eq("type", ...)` fails with Postgres `42703`
("column knowledge_base.type does not exist") and the caller silently swallowed
it — this disabled knowledge auto-consolidation. Grep for `.eq("type"` against
`knowledge_base` when touching that table.

## Duplicate route prefixes are harmless
Routers declare both `/api/x` and `/x` decorators and `main.py` adds
`prefix="/api"`, so `/api/api/x` also resolves. This is aliasing, not a bug —
don't "fix" it by removing decorators without checking the frontend's `buildUrl`.

## Next.js dynamic segments shadow the catch-all proxy
`app/api/[...slug]/route.ts` only sees paths with **no** other matching route.
A dynamic folder such as `app/api/websites/[id]/route.ts` captures every
`/api/websites/<anything>` path — including backend aliases like
`/api/websites/create` and `/api/websites/list`. If the dynamic route exports
only `GET`, those aliases get Next's automatic **405 Method Not Allowed**
instead of reaching the backend. When adding a backend alias under an existing
dynamic segment, export the matching HTTP methods in the `[id]` handler too.
This was the second "create website 405" (distinct from the missing `POST` on
`app/api/websites/route.ts`).

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

## Generation liveness (do not fail a slow run)
`/api/crew/status/{blog_id}` must distinguish a dead run from a slow one by
**liveness**, never by age alone. A valid NIM run can take 45+ minutes when the
model is cold or shared, so an age-only "stale" check falsely flipped a running
job to `failed/stalled`.
- `backend/services/local_store.py` exports `mark_run_active`, `mark_run_finished`,
  `is_run_active`. `generate_blog_autonomous` wraps its body with these markers, so
  every call path (router, direct, self-healing retry) is covered.
- `crew_status` only reports `failed/stalled` for a `generating` row when
  `is_run_active()` is false **and** the row is older than 45 min with no content.
- A generation started before a backend restart has no liveness marker, so the age
  fallback still surfaces it as failed instead of spinning forever.
- A generation that **raises** must be written to the store as `failed`
  (`routers/crew_writer.py::_run_generation` catches the exception and calls
  `save_local_content`). Publishing a failure event alone is not enough: the
  placeholder row kept `generating/running` on disk and listings advertised a dead
  run forever, while only `/crew/status` masked it via the age check.
  Regression: `tests/test_durable_persistence.py::test_failed_generation_is_persisted_as_failed`.

## Connector proxy timeouts must exceed the upstream budget
Next route handlers under `frontend-next/app/api/connectors/` abort with
`AbortSignal.timeout(...)`/`proxyToBackend(..., TIMEOUT_MS)`. That budget must be
**larger** than the backend's own upstream call, or the proxy aborts first and
reports a false failure at the exact moment the user clicks Connect.
- NVIDIA NIM validation allows 45s in `routers/connectors.py::verify_nvidia_key`,
  so `app/api/connectors/test-nvidia/route.ts` uses 70s (20s caused false
  "NIM validation timed out" for valid keys).

## WordPress publish config resolution (tests)
`WordPressService.publish_post_via_crew` re-resolves the site via
`self._get_site_config()` rather than using `self.site`, so a test that only sets
`svc.site = {...}` sees "credentials not configured". Patch `_get_site_config`
(see `tests/test_wp_draft_fix.py`).

## Sanitization
- `backend/security.py::sanitize_html` uses `bleach.clean(..., css_sanitizer=CSSSanitizer(...))`
  on bleach 6.x (the old `styles=` kwarg is gone). A regex fallback strips
  `script/iframe/object/embed/applet/style/svg`, `on*` handlers and `javascript:` URIs.
- `ALLOWED_HTML_TAGS` must never contain `script`, `style`, `svg` or `path` — bleach
  only removes *disallowed* tags, so listing them lets XSS through.
- `backend/middleware/sanitize_response.py` sanitizes **only** keys in
  `HTML_FIELD_NAMES`; do not sanitize every HTML-looking string (it corrupts diffs
  and code payloads).

## Supabase status honesty
`GET /api/connectors/status` must never infer success from the mere *presence* of a
key. A failed live query is `connected: false`; placeholder values
(`example.supabase.co`, `dummy`, `mock-key`, `your-supabase-service-role-key`) set
`placeholder: true` and `is_configured: false`. The old `except: connected = bool(SUPABASE_KEY)`
reported a healthy Supabase while every real write silently failed.
- The Supabase **URL alone is not a credential** — the project needs the `anon` or
  `service_role` key. Configure via `POST /api/connectors/setup-supabase`
  (`connect_and_setup`: URL + anon_key + service_key + db_password → writes `.env`,
  creates tables, pgvector + match RPCs).
- A shell-exported `SUPABASE_URL` overrides `.env` (python-dotenv does not override
  existing env). If status shows the wrong URL, check `env | grep SUPABASE` before
  restarting the backend.
