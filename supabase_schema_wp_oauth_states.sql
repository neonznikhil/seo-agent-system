-- Temporary OAuth states for WordPress authorize-application.php flow
CREATE TABLE IF NOT EXISTS wp_oauth_states (
  state text PRIMARY KEY,
  user_id text NOT NULL,
  site_url text NOT NULL,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wp_oauth_states_user ON wp_oauth_states(user_id);
