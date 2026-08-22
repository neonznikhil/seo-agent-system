"use client";

import { useEffect, useState, useRef } from "react";
import { get, post } from "@/lib/api";
import { KeywordBadge } from "@/components/KeywordBadge";
import { getCurrentWebsiteId } from "@/lib/website";

interface Alert {
  id: string;
  alert_type: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  title: string;
  description: string;
  data: any;
  source_monitor: string;
  created_at: string;
  requires_human_approval: boolean;
}

interface MonitorStats {
  total_alerts_24h: number;
  critical: number;
  high: number;
  medium: number;
  monitors: Record<string, string>;
  all_monitors_ok: boolean;
}

interface PendingItem {
  id: string;
  type: string;
  label: string;
  count: number;
}

interface IntegrationStatus {
  name: string;
  status: "connected" | "disconnected" | "error";
  detail?: string;
}

export default function MonitoringPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [stats, setStats] = useState<MonitorStats | null>(null);
  const [pendingItems, setPendingItems] = useState<PendingItem[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("unread");
  const [userId, setUserId] = useState<string>("");
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem("x-user-id") || localStorage.getItem("userId") || "";
    setUserId(stored);
  }, []);

  useEffect(() => {
    fetchAlerts();
    fetchStats();
    fetchPendingItems();
    fetchIntegrations();
    setupSSE();

    const interval = setInterval(() => {
      fetchAlerts();
      fetchStats();
      fetchPendingItems();
      fetchIntegrations();
    }, 30000);

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      clearInterval(interval);
    };
  }, [filter]);

  const fetchAlerts = async () => {
    try {
      const websiteId = getCurrentWebsiteId();
      const data = await get(`/monitoring/${websiteId}/alerts?filter=${filter}`);
      setAlerts(data || []);
    } catch (e) {
      console.error("Failed to fetch alerts", e);
    }
  };

  const fetchStats = async () => {
    try {
      const websiteId = getCurrentWebsiteId();
      const data = await get(`/monitoring/${websiteId}/stats`);
      setStats(data);
    } catch (e) {
      console.error("Failed to fetch stats", e);
    }
  };

  const fetchPendingItems = async () => {
    try {
      const websiteId = getCurrentWebsiteId();
      const data = await get(`/monitoring/${websiteId}/pending-fixes`);
      const items = Array.isArray(data) ? data : [];
      setPendingItems(
        items.map((item: any) => ({
          id: item.id || String(Math.random()),
          type: item.fix_type || "fix",
          label: item.fix_type?.replace(/_/g, " ") || "Fix",
          count: 1,
        }))
      );
    } catch (e) {
      console.error("Failed to fetch pending items", e);
      setPendingItems([]);
    }
  };

  const fetchIntegrations = async () => {
    try {
      const websiteId = getCurrentWebsiteId();
      const data = await get(`/settings/website/${websiteId}`);
      const config = data || {};
      const integrations: IntegrationStatus[] = [
        {
          name: "WordPress",
          status: config.cms_url ? "connected" : "disconnected",
          detail: config.cms_url ? "Draft Mode" : undefined,
        },
        {
          name: "Google Search Console",
          status: config.gsc_property ? "connected" : "disconnected",
        },
        {
          name: "PageSpeed API",
          status: (config.settings?.pagespeed_key || config.pagespeed_key) ? "connected" : "disconnected",
        },
        {
          name: "Slack",
          status: (config.settings?.slack_webhook || config.slack_webhook) ? "connected" : "disconnected",
        },
      ];
      setIntegrations(integrations);
    } catch (e) {
      console.error("Failed to fetch integrations", e);
      setIntegrations([]);
    }
  };

  const setupSSE = () => {
    try {
      const websiteId = getCurrentWebsiteId();
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
      const es = new EventSource(`${apiBase}/monitoring/${websiteId}/live`);
      eventSourceRef.current = es;

      es.onmessage = (event) => {
        try {
          const alert = JSON.parse(event.data);
          if (alert.id && !alerts.find((a) => a.id === alert.id)) {
            setAlerts((prev) => [alert, ...prev]);
            playNotificationSound();
          }
        } catch (e) {
          console.error("SSE parse error", e);
        }
      };

      es.onerror = (err) => {
        console.error("SSE error", err);
      };
    } catch (e) {
      console.error("SSE setup failed", e);
    }
  };

  const playNotificationSound = () => {
    try {
      const audio = new Audio("/notification.mp3");
      audio.play().catch(() => {});
    } catch {
      // ignore audio errors
    }
  };

  const markRead = async (alertId: string) => {
    try {
      const websiteId = getCurrentWebsiteId();
      await post(`/monitoring/${websiteId}/alerts/${alertId}/read`, {}, { "X-User-Id": userId });
    } catch (e) {
      console.error("Failed to mark read", e);
    }
    setAlerts((prev) => prev.filter((a) => a.id !== alertId));
  };

  const approveAlert = async (alertId: string) => {
    try {
      const websiteId = getCurrentWebsiteId();
      await post(`/monitoring/${websiteId}/alerts/${alertId}/approve`, {}, { "X-User-Id": userId });
    } catch (e) {
      console.error("Failed to approve alert", e);
    }
    fetchAlerts();
  };

  const getSeverityColor = (severity: string) => {
    const colors: Record<string, string> = {
      critical: "bg-red-50 border-red-400 text-red-700",
      high: "bg-orange-50 border-orange-400 text-orange-700",
      medium: "bg-yellow-50 border-yellow-400 text-yellow-700",
      low: "bg-blue-50 border-blue-400 text-blue-700",
      info: "bg-gray-50 border-gray-400 text-gray-700",
    };
    return colors[severity] || "bg-stone border-ink text-ink";
  };

  const getSeverityIcon = (severity: string) => {
    const icons: Record<string, string> = {
      critical: "●",
      high: "⚠",
      medium: "●",
      low: "●",
      info: "●",
    };
    return icons[severity] || "●";
  };

  const getFixMethodDisplay = (fixType: string) => {
    const methods: Record<string, string> = {
      tech_broken_link: "Add redirect / 404 page",
      tech_speed: "Optimize images & lazy load",
      tech_mobile: "Fix viewport & tap targets",
      tech_crawl: "Fix robots.txt / sitemap",
      tech_index: "Remove noindex tag",
    };
    return methods[fixType] || "Manual review";
  };

  const monitorCount = stats?.monitors
    ? Object.values(stats.monitors).filter((v) => v === "ok").length
    : 0;
  const monitorTotal = stats?.monitors ? Object.keys(stats.monitors).length : 0;

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold dot-font">LIVE MONITORING 24/7</h1>
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-stone border border-ink p-4 animate-pulse">
              <div className="h-4 bg-line rounded mb-2"></div>
              <div className="h-8 bg-line rounded"></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold dot-font">
          <span className="text-accent">●</span> Live Monitoring 24/7
        </h1>
        <div className="text-xs mono-font">
          Last checked: {new Date().toLocaleTimeString()}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <div className="bg-red-50 border border-red-400 p-4">
          <div className="text-xs text-red-600 uppercase tracking-wider">CRITICAL</div>
          <div className="text-2xl font-bold text-red-700 dot-font">{stats?.critical || 0}</div>
        </div>
        <div className="bg-orange-50 border border-orange-400 p-4">
          <div className="text-xs text-orange-600 uppercase tracking-wider">HIGH</div>
          <div className="text-2xl font-bold text-orange-700 dot-font">{stats?.high || 0}</div>
        </div>
        <div className="bg-blue-50 border border-blue-400 p-4">
          <div className="text-xs text-blue-600 uppercase tracking-wider">OPPORTUNITIES</div>
          <div className="text-2xl font-bold text-blue-700 dot-font">{stats?.medium || 0}</div>
        </div>
        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-ink uppercase tracking-wider">MONITORS</div>
          <div className="text-2xl font-bold dot-font">
            {monitorCount}/{monitorTotal || 6} OK
          </div>
        </div>
      </div>

      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setFilter("unread")}
          className={`px-3 py-1 text-xs border ${filter === "unread" ? "bg-ink text-stone" : "bg-stone border-ink"}`}
        >
          Unread
        </button>
        <button
          onClick={() => setFilter("critical")}
          className={`px-3 py-1 text-xs border ${filter === "critical" ? "bg-ink text-stone" : "bg-stone border-ink"}`}
        >
          Critical
        </button>
        <button
          onClick={() => setFilter("all")}
          className={`px-3 py-1 text-xs border ${filter === "all" ? "bg-ink text-stone" : "bg-stone border-ink"}`}
        >
          All
        </button>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <div className="md:col-span-2">
          <div className="bg-stone border border-ink p-4">
            <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">LIVE ALERT FEED</div>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {alerts.length === 0 ? (
                <div className="text-center py-8 text-muted mono-font">
                  No unread alerts. All systems monitoring...
                </div>
              ) : (
                alerts.map((alert) => (
                  <div
                    key={alert.id}
                    className={`p-3 border-l-4 ${getSeverityColor(alert.severity)}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="mono-font text-sm">
                            {new Date(alert.created_at).toLocaleTimeString()}
                          </span>
                           <KeywordBadge query={alert.source_monitor} impressions={0} ctr={0} />
                          <span className="text-xs mono-font">
                            [{alert.severity.toUpperCase()}]
                          </span>
                        </div>
                        <div className="font-mono text-sm">{alert.title}</div>
                        <div className="text-xs text-muted">{alert.description}</div>
                        <div className="text-xs mono-font">
                          <details>
                            <summary>View data</summary>
                            <pre className="text-xs bg-line p-2 rounded mt-2 overflow-x-auto">
                              {JSON.stringify(alert.data, null, 2)}
                            </pre>
                          </details>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => markRead(alert.id)}
                          className="text-xs px-2 py-1 bg-line border border-ink hover:bg-stone"
                        >
                          Mark Read
                        </button>
                        {alert.requires_human_approval && (
                          <button
                            onClick={() => approveAlert(alert.id)}
                            className="text-xs px-2 py-1 bg-accent text-stone border border-ink hover:bg-ink hover:text-stone"
                          >
                            Approve
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-stone border border-ink p-4">
            <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">PENDING HUMAN APPROVAL</div>
            <div className="space-y-3">
              {pendingItems.length === 0 && (
                <div className="text-[11px] text-muted mono-font">No pending approvals</div>
              )}
              {pendingItems.map((item) => (
                <div key={item.id}>
                  <div className="text-sm mono-font mb-2">
                    {item.label}: {item.count} pending
                  </div>
                  <button className="w-full text-xs px-2 py-1 bg-line border border-ink hover:bg-stone">
                    Review
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-stone border border-ink p-4">
            <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">INTEGRATION STATUS</div>
            <div className="space-y-2 text-sm">
              {integrations.length === 0 && (
                <div className="text-[11px] text-muted mono-font">No integration data</div>
              )}
              {integrations.map((item) => (
                <div key={item.name} className="flex justify-between">
                  <span className="mono-font">{item.name}</span>
                  <span
                    className={
                      item.status === "connected"
                        ? "text-green-600"
                        : item.status === "error"
                        ? "text-red-600"
                        : "text-yellow-600"
                    }
                  >
                    ● {item.status}
                    {item.detail ? ` (${item.detail})` : ""}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {userId && (
            <div className="bg-stone border border-ink p-4">
              <div className="text-xs text-ink mono-font">
                USER ID: {userId}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
