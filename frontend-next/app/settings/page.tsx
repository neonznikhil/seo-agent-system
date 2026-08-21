"use client";

import { useEffect, useState } from "react";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface Website {
  id: string;
  domain: string;
  cms_url: string | null;
  cms_user: string | null;
  app_password: string | null;
  gsc_property: string | null;
  status: string;
  oauth_enabled?: boolean;
  wp_oauth_connected?: boolean;
}

interface SettingsConfig {
  website_id: string;
  cms_url: string | null;
  cms_user: string | null;
  gsc_property: string | null;
  auto_publish: boolean;
  human_approval_required: boolean;
  max_daily_posts: number;
}

interface OAuthStatus {
  connected: boolean;
  reason?: string;
  needs_reconnect?: boolean;
  wp_site_url?: string;
  wp_user_login?: string;
  expires_at?: string;
  last_used_at?: string;
}

export default function SettingsPage() {
  const [websites, setWebsites] = useState<Website[]>([]);
  const [config, setConfig] = useState<SettingsConfig>({
    website_id: "",
    cms_url: null,
    cms_user: null,
    gsc_property: null,
    auto_publish: false,
    human_approval_required: true,
    max_daily_posts: 3,
  });
  const [selectedWebsite, setSelectedWebsite] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [oauthStatus, setOauthStatus] = useState<OAuthStatus | null>(null);
  const [testingOAuth, setTestingOAuth] = useState(false);
  const [publishingTest, setPublishingTest] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const wpConnected = params.get("wp_connected");
    const wpError = params.get("wp_error");
    const wpUser = params.get("wp_user");

    if (wpConnected === "1" && wpUser) {
      setSuccess(`Connected to WordPress as ${decodeURIComponent(wpUser)}`);
      window.history.replaceState({}, "", "/settings");
    }
    if (wpError) {
      setError(`WordPress OAuth failed: ${decodeURIComponent(wpError)} - Check WP OAuth Server plugin installed + Redirect URI matches`);
      window.history.replaceState({}, "", "/settings");
    }
  }, []);

  useEffect(() => {
    async function fetchSettings() {
      try {
        setLoading(true);
        const websitesData = await get("/websites");
        const sites = websitesData?.data || websitesData || [];
        setWebsites(Array.isArray(sites) ? sites : []);
        if (sites.length > 0) {
          const site = sites[0];
          setSelectedWebsite(site.id);
          setConfig((prev) => ({
            ...prev,
            website_id: site.id,
            cms_url: site.cms_url,
            cms_user: site.cms_user,
          }));
        }
        setError(null);
      } catch (e) {
        setError("Backend not running - run uvicorn main:app --reload in backend");
        setWebsites([]);
      } finally {
        setLoading(false);
      }
    }

    fetchSettings();
  }, []);

  useEffect(() => {
    if (selectedWebsite) {
      checkOAuthStatus();
    }
  }, [selectedWebsite]);

  const checkOAuthStatus = async () => {
    if (!selectedWebsite) return;
    try {
      const data = await get(`/wordpress/oauth/status/${selectedWebsite}`);
      setOauthStatus(data || null);
    } catch (e) {
      setOauthStatus(null);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      setError(null);
      setSuccess(null);
      await post(`/settings/website/${config.website_id}`, config);
      setSuccess("Settings saved successfully");
    } catch (e: any) {
      setError(e.message || "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleWebsiteChange = (id: string) => {
    setSelectedWebsite(id);
    const site = websites.find((w) => w.id === id);
    if (site) {
      setConfig((prev) => ({
        ...prev,
        website_id: site.id,
        cms_url: site.cms_url,
        cms_user: site.cms_user,
      }));
    }
  };

  const handleOAuthConnect = async () => {
    if (!selectedWebsite) return;
    try {
      setTestingOAuth(true);
      setError(null);
      const data = await get(`/wordpress/oauth/authorize?website_id=${selectedWebsite}`);
      if (data?.authorize_url) {
        window.location.href = data.authorize_url;
      } else {
        setError("Failed to get OAuth authorization URL");
      }
    } catch (e: any) {
      setError(e.message || "Failed to initiate OAuth");
    } finally {
      setTestingOAuth(false);
    }
  };

  const handleOAuthDisconnect = async () => {
    if (!selectedWebsite) return;
    try {
      await post(`/wordpress/oauth/disconnect/${selectedWebsite}`, {});
      setOauthStatus({ connected: false, reason: "Not connected - Click Connect WordPress OAuth" });
      setSuccess("WordPress OAuth disconnected");
    } catch (e: any) {
      setError(e.message || "Failed to disconnect OAuth");
    }
  };

  const handleTestConnection = async () => {
    if (!selectedWebsite) return;
    try {
      setTestingOAuth(true);
      await checkOAuthStatus();
      if (oauthStatus?.connected) {
        setSuccess(`Connection verified - Connected as ${oauthStatus.wp_user_login} to ${oauthStatus.wp_site_url}`);
      }
    } catch (e: any) {
      setError(e.message || "Connection test failed");
    } finally {
      setTestingOAuth(false);
    }
  };

  const handlePublishTest = async () => {
    if (!selectedWebsite) return;
    try {
      setPublishingTest(true);
      setError(null);
      const result = await post(`/wordpress/oauth/publish/${selectedWebsite}`, {
        title: "RANKFORGE OAuth Test",
        content_html: "<p>Real OAuth test from RANKFORGE - this is a test post.</p>",
        status: "draft",
      });
      setSuccess(`Test post created: ${result.wp_url} (ID: ${result.wp_post_id})`);
    } catch (e: any) {
      setError(e.message || "Failed to publish test post");
    } finally {
      setPublishingTest(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2 text-[11px] text-muted">
          <span className="w-2 h-2 bg-accent" />
          <span>Settings</span>
        </div>
        <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">Settings</h1>
        <div className="bg-stone border border-ink p-4 space-y-4">
          {[...Array(4)].map((_, i) => (
            <div key={i}>
              <div className="h-3 bg-line animate-pulse w-24 mb-2" />
              <div className="h-10 bg-line animate-pulse" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2 text-[11px] text-muted">
          <span className="w-2 h-2 bg-accent" />
          <span>Settings</span>
        </div>
        <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">Settings</h1>
        <div className="bg-stone border border-ink p-4">
          <div className="text-[11px] mono-font">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-[11px] text-muted">
        <span className="w-2 h-2 bg-accent" />
        <span>Settings</span>
      </div>
      <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">Settings</h1>

      <form onSubmit={handleSave} className="space-y-6">
        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Website</div>
          <div className="space-y-3">
            <div>
              <label className="text-[10px] text-muted uppercase tracking-wider mono-font block mb-1">Website</label>
              <select
                value={selectedWebsite}
                onChange={(e) => handleWebsiteChange(e.target.value)}
                className="field w-full"
              >
                {websites.length === 0 ? (
                  <option value="">No websites connected</option>
                ) : (
                  websites.map((site) => (
                    <option key={site.id} value={site.id}>{site.domain}</option>
                  ))
                )}
              </select>
            </div>
            <div>
              <label className="text-[10px] text-muted uppercase tracking-wider mono-font block mb-1">CMS URL</label>
              <input
                type="text"
                className="field w-full"
                value={config.cms_url || ""}
                onChange={(e) => setConfig({ ...config, cms_url: e.target.value || null })}
                placeholder="https://yourwp.com"
              />
            </div>
            <div>
              <label className="text-[10px] text-muted uppercase tracking-wider mono-font block mb-1">GSC Property</label>
              <input
                type="text"
                className="field w-full"
                value={config.gsc_property || ""}
                onChange={(e) => setConfig({ ...config, gsc_property: e.target.value || null })}
                placeholder="https://search.google.com/search-console"
              />
            </div>
          </div>
        </div>

        {/* WordPress OAuth Section */}
        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">WordPress OAuth</div>
          <div className="space-y-3">
            {oauthStatus?.connected ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 bg-green-500 rounded-full" />
                    <div className="mono-font text-sm">
                      Connected as {oauthStatus.wp_user_login || "Unknown"} to {oauthStatus.wp_site_url || "Unknown"}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={handleTestConnection}
                      disabled={testingOAuth}
                      className="px-3 py-1 text-[9px] mono-font uppercase tracking-widest border border-ink hover:bg-paper transition-colors disabled:opacity-50"
                    >
                      {testingOAuth ? "Testing..." : "Test Connection"}
                    </button>
                    <button
                      type="button"
                      onClick={handlePublishTest}
                      disabled={publishingTest}
                      className="px-3 py-1 text-[9px] mono-font uppercase tracking-widest border border-green-500 text-green-500 hover:bg-green-500 hover:text-paper transition-colors disabled:opacity-50"
                    >
                      {publishingTest ? "Publishing..." : "Publish Test Post"}
                    </button>
                    <button
                      type="button"
                      onClick={handleOAuthDisconnect}
                      className="px-3 py-1 text-[9px] mono-font uppercase tracking-widest border border-red-500 text-red-500 hover:bg-red-500 hover:text-paper transition-colors"
                    >
                      Disconnect
                    </button>
                  </div>
                </div>
                {oauthStatus.expires_at && (
                  <div className="text-[10px] text-muted mono-font">
                    Token expires: {new Date(oauthStatus.expires_at).toLocaleString()}
                  </div>
                )}
                {oauthStatus.last_used_at && (
                  <div className="text-[10px] text-muted mono-font">
                    Last used: {new Date(oauthStatus.last_used_at).toLocaleString()}
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <div>
                  <div className="mono-font text-sm">OAuth Connection</div>
                  <div className="text-[10px] text-muted mono-font">
                    {oauthStatus?.needs_reconnect ? (
                      <span className="text-amber-500">Token expired - reconnect required</span>
                    ) : (
                      <span>Not connected via OAuth</span>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleOAuthConnect}
                  disabled={testingOAuth || !config.cms_url}
                  className="px-3 py-1 text-[9px] mono-font uppercase tracking-widest border border-accent text-accent hover:bg-accent hover:text-paper transition-colors disabled:opacity-50"
                >
                  {testingOAuth ? "Connecting..." : "Connect WordPress via OAuth"}
                </button>
              </div>
            )}
            {oauthStatus?.reason && !oauthStatus.connected && (
              <div className="text-[10px] text-muted mono-font">
                {oauthStatus.reason}
              </div>
            )}
          </div>
        </div>

        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Agent Configuration</div>
          <div className="space-y-3">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={config.auto_publish}
                onChange={(e) => setConfig({ ...config, auto_publish: e.target.checked })}
                className="w-4 h-4 border-ink"
              />
              <span className="mono-font text-sm">Auto-publish content</span>
            </label>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={config.human_approval_required}
                onChange={(e) => setConfig({ ...config, human_approval_required: e.target.checked })}
                className="w-4 h-4 border-ink"
              />
              <span className="mono-font text-sm">Require human approval</span>
            </label>
            <div>
              <label className="text-[10px] text-muted uppercase tracking-wider mono-font block mb-1">
                Max Daily Posts: {config.max_daily_posts}
              </label>
              <input
                type="range"
                min="1"
                max="10"
                value={config.max_daily_posts}
                onChange={(e) => setConfig({ ...config, max_daily_posts: parseInt(e.target.value) })}
                className="w-full"
              />
            </div>
          </div>
        </div>

        {error && (
          <div className="bg-stone border border-red-500 p-4">
            <div className="text-[11px] mono-font">{error}</div>
          </div>
        )}

        {success && (
          <div className="bg-green-100 border border-green-500 p-4">
            <div className="text-[11px] mono-font">{success}</div>
          </div>
        )}

        <button type="submit" disabled={saving} className="btn btn-accent">
          {saving ? "Saving..." : "Save Settings"}
        </button>
      </form>
    </div>
  );
}
