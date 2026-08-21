alter table if exists websites alter column id set default gen_random_uuid();
alter table if exists pages alter column id set default gen_random_uuid();
alter table if exists website_knowledge alter column id set default gen_random_uuid();
alter table if exists tone_profiles alter column id set default gen_random_uuid();
alter table if exists knowledge_base alter column id set default gen_random_uuid();
alter table if exists content_log alter column id set default gen_random_uuid();
alter table if exists audits alter column id set default gen_random_uuid();
alter table if exists quality_checks alter column id set default gen_random_uuid();
alter table if exists agent_thoughts alter column id set default gen_random_uuid();
alter table if exists agent_feedback alter column id set default gen_random_uuid();
alter table if exists tasks alter column id set default gen_random_uuid();
alter table if exists technical_audits alter column id set default gen_random_uuid();
alter table if exists backlinks alter column id set default gen_random_uuid();
alter table if exists llms_txt_log alter column id set default gen_random_uuid();
alter table if exists critical_action_logs alter column id set default gen_random_uuid();

alter table if exists content_log add column if not exists human_user_id text;
alter table if exists content_log add column if not exists approval_timestamp timestamptz;
alter table if exists audits add column if not exists human_user_id text;
alter table if exists audits add column if not exists approval_timestamp timestamptz;

alter table if exists content_log add column if not exists keyword text;
alter table if exists content_log add column if not exists use_case text;
alter table if exists content_log add column if not exists published_url text;

alter table if exists quality_checks add column if not exists spell_errors jsonb default '[]'::jsonb;
alter table if exists quality_checks add column if not exists knowledge_errors jsonb default '[]'::jsonb;
alter table if exists quality_checks add column if not exists factual_accuracy_pass boolean default true;

alter table if exists agent_thoughts add column if not exists agent_name text;
alter table if exists agent_thoughts add column if not exists decision text;

alter table if exists agent_feedback add column if not exists agent_name text;

alter table if exists tasks add column if not exists agent_name text;
alter table if exists tasks add column if not exists payload jsonb default '{}'::jsonb;
alter table if exists tasks add column if not exists result jsonb default '{}'::jsonb;
alter table if exists tasks add column if not exists real_api_called text;

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

create table if not exists critical_action_logs (
  id uuid default gen_random_uuid() primary key,
  website_id uuid references websites(id),
  agent_name text,
  action_type text,
  attempted_at timestamptz,
  blocked boolean,
  block_reason text,
  status_before text,
  approved_by text,
  created_at timestamptz
);

create index if not exists idx_critical_logs_website on critical_action_logs(website_id);
create index if not exists idx_critical_logs_blocked on critical_action_logs(blocked);
create index if not exists idx_critical_logs_action on critical_action_logs(action_type);
