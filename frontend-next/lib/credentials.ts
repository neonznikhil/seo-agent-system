/**
 * Browser-side connector credential cache.
 *
 * Credentials are still persisted durably on the backend, but users repeatedly
 * had to re-paste NVIDIA / Supabase / WordPress / Serper keys after a reload
 * because the form was never repopulated. This module is the single place the
 * UI reads and writes the local copy, so every connector behaves the same and
 * the legacy `rankforge_wp_credentials` key keeps working.
 */

export interface StoredConnectorCredentials {
  nvidia_api_key?: string;
  supabase_url?: string;
  supabase_anon_key?: string;
  supabase_service_key?: string;
  supabase_db_password?: string;
  wordpress_site_url?: string;
  wordpress_username?: string;
  wordpress_app_password?: string;
  serper_api_key?: string;
  gsc_property_url?: string;
  gsc_credentials_json?: string;
  ga4_property_id?: string;
  ga4_credentials_json?: string;
  slack_webhook_url?: string;
  openai_api_key?: string;
  perplexity_api_key?: string;
}

const STORAGE_KEY = "rankforge_connector_credentials";
const LEGACY_WP_KEY = "rankforge_wp_credentials";

// Mirrors the backend sentinel list (services/connector_credentials.py): a
// username that is blank or an obvious placeholder ("admin", "your-username",
// ...) is never a real WordPress login. Rejecting it here gives the user an
// actionable message instead of a generic "connection failed" after a round-trip.
//
// This list must NEVER contain a real account name. It previously blocklisted
// the owner's own username, which made every genuine save fail client-side
// before the request was even sent.
const PLACEHOLDER_WP_USERNAMES = new Set(
  [
    "", "admin", "administrator", "root", "your-username", "yourusername",
    "your_username", "your name", "yourname", "your_user", "youruser",
    "username", "wp-username", "wp_username", "wpuser", "test", "testuser",
    "demo", "example", "exampleuser", "user@example.com", "you@example.com",
  ].map((n) => n.trim().toLowerCase().replace(/[-_. ]/g, ""))
);

function normalizeWpUsername(username: string): string {
  return username.trim().toLowerCase().replace(/[-_. ]/g, "");
}

export function isPlaceholderWordPressUsername(username: string | undefined | null): boolean {
  return PLACEHOLDER_WP_USERNAMES.has(normalizeWpUsername(username || ""));
}

function isBrowser(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function readJson(key: string): any {
  if (!isBrowser()) return null;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/** Load the cached credentials, folding in the legacy WordPress-only key. */
export function loadConnectorCredentials(): StoredConnectorCredentials {
  const stored = readJson(STORAGE_KEY) || {};
  const legacy = readJson(LEGACY_WP_KEY) || {};

  const merged: StoredConnectorCredentials = { ...stored };
  if (!merged.wordpress_site_url && legacy.site_url) {
    merged.wordpress_site_url = legacy.site_url;
  }
  if (!merged.wordpress_username && legacy.username) {
    merged.wordpress_username = legacy.username;
  }
  // Never resurrect a legacy plaintext password; the backend holds the secret.
  return merged;
}

/**
 * Merge and persist credentials. Empty/undefined values are ignored so a partial
 * save never erases a previously stored field.
 */
export function saveConnectorCredentials(
  partial: StoredConnectorCredentials
): StoredConnectorCredentials {
  const current = loadConnectorCredentials();
  const incoming: StoredConnectorCredentials = {};
  (Object.keys(partial) as (keyof StoredConnectorCredentials)[]).forEach((key) => {
    const value = partial[key];
    if (typeof value === "string" && value.trim() !== "") {
      incoming[key] = value.trim();
    }
  });
  const merged = { ...current, ...incoming };

  if (isBrowser()) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
    } catch {
      // Storage full or blocked (private mode): non-fatal, backend still has it.
    }
  }
  return merged;
}

export function clearConnectorCredentials(): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
    window.localStorage.removeItem(LEGACY_WP_KEY);
  } catch {
    // ignore
  }
}
