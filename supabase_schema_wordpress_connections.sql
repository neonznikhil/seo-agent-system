-- WordPress 1-click OAuth connections (authorize-application.php flow)
-- Stores encrypted app passwords per user for accident.innovatcs.com
CREATE TABLE IF NOT EXISTS wordpress_connections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id text NOT NULL,
  site_url text NOT NULL,
  wp_username text NOT NULL,
  encrypted_password text NOT NULL,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS idx_wp_connections_user ON wordpress_connections(user_id);
