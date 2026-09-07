# Security & Key Rotation Checklist

For the CTO review. All `.env` files are git-ignored (verified with
`git check-ignore`) and Render env vars use `sync: false`, so secrets only
live in: local `.env`, the Render dashboard, and Supabase dashboard.

## Rotate immediately (do once, then yearly)

- [ ] **Supabase keys** — Dashboard → Project Settings → API → generate new
      `anon` + `service_role` keys. Update root `.env`
      (`SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`) and the same keys in the
      Render dashboard. Old keys in shell history / backups count as exposed.
- [ ] **WordPress application password** — WP Admin → Users → Profile →
      Application Passwords → revoke old, add new. Update `.env`
      (`WORDPRESS_APP_PASSWORD`) + Render.
- [ ] **NVIDIA NIM key** — build.nvidia.com → revoke + regenerate. Update
      `.env` (`NVIDIA_API_KEY`) + Render.
- [ ] **Serper / Tavily keys** — same flow as above.
- [ ] **JWT_SECRET + ENCRYPTION_KEY** — generate fresh random 64-char values
      per environment. WARNING: rotating `ENCRYPTION_KEY` invalidates stored
      WordPress passwords encrypted with the old key — re-save WP connections
      in the UI afterwards.

## Steady state

- [ ] RLS migration applied (`supabase_migration_rls.sql`) — anon key is
      deny-by-default; confirm no app flow depends on direct anon writes.
- [ ] Nightly `backend/scripts/backup_supabase.py` scheduled (Task
      Scheduler / cron), retention 14 verified.
- [ ] `BUDGET_THRESHOLD_USD` set in production env (default 150.0).
- [ ] Render health check path `/health` alarming configured.
- [ ] Never `git add -f` an `.env` file; never paste keys into issues/logs.
