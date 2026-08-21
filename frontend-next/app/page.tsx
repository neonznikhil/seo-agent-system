"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { get, createSSE } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";
import Link from "next/link";

interface HealthStatus {
  status: string;
  checks: Record<string, string>;
  degraded_reasons?: string[];
}

interface ROIMetrics {
  impressions_last_30d: number;
  blogs_published_last_30d: number;
  technical_health_score: number;
  backlinks_total: number;
  backlinks_new_7d: number;
  impressions_change_pct: number;
}

interface AEOScore {
  score: number;
  improvements?: string[];
  featured_snippet_opportunities?: string[];
}

interface GEOReadiness {
  score: number;
  ai_citation_potential: string;
  citation_ready?: boolean;
  improvements?: string[];
}

interface GSCKeyword {
  query: string;
  clicks: number;
  impressions: number;
  position: number;
  ctr: number;
}

interface GSCData {
  website_id: string;
  keywords: GSCKeyword[];
  total_clicks: number;
  total_impressions: number;
}

interface Alert {
  id: string;
  website_id: string;
  severity: string;
  alert_type: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

interface Cluster {
  id: string;
  website_id: string;
  name: string;
  description?: string;
  keywords?: string[];
  authority_score?: number;
}

interface DecayLog {
  id: string;
  website_id: string;
  url: string;
  status: string;
  decay_percent?: number;
  detected_at: string;
}

interface ContentItem {
  id: string;
  website_id: string;
  title: string;
  status: string;
  content_type: string;
  created_at: string;
}

interface Memory {
  id: string;
  memory_type: string;
  title: string;
  content: string;
  confidence: number;
  times_used: number;
  times_successful: number;
  last_used_at: string;
  created_at: string;
}

interface QueueItem {
  id: string;
  suggested_topic: string;
  primary_keyword: string;
  reason: string;
  priority_score: number;
  source: string;
  status: string;
  auto_approve: boolean;
  created_at: string;
}

interface DailyJob {
  id: string;
  job_type: string;
  status: string;
  result: string;
  error?: string;
  run_at: string;
  next_run_at?: string;
}

function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "K";
  return String(n);
}

export default function HomePage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [roiData, setRoiData] = useState<ROIMetrics | null>(null);
  const [aeoScore, setAeoScore] = useState<AEOScore | null>(null);
  const [geoReadiness, setGeoReadiness] = useState<GEOReadiness | null>(null);
  const [gscData, setGscData] = useState<GSCData | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [decayLogs, setDecayLogs] = useState<DecayLog[]>([]);
  const [contentItems, setContentItems] = useState<ContentItem[]>([]);
  const [brainMemories, setBrainMemories] = useState<Memory[]>([]);
  const [autoQueue, setAutoQueue] = useState<QueueItem[]>([]);
  const [dailyJobs, setDailyJobs] = useState<DailyJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [liveEvents, setLiveEvents] = useState<string[]>([]);

  const websiteId = getCurrentWebsiteId();
  const sseRef = useRef<EventSource | null>(null);

  const fetchData = useCallback(async () => {
    setError(null);
    try {
      const results = await Promise.allSettled([
        get("/health"),
        get(`/roi/${websiteId}`),
        get(`/aeo-score/${websiteId}`),
        get(`/geo-readiness/${websiteId}`),
        get(`/gsc/keywords/${websiteId}`),
        get(`/monitoring/${websiteId}/alerts?filter=unread`),
        get(`/clusters?website_id=${websiteId}`),
        get(`/decay/${websiteId}/list?status=detected`),
        get(`/content?website_id=${websiteId}&limit=5`),
        get(`/brain/${websiteId}/memories?top_k=5`),
        get(`/brain/${websiteId}/auto-queue`),
        get(`/brain/${websiteId}/daily-jobs?days=7`),
      ]);

      const healthRes = results[0].status === "fulfilled" ? results[0].value : null;
      const roiRes = results[1].status === "fulfilled" ? results[1].value : null;
      const aeoRes = results[2].status === "fulfilled" ? results[2].value : null;
      const geoRes = results[3].status === "fulfilled" ? results[3].value : null;
      const gscRes = results[4].status === "fulfilled" ? results[4].value : null;
      const alertsRes = results[5].status === "fulfilled" ? results[5].value : null;
      const clustersRes = results[6].status === "fulfilled" ? results[6].value : null;
      const decayRes = results[7].status === "fulfilled" ? results[7].value : null;
      const contentRes = results[8].status === "fulfilled" ? results[8].value : null;
      const brainMemoriesRes = results[9].status === "fulfilled" ? results[9].value : null;
      const autoQueueRes = results[10].status === "fulfilled" ? results[10].value : null;
      const dailyJobsRes = results[11].status === "fulfilled" ? results[11].value : null;

      setHealth(healthRes);
      setRoiData(roiRes || null);
      setAeoScore(aeoRes || null);
      setGeoReadiness(geoRes || null);
      setGscData(gscRes || null);
      setAlerts(Array.isArray(alertsRes) ? alertsRes : []);
      setClusters(Array.isArray(clustersRes) ? clustersRes : []);
      setDecayLogs(Array.isArray(decayRes?.decay_logs) ? decayRes.decay_logs : []);
      setContentItems(Array.isArray(contentRes) ? contentRes : []);
      setBrainMemories(Array.isArray(brainMemoriesRes) ? brainMemoriesRes : []);
      setAutoQueue(Array.isArray(autoQueueRes) ? autoQueueRes : []);
      setDailyJobs(Array.isArray(dailyJobsRes) ? dailyJobsRes : []);
      setLastUpdated(new Date());

      const failures = results.filter(r => r.status === "rejected");
      if (failures.length > 0 && !healthRes) {
        setError("Backend offline - start uvicorn backend.main:app --reload");
      }
    } catch (e: any) {
      setError(e.message || "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  useEffect(() => {
    if (loading) return;
    sseRef.current = createSSE(`/monitoring/${websiteId}/live`, (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        setLiveEvents(prev => {
          const next = [data.message || JSON.stringify(data), ...prev].slice(0, 20);
          return next;
        });
      } catch {
        setLiveEvents(prev => [event.data, ...prev].slice(0, 20));
      }
    });
    return () => {
      if (sseRef.current) sseRef.current.close();
    };
  }, [websiteId, loading]);

  const backendOffline = !health && error;
  const gscConnected = health?.checks?.gsc === "ok";
  const nimConnected = health?.checks?.nim === "configured";

  const gscKeywords11to20 = gscData?.keywords?.filter(k => k.position >= 11 && k.position <= 20) || [];
  const avgTechHealth = roiData?.technical_health_score ?? null;
  const techIssues = alerts.filter(a => a.alert_type?.startsWith("tech_"));
  const avgAuthority = clusters.length > 0 ? Math.round(clusters.reduce((sum, c) => sum + (c.authority_score || 0), 0) / clusters.length) : null;

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-[11px] text-muted">
            <span className="w-2 h-2 bg-accent rounded-full" />
            <span>Dashboard</span>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="bg-stone border border-ink p-4">
              <div className="text-[11px] text-muted uppercase tracking-wider mono-font mb-2">Loading...</div>
              <div className="h-8 w-24 bg-line animate-pulse" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {backendOffline && (
        <div className="bg-stone border border-red-500 p-4">
          <div className="text-[11px] mono-font text-red-500">
            Backend offline at http://localhost:8000 - Run: uvicorn backend.main:app --reload
          </div>
        </div>
      )}

      {health?.status === "degraded" && health.degraded_reasons && (
        <div className="bg-stone border border-amber-500 p-4">
          <div className="text-[11px] mono-font text-amber-500">
            Degraded: {health.degraded_reasons.join(", ")}
          </div>
        </div>
      )}

      {!gscConnected && !backendOffline && (
        <div className="bg-stone border border-amber-500 p-4">
          <div className="text-[11px] mono-font text-amber-500">
            GSC not connected - Add GSC_CREDENTIALS_PATH in backend.env and test in /settings
          </div>
        </div>
      )}

      {/* HEADER */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[11px] text-muted">
          <span className="w-2 h-2 bg-accent rounded-full" />
          <span>Dashboard</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[9px] text-muted mono-font">
            Updated {timeAgo(lastUpdated)}
          </span>
          <Link href="/dashboard" className="px-3 py-1 text-[9px] mono-font uppercase tracking-widest border border-ink hover:bg-paper">
            Full View
          </Link>
        </div>
      </div>

      {/* TITLE */}
      <div>
        <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">RANKFORGE</h1>
        <p className="text-[11px] text-muted uppercase tracking-widest mono-font mt-1">
          Autonomous SEO &nbsp;·&nbsp; Real data only
        </p>
      </div>

      {/* KPI GRID */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <KPICard
          label="SEO SCORE"
          value={avgTechHealth !== null ? `${avgTechHealth}/100` : "No data"}
          sub={avgTechHealth !== null ? (avgTechHealth >= 80 ? "Healthy" : avgTechHealth >= 50 ? "Needs attention" : "Critical") : "Run tech monitor"}
          href="/tech-seo"
        />
        <KPICard
          label="AEO OPPORTUNITIES"
          value={gscConnected ? `${gscKeywords11to20.length}` : "Connect GSC"}
          sub={gscConnected ? "Position 11-20 striking" : "Add credentials in .env"}
          href="/research"
        />
        <KPICard
          label="GEO READINESS"
          value={geoReadiness?.score ? `${geoReadiness.score}/100` : "No data"}
          sub="Run GEO check"
          href="/settings"
        />
        <KPICard
          label="AI CITATIONS"
          value={geoReadiness?.ai_citation_potential || "0%"}
          sub="Perplexity/ChatGPT"
          href="/settings"
        />
        <KPICard
          label="DECAYED PAGES"
          value={`${decayLogs.length}`}
          sub={decayLogs.length > 0 ? "Need refresh" : "No decay detected"}
          href="/decay"
        />
        <KPICard
          label="TOPIC AUTHORITY"
          value={avgAuthority !== null ? `${avgAuthority}%` : "No data"}
          sub={clusters.length > 0 ? `${clusters.length} clusters` : "Build from GSC"}
          href="/clusters"
        />
        <KPICard
          label="BRAIN MEMORIES"
          value={`${brainMemories.length}`}
          sub="Facts, experiences, failures"
          href="/brain"
        />
        <KPICard
          label="AUTO QUEUE"
          value={`${autoQueue.length}`}
          sub="Pages waiting to write"
          href="/brain"
        />
        <KPICard
          label="DAILY JOBS"
          value={dailyJobs.length > 0 ? `${dailyJobs.length}` : "0"}
          sub={dailyJobs.length > 0 ? `Last run ${timeAgo(new Date(dailyJobs[0].run_at))}` : "No runs yet"}
          href="/brain"
        />
      </div>

      {/* AGENTS + ACTIVITY */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-stone border border-ink p-4">
          <div className="flex items-center justify-between mb-4">
            <div className="text-xs text-muted uppercase tracking-wider mono-font">Live Agent Activity</div>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              <span className="text-[9px] text-green-500 mono-font">LIVE</span>
            </div>
          </div>
          <div className="space-y-0">
            {liveEvents.length === 0 ? (
              <div className="text-[11px] text-muted mono-font py-2">Monitoring offline - Start backend</div>
            ) : (
              liveEvents.slice(0, 8).map((evt, i) => (
                <div key={i} className="flex items-center justify-between p-2 border-b border-line last:border-b-0">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 bg-accent" />
                    <span className="mono-font text-sm">{evt}</span>
                  </div>
                  <span className="text-[10px] text-muted mono-font whitespace-nowrap">
                    {i === 0 ? "now" : `${i * 2}m ago`}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="bg-stone border border-ink p-4">
          <div className="flex items-center justify-between mb-4">
            <div className="text-xs text-muted uppercase tracking-wider mono-font">ROI Trend</div>
            <div className="text-[9px] text-muted mono-font">Last 7 days</div>
          </div>
          {gscConnected && gscData?.keywords ? (
            <div className="h-32 flex items-end gap-1">
              {gscData.keywords.slice(0, 7).map((kw, i) => (
                <div key={i} className="flex-1 bg-accent hover:bg-ink transition-colors" style={{ height: `${Math.min(100, Math.max(10, kw.clicks * 2))}%` }} title={`${kw.query}: ${kw.clicks} clicks`} />
              ))}
            </div>
          ) : (
            <div className="text-[11px] text-muted mono-font py-8">Connect GSC to see trend</div>
          )}
        </div>
      </div>

      {/* CONTENT + TECH HEALTH */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-stone border border-ink p-4">
          <div className="flex items-center justify-between mb-4">
            <div className="text-xs text-muted uppercase tracking-wider mono-font">Content Calendar</div>
          </div>
          {contentItems.length > 0 ? (
            <div className="space-y-2">
              {contentItems.slice(0, 5).map((item) => (
                <div key={item.id} className="flex items-center justify-between p-2 border border-line hover:border-accent hover:bg-paper transition-colors">
                  <div>
                    <div className="mono-font text-sm">{item.title}</div>
                    <div className="text-[10px] text-muted mono-font">{item.status} · {item.content_type}</div>
                  </div>
                  <span className="text-[9px] text-muted mono-font">{new Date(item.created_at).toLocaleDateString()}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-[11px] text-muted mono-font py-4">No content - Create in /content</div>
          )}
        </div>

        <div className="bg-stone border border-ink p-4">
          <div className="flex items-center justify-between mb-4">
            <div className="text-xs text-muted uppercase tracking-wider mono-font">Technical Health</div>
          </div>
          {techIssues.length > 0 ? (
            <div className="space-y-2">
              {techIssues.slice(0, 5).map((issue) => (
                <div key={issue.id} className="flex items-center justify-between p-2 border border-line">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 ${issue.severity === 'critical' ? 'bg-red-500' : issue.severity === 'high' ? 'bg-amber-500' : 'bg-line'}`} />
                    <span className="mono-font text-sm">{issue.message}</span>
                  </div>
                  <span className="text-[9px] text-muted mono-font">{issue.alert_type}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-[11px] text-muted mono-font py-4">No tech issues detected</div>
          )}
          <Link href="/tech-seo" className="block mt-3 text-[9px] mono-font uppercase tracking-widest text-accent hover:underline">
            View Fix
          </Link>
        </div>
      </div>

      {/* BRAIN AUTO-ADDED TODAY */}
      {autoQueue.filter(q => {
        const created = new Date(q.created_at);
        const today = new Date();
        return created.toDateString() === today.toDateString();
      }).length > 0 && (
        <div className="bg-stone border border-ink p-4">
          <div className="flex items-center justify-between mb-4">
            <div className="text-xs text-muted uppercase tracking-wider mono-font">Brain Auto-Added Today</div>
            <Link href="/brain" className="text-[9px] mono-font uppercase tracking-widest text-accent hover:underline">
              View Brain
            </Link>
          </div>
          <div className="space-y-2">
            {autoQueue
              .filter(q => new Date(q.created_at).toDateString() === new Date().toDateString())
              .slice(0, 5)
              .map((item) => (
                <div key={item.id} className="flex items-center justify-between p-2 border border-line">
                  <div>
                    <div className="mono-font text-sm">{item.suggested_topic}</div>
                    <div className="text-[10px] text-muted mono-font">{item.primary_keyword} · {item.reason}</div>
                  </div>
                  <span className="text-[9px] mono-font text-muted">{item.status}</span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

function KPICard({ label, value, sub, href }: { label: string; value: string; sub: string; href: string }) {
  return (
    <Link href={href} className="bg-stone border border-ink p-4 hover:border-accent transition-colors group block">
      <div className="text-[11px] text-muted uppercase tracking-wider mono-font mb-2">{label}</div>
      <div className="text-3xl font-bold dot-font group-hover:text-accent transition-colors">{value}</div>
      <div className="text-[10px] text-muted mono-font mt-2">{sub}</div>
    </Link>
  );
}

function timeAgo(date: Date): string {
  const diff = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}
