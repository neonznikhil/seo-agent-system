-- WordPress OAuth tokens table
-- Run this in Supabase SQL Editor after the main schema

create table if not exists wordpress_oauth_tokens (
  id uuid primary key default gen_random_uuid(),
  website_id uuid references websites(id) on delete cascade,
  access_token text not null,
  refresh_token text,
  token_type text default 'Bearer',
  expires_at timestamptz,
  scope text,
  provider text default 'wordpress',
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique(website_id, provider)
);

create index if not exists idx_wordpress_oauth_tokens_website_id on wordpress_oauth_tokens(website_id);
