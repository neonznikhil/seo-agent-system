-- RankForge schema v4: portfolio intelligence, prioritized actions, lead
-- attribution, guardrails/rollback, competitor share of voice, and 28-day
-- lift measurement. Extends the existing websites/content_log/etc. tables.

-- ---------------------------------------------------------------------------
-- Bullet 1: multi-site portfolio
-- ---------------------------------------------------------------------------
create table if not exists site_metrics_daily (
  id uuid primary key default gen_random_uuid(),
  website_id uuid not null references websites(id) on delete cascade,
  metric_date date not null,
  indexed_pages int,
  excluded_pages int,
  errors int,
  clicks int,
  impressions int,
  avg_position float,
  open_issues int,
  critical_issues int,
  health_score int,
  source text not null default 'gsc',
  collected_at timestamptz default now(),
  unique (website_id, metric_date, source)
);
create index if not exists idx_site_metrics_daily_site_date
  on site_metrics_daily(website_id, metric_date desc);

-- ---------------------------------------------------------------------------
-- Bullet 2: prioritized action list
-- ---------------------------------------------------------------------------
create table if not exists action_items (
  id uuid primary key default gen_random_uuid(),
  website_id uuid not null references websites(id) on delete cascade,
  category text not null,
  title text not null,
  target_url text,
  keyword text,
  search_volume int,
  current_position float,
  target_position float,
  projected_ctr_gain float,
  projected_clicks_gain float,
  effort_minutes int not null default 30,
  confidence float not null default 0.6,
  priority_score float not null default 0,
  -- full arithmetic so the UI can prove the ranking, never a bare number
  evidence jsonb not null default '{}'::jsonb,
  source text not null default 'derived',
  status text not null default 'open',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create index if not exists idx_action_items_site_score
  on action_items(website_id, priority_score desc);
create index if not exists idx_action_items_status on action_items(status);

-- ---------------------------------------------------------------------------
-- Bullet 3: leads / cost per lead by keyword
-- ---------------------------------------------------------------------------
create table if not exists conversions (
  id uuid primary key default gen_random_uuid(),
  website_id uuid not null references websites(id) on delete cascade,
  conversion_date date not null,
  landing_page text not null,
  session_source text,
  conversion_count int not null default 0,
  conversion_value float not null default 0,
  source text not null default 'ga4',
  collected_at timestamptz default now(),
  unique (website_id, conversion_date, landing_page, session_source, source)
);
create index if not exists idx_conversions_site_date
  on conversions(website_id, conversion_date desc);

create table if not exists keyword_lead_attribution (
  id uuid primary key default gen_random_uuid(),
  website_id uuid not null references websites(id) on delete cascade,
  keyword text not null,
  landing_page text not null,
  period_start date not null,
  period_end date not null,
  clicks int not null default 0,
  leads int not null default 0,
  conversion_rate float,
  -- organic has no ad spend; this is production effort cost, not media spend
  effort_cost float not null default 0,
  cost_per_lead float,
  -- GA4 cannot bind organic conversions to keywords; we state how we derived it
  attribution_method text not null default 'landing_page_join',
  attribution_confidence float not null default 0.0,
  created_at timestamptz default now(),
  unique (website_id, keyword, landing_page, period_start, period_end)
);
create index if not exists idx_kla_site_period
  on keyword_lead_attribution(website_id, period_start desc);

-- ---------------------------------------------------------------------------
-- Bullet 4: guardrails and rollback
-- ---------------------------------------------------------------------------
create table if not exists change_events (
  id uuid primary key default gen_random_uuid(),
  website_id uuid not null references websites(id) on delete cascade,
  target_url text not null,
  change_type text not null,
  actor text not null default 'system',
  -- preview payload; never applied until apply_change is called
  before_content text,
  after_content text,
  unified_diff text,
  -- inverse patch used by undo
  inverse_payload jsonb not null default '{}'::jsonb,
  reversible boolean not null default true,
  is_ymyl boolean not null default false,
  ymyl_reason text,
  review_required boolean not null default false,
  second_reviewer text,
  status text not null default 'previewed',
  applied_at timestamptz,
  undone_at timestamptz,
  external_revision_id text,
  created_at timestamptz default now()
);
create index if not exists idx_change_events_site
  on change_events(website_id, created_at desc);
create index if not exists idx_change_events_status on change_events(status);

-- ---------------------------------------------------------------------------
-- Bullet 5: competitor share of voice
-- ---------------------------------------------------------------------------
create table if not exists competitor_rankings (
  id uuid primary key default gen_random_uuid(),
  website_id uuid not null references websites(id) on delete cascade,
  competitor_domain text not null,
  keyword text not null,
  position int,
  url text,
  captured_date date not null,
  source text not null default 'serp',
  created_at timestamptz default now(),
  unique (website_id, competitor_domain, keyword, captured_date, source)
);
create index if not exists idx_comp_rankings_site_date
  on competitor_rankings(website_id, captured_date desc);

create table if not exists competitor_new_pages (
  id uuid primary key default gen_random_uuid(),
  website_id uuid not null references websites(id) on delete cascade,
  competitor_domain text not null,
  url text not null,
  first_seen date not null,
  title text,
  created_at timestamptz default now(),
  unique (website_id, competitor_domain, url)
);

create table if not exists sov_snapshots (
  id uuid primary key default gen_random_uuid(),
  website_id uuid not null references websites(id) on delete cascade,
  snapshot_date date not null,
  scope text not null default 'tracked_keyword_set',
  our_visibility float not null default 0,
  total_visibility float not null default 0,
  share_of_voice float not null default 0,
  per_competitor jsonb not null default '{}'::jsonb,
  keyword_count int not null default 0,
  created_at timestamptz default now(),
  unique (website_id, snapshot_date, scope)
);

-- ---------------------------------------------------------------------------
-- Bullet 6: prove the work (28-day lift)
-- ---------------------------------------------------------------------------
create table if not exists measurement_windows (
  id uuid primary key default gen_random_uuid(),
  website_id uuid not null references websites(id) on delete cascade,
  change_event_id uuid references change_events(id) on delete set null,
  target_url text not null,
  keyword text,
  window_start date not null,
  baseline_clicks float not null default 0,
  baseline_impressions float not null default 0,
  baseline_position float,
  -- control set discounts seasonality; raw before/after overclaims
  control_urls jsonb not null default '[]'::jsonb,
  baseline_control_clicks float not null default 0,
  status text not null default 'open',
  created_at timestamptz default now()
);
create index if not exists idx_mw_site_status
  on measurement_windows(website_id, status, window_start);

create table if not exists measurement_snapshots (
  id uuid primary key default gen_random_uuid(),
  window_id uuid not null references measurement_windows(id) on delete cascade,
  day_offset int not null,
  clicks float not null default 0,
  impressions float not null default 0,
  position float,
  control_clicks float not null default 0,
  control_impressions float not null default 0,
  captured_date date not null,
  created_at timestamptz default now(),
  unique (window_id, day_offset)
);

-- ---------------------------------------------------------------------------
-- Cost accounting used by CPL (production effort, not media spend)
-- ---------------------------------------------------------------------------
create table if not exists effort_costs (
  id uuid primary key default gen_random_uuid(),
  website_id uuid not null references websites(id) on delete cascade,
  cost_date date not null,
  category text not null,
  minutes float not null default 0,
  hourly_rate float not null default 0,
  api_cost float not null default 0,
  total_cost float not null default 0,
  created_at timestamptz default now(),
  unique (website_id, cost_date, category)
);

create table if not exists ymyl_classifications (
  id uuid primary key default gen_random_uuid(),
  website_id uuid not null references websites(id) on delete cascade,
  url_pattern text not null,
  is_ymyl boolean not null default false,
  category text,
  reason text,
  created_at timestamptz default now(),
  unique (website_id, url_pattern)
);
