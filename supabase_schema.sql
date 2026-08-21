create extension if not exists vector;

create table if not exists websites (
  id uuid primary key default gen_random_uuid(),
  domain text not null unique,
  cms_url text,
  cms_user text,
  app_password text,
  gsc_property text,
  created_at timestamptz default now()
);

create table if not exists pages (
  id uuid primary key default gen_random_uuid(),
  website_id uuid references websites(id) on delete cascade,
  url text not null,
  title text,
  content_text text,
  embedding vector(1024),
  last_audited timestamptz,
  impressions int default 0,
  ctr float default 0.0,
  created_at timestamptz default now()
);

create table if not exists website_knowledge (
  id uuid primary key default gen_random_uuid(),
  website_id uuid references websites(id) on delete cascade,
  url text,
  title text,
  content_text text,
  embedding vector(1024),
  content_type text check (content_type in ('homepage','about','product','blog')),
  tone_sample text,
  extracted_facts jsonb default '[]'::jsonb,
  crawled_at timestamptz default now()
);

create table if not exists tone_profiles (
  id uuid primary key default gen_random_uuid(),
  website_id uuid references websites(id) on delete cascade unique,
  tone_description text not null,
  writing_style text not null,
  vocabulary jsonb default '[]'::jsonb,
  forbidden_words jsonb default '[]'::jsonb,
  sample_embeddings vector(1024)[],
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists knowledge_base (
  id uuid primary key default gen_random_uuid(),
  website_id uuid references websites(id) on delete cascade,
  fact text not null,
  fact_type text not null check (fact_type in ('product_name','pricing','feature','company_info','tone_rule')),
  source_url text,
  embedding vector(1024),
  created_at timestamptz default now()
);

create table if not exists content_log (
  id uuid primary key default gen_random_uuid(),
  website_id uuid references websites(id) on delete cascade,
  title text not null,
  content text not null,
  status text not null default 'draft' check (status in ('draft_planned','pending_approval','needs_revision','published','failed')),
  keyword text,
  use_case text,
  embedding vector(1024),
  faq_schema jsonb default '{}'::jsonb,
  internal_links jsonb default '[]'::jsonb,
  similarity_score float,
  published_url text,
  created_at timestamptz default now()
);

create table if not exists audits (
  id uuid primary key default gen_random_uuid(),
  website_id uuid references websites(id) on delete cascade,
  page_url text,
  issue_type text not null check (issue_type in ('missing_meta','duplicate_title','low_ctr_title','missing_h1','no_alt','no_internal','missing_canonical','broken_link','redirect_chain','schema_error','noindex_wrong')),
  old_value text,
  new_value text,
  impact_score float,
  status text not null default 'pending_approval' check (status in ('pending_approval','fixed','rejected')),
  created_at timestamptz default now()
);

create table if not exists quality_checks (
  id uuid primary key default gen_random_uuid(),
  content_log_id uuid references content_log(id) on delete cascade,
  website_id uuid references websites(id) on delete cascade,
  spell_check_pass boolean default true,
  spell_errors jsonb default '[]'::jsonb,
  tone_match_score float default 0.0 check (tone_match_score >= 0 and tone_match_score <= 1),
  knowledge_match_pass boolean default true,
  knowledge_errors jsonb default '[]'::jsonb,
  factual_accuracy_pass boolean default true,
  overall_pass boolean default true,
  checked_at timestamptz default now()
);

create table if not exists agent_thoughts (
  id uuid primary key default gen_random_uuid(),
  website_id uuid references websites(id) on delete cascade,
  agent_name text not null,
  thought text not null,
  decision text,
  created_at timestamptz default now()
);

create table if not exists agent_feedback (
  id uuid primary key default gen_random_uuid(),
  website_id uuid references websites(id) on delete cascade,
  agent_name text not null,
  rejected_type text not null,
  rejected_value text,
  human_feedback text not null,
  learning text,
  created_at timestamptz default now()
);

create table if not exists tasks (
  id uuid primary key default gen_random_uuid(),
  website_id uuid references websites(id) on delete cascade,
  agent_name text not null,
  action text not null,
  payload jsonb default '{}'::jsonb,
  result jsonb default '{}'::jsonb,
  status text not null default 'pending' check (status in ('pending','running','success','failed','skipped')),
  real_api_called text check (real_api_called in ('supabase','nim','wordpress','gsc','mock')),
  created_at timestamptz default now()
);

create table if not exists technical_audits (
  id uuid primary key default gen_random_uuid(),
  website_id uuid references websites(id) on delete cascade,
  url text not null,
  issue_type text not null check (issue_type in ('sitemap','robots','canonical','broken_link','redirect_chain','schema','noindex','ssl','performance')),
  severity text not null default 'medium' check (severity in ('high','medium','low')),
  details jsonb default '{}'::jsonb,
  status text not null default 'open' check (status in ('open','fixed','ignored')),
  created_at timestamptz default now()
);

create table if not exists backlinks (
  id uuid primary key default gen_random_uuid(),
  website_id uuid references websites(id) on delete cascade,
  source_url text not null,
  target_url text not null,
  anchor_text text,
  domain_rating int default 0,
  first_seen timestamptz default now(),
  last_seen timestamptz default now(),
  status text not null default 'active' check (status in ('active','lost','toxic')),
  created_at timestamptz default now()
);

create table if not exists llms_txt_log (
  id uuid primary key default gen_random_uuid(),
  website_id uuid references websites(id) on delete cascade,
  content text not null,
  last_updated timestamptz default now(),
  next_due timestamptz default (now() + interval '30 days')
);

create or replace function match_content (
  query_embedding vector(1024),
  match_threshold float,
  p_website_id uuid
) returns table (
  id uuid,
  similarity float
) language sql stable as $$
  select
    id,
    1 - (embedding <=> query_embedding) as similarity
  from content_log
  where website_id = p_website_id
    and 1 - (embedding <=> query_embedding) > match_threshold
  order by similarity desc
  limit 10;
$$;

create or replace function match_pages (
  query_embedding vector(1024),
  match_threshold float,
  p_website_id uuid
) returns table (
  id uuid,
  url text,
  similarity float
) language sql stable as $$
  select
    id,
    url,
    1 - (embedding <=> query_embedding) as similarity
  from pages
  where website_id = p_website_id
    and 1 - (embedding <=> query_embedding) > match_threshold
  order by similarity desc
  limit 20;
$$;

create or replace function match_knowledge (
  query_embedding vector(1024),
  match_threshold float,
  p_website_id uuid
) returns table (
  id uuid,
  fact text,
  similarity float
) language sql stable as $$
  select
    id,
    fact,
    1 - (embedding <=> query_embedding) as similarity
  from knowledge_base
  where website_id = p_website_id
    and 1 - (embedding <=> query_embedding) > match_threshold
  order by similarity desc
  limit 10;
$$;

create index if not exists idx_content_log_embedding on content_log using ivfflat (embedding vector_cosine_ops) with (lists = 100);
create index if not exists idx_pages_embedding on pages using ivfflat (embedding vector_cosine_ops) with (lists = 100);
create index if not exists idx_knowledge_base_embedding on knowledge_base using ivfflat (embedding vector_cosine_ops) with (lists = 100);
create index if not exists idx_website_knowledge_embedding on website_knowledge using ivfflat (embedding vector_cosine_ops) with (lists = 100);
