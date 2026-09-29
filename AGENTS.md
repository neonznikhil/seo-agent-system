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
