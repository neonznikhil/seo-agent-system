-- WordPress OAuth Token Storage (real encrypted tokens)
CREATE TABLE IF NOT EXISTS wordpress_oauth_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  website_id UUID REFERENCES websites(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL,
  wp_site_url TEXT NOT NULL,
  client_id TEXT NOT NULL,
  access_token_encrypted TEXT NOT NULL,
  refresh_token_encrypted TEXT,
  token_type TEXT DEFAULT 'Bearer',
  expires_at TIMESTAMPTZ,
  scope TEXT,
  wp_user_id INT,
  wp_user_login TEXT,
  is_connected BOOLEAN DEFAULT true,
  connected_at TIMESTAMPTZ DEFAULT NOW(),
  last_used_at TIMESTAMPTZ,
  UNIQUE(website_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_wp_oauth_tokens_website_user ON wordpress_oauth_tokens(website_id, user_id, is_connected);

ALTER TABLE IF EXISTS websites ADD COLUMN IF NOT EXISTS wp_oauth_connected BOOLEAN DEFAULT false;
