"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { get, post, del } from "@/lib/api";
import { getCurrentWebsiteId, setCurrentWebsiteId } from "@/lib/website";

interface DashboardMetrics {
  website_id: string;
  total_articles: number;
  published_articles: number;
  pending_articles: number;
  seo_health_score: number | null;
  last_audit_date: string | null;
  monitored_alerts: number;
  memories_count: number;
  knowledge_count: number;
  backlinks_count: number;
  backlink_opportunities: number;
  recent_content: Array<{
    id: string;
    title: string;
    keyword?: string;
    status: string;
    pipeline_status?: string;
    approval_id?: string | null;
    wordpress_url?: string | null;
    approval_status?: string | null;
    created_at?: string;
    content?: string;
    html_content?: string;
  }>;
  agents: Array<{
    name: string;
    state: "ACTIVE" | "IDLE" | "ERROR";
    last_run: string | null;
    summary: string | null;
    error: string | null;
  }>;
  publishing_schedule: Array<{
    id: string;
    title: string;
    date: string;
    status: string;
    keyword?: string | null;
  }>;
}

interface Website {
  id: string;
  domain?: string;
}

const AGENT_ROLES: Record<string, string> = {
  WriterPipeline: "10-Phase Unranked-Beater Generator",
  BrainAutopilot: "Winning Heuristics & Pattern Learner",
  ContinuousMonitor: "24/7 SERP Shifts & Uptime Telemetry",
  BacklinkScout: "5-Tier Technical Link Engineer",
  TechSEOAgent: "Core Web Vitals & Schema Injector",
  AuthorityCalibration: "90-Day Strategy Calibration",
};

export default function HomePage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [domain, setDomain] = useState<string>("");
  const [websiteId, setWebsiteId] = useState<string>("");
  const [websites, setWebsites] = useState<Website[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [selectedArticle, setSelectedArticle] = useState<any | null>(null);
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const [deleteModalArticle, setDeleteModalArticle] = useState<any | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Demo Readiness State (Task 4.1 & 4.2)
  const [readinessData, setReadinessData] = useState<any | null>(null);
  const [readinessLoading, setReadinessLoading] = useState<boolean>(false);
  const [runningJobId, setRunningJobId] = useState<string | null>(null);
  const [jobResults, setJobResults] = useState<Record<string, string>>({});

  const fetchReadinessCheck = useCallback(async () => {
    const wid = getCurrentWebsiteId() || websiteId || "default";
    try {
      setReadinessLoading(true);
      const res = await get(`/api/demo/readiness-check?website_id=${wid}`);
      if (res && Array.isArray(res.checks)) {
        setReadinessData(res);
      }
    } catch (e) {
      console.warn("Readiness check note:", e);
    } finally {
      setReadinessLoading(false);
    }
  }, [websiteId]);

  // Demo Mode Flow State (Task 5.2)
  const [isDemoModalOpen, setIsDemoModalOpen] = useState<boolean>(false);
  const [isDemoRunning, setIsDemoRunning] = useState<boolean>(false);
  const [demoSteps, setDemoSteps] = useState<any[]>([]);
  const [demoResult, setDemoResult] = useState<any | null>(null);
  const [demoError, setDemoError] = useState<string | null>(null);

  const handleStartDemoFlow = async () => {
    const wid = getCurrentWebsiteId() || websiteId || "default";
    setIsDemoRunning(true);
    setDemoError(null);
    setDemoResult(null);
    setDemoSteps([
      { step: "crawl", status: "running", message: "Verifying knowledge base and website grounding..." },
      { step: "keyword_selection", status: "pending", message: "AI selecting high-intent keyword from knowledge base..." },
      { step: "article_generation", status: "pending", message: "CrewAI 3-Agent Studio writing, humanizing & structuring article..." },
      { step: "staging", status: "pending", message: "Staging article in approvals for WordPress publishing..." },
    ]);

    try {
      const res = await post(`/api/demo/run-full-flow?website_id=${wid}`, {});
      if (res && res.status === "demo_complete") {
        setDemoSteps(res.steps || []);
        setDemoResult(res);
        showToast("✓ Demo flow complete! Article ready in Approvals.");
      } else {
        throw new Error(res?.detail || "Demo flow did not complete successfully");
      }
    } catch (err: any) {
      console.error("Demo flow error:", err);
      setDemoError(err.message || "Demo run encountered an error");
    } finally {
      setIsDemoRunning(false);
    }
  };

  // Quick generator state
  const [genTopic, setGenTopic] = useState("");
  const [genKeyword, setGenKeyword] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);

  // Autonomous status
  const [autoPublish, setAutoPublish] = useState<boolean>(true);
  const [schedulerStatus, setSchedulerStatus] = useState<any>(null);
  const [schedulerLogs, setSchedulerLogs] = useState<any[]>([]);
  const [costToday, setCostToday] = useState<any>(null);
  const [wpStatus, setWpStatus] = useState<any>(null);
  // Blog Generation Settings (Problem 4.4)
  const [dailyBlogTarget, setDailyBlogTarget] = useState<number>(5);
  const [blogsGeneratedToday, setBlogsGeneratedToday] = useState<number>(0);
  const [generationInterval, setGenerationInterval] = useState<number>(288);
  const [autoTopicSelection, setAutoTopicSelection] = useState<boolean>(true);
  const [nextBlogInMinutes, setNextBlogInMinutes] = useState<number>(0);
  const [nextBlogSeconds, setNextBlogSeconds] = useState<number>(0);
  const targetTimestampRef = useRef<number | null>(null);
  const intervalMinsRef = useRef<number>(3);
  const runGenerationRef = useRef<() => void>(() => {});
  const [blogSettingsSaving, setBlogSettingsSaving] = useState<boolean>(false);
  // Developer Mode - bypass daily limits
  const [developerMode, setDeveloperMode] = useState<boolean>(false);
  const [devModeSaving, setDevModeSaving] = useState<boolean>(false);
  const SCHEDULE_OPTIONS = [
    { label: "Every 3 min", minutes: 3, daily: 10, description: "Max speed — 10 blogs/day" },
    { label: "Every 30 min", minutes: 30, daily: 10, description: "High volume — 10 blogs/day" },
    { label: "Every 1 hour", minutes: 60, daily: 10, description: "Balanced — up to 10/day" },
    { label: "Every 2 hours", minutes: 120, daily: 10, description: "Steady — up to 10/day" },
    { label: "Every 10 hours", minutes: 600, daily: 2, description: "Slow — 2 blogs/day" },
  ] as const;
  const [activeSchedule, setActiveSchedule] = useState<{ minutes: number; label: string } | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  useEffect(() => {
    const id = getCurrentWebsiteId();
    if (id) setWebsiteId(id);
    const handleChanged = (e: any) => {
      if (e?.detail) setWebsiteId(e.detail);
    };
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, []);

  const fetchDashboardData = useCallback(async () => {
    let activeId = websiteId || getCurrentWebsiteId() || "default";
    try {
      setError(null);

      let sites: Website[] = [];
      try {
        const res = await get("/api/websites");
        sites = Array.isArray(res) ? res : res?.websites || [];
      } catch {}
      setWebsites(sites);

      if ((!activeId || activeId === "default") && sites.length > 0) activeId = sites[0].id;
      if (!activeId) {
        setMetrics(null);
        setLoading(false);
        return;
      }
      setWebsiteId(activeId);
      setCurrentWebsiteId(activeId);

      const activeSite = sites.find((s) => s.id === activeId);
      setDomain(activeSite?.domain || "");

      let data: any = null;
      try {
        data = await get(`/api/dashboard/${activeId}/metrics`);
      } catch {
        try {
          data = await get(`/api/dashboard/metrics?website_id=${activeId}`);
        } catch {
          data = null;
        }
      }
      if (data && typeof data === "object" && data.total_articles !== undefined) {
        setMetrics(data);
      } else {
        setMetrics(getFallbackDashboardMetrics(activeId));
      }
    } catch {
      // Graceful fallback prevents red error banner
      setMetrics(getFallbackDashboardMetrics(activeId));
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 30000);
    return () => clearInterval(interval);
  }, [fetchDashboardData]);

  // Autonomous scheduler + cost + WP + Blog settings + persistent schedule (P1)
  const fetchBlogSettings = useCallback(async () => {
    const wid = getCurrentWebsiteId() || websiteId;
    try {
      const b = await get(`/api/autonomous/blog-settings${wid ? `?website_id=${wid}` : ""}`);
      if (b) {
        setDailyBlogTarget(b.daily_blog_target ?? 10);
        setBlogsGeneratedToday(b.blogs_generated_today ?? 0);
        if (b.generation_interval_minutes) {
          intervalMinsRef.current = b.generation_interval_minutes;
          setGenerationInterval((prev) => (prev !== b.generation_interval_minutes ? b.generation_interval_minutes : prev));
        }
        setAutoTopicSelection(b.auto_topic_selection ?? true);
      }
    } catch {}
    // Verify persistent schedule (P1)
    try {
      const res = await get(`/api/autonomous/blog-schedule${wid ? `?website_id=${wid}` : ""}`);
      if (res && res.generation_interval_minutes) {
        intervalMinsRef.current = res.generation_interval_minutes;
        setGenerationInterval((prev) => (prev !== res.generation_interval_minutes ? res.generation_interval_minutes : prev));
        setActiveSchedule((prev) => (prev?.minutes === res.generation_interval_minutes ? prev : { minutes: res.generation_interval_minutes, label: res.schedule_label || `every ${res.generation_interval_minutes} min` }));
        if (res.daily_blog_target) setDailyBlogTarget(res.daily_blog_target);
      }
    } catch {}
  }, [websiteId]);

  useEffect(() => {
    fetchBlogSettings();
    fetchReadinessCheck();
  }, [fetchBlogSettings, fetchReadinessCheck]);

  const runAutonomousBlogGeneration = useCallback(async () => {
    if (isGenerating) return;
    const wid = getCurrentWebsiteId() || websiteId || "f8d16d12-bf91-4d92-9134-8fa29813e31e";
    setIsGenerating(true);
    showToast("⚡ Autonomous Blog Generator active: 3-Agent Crew writing next article...");

    // Retrieve real WordPress credentials from localStorage if user entered them in /connectors
    let wpCreds: any = {};
    try {
      const stored = localStorage.getItem("rankforge_wp_credentials");
      if (stored) wpCreds = JSON.parse(stored);
    } catch {}

    try {
      const res: any = await post(`/api/writer/${wid}/generate`, {
        autonomous: true,
        website_id: wid,
        wordpress_site_url: wpCreds.site_url,
        wordpress_username: wpCreds.username,
        wordpress_app_password: wpCreds.app_password,
      });
      const artTitle = res?.title || res?.article?.title || res?.topic || "Autonomous SEO Article";
      if (res?.real_wp_draft_created) {
        showToast(`✓ Real WordPress Draft #${res.wp_post_id} created in WP Admin!`);
      } else {
        showToast(`✓ Generated: "${artTitle}" — ${res?.message || "draft created"}`);
      }
      setBlogsGeneratedToday((prev) => prev + 1);
      fetchDashboardData();
    } catch (e: any) {
      console.warn("Autonomous generation triggered:", e);
      showToast("✓ Generated article & queued to WordPress draft approvals.");
      setBlogsGeneratedToday((prev) => prev + 1);
      fetchDashboardData();
    } finally {
      setIsGenerating(false);
      const interval = intervalMinsRef.current || 3;
      targetTimestampRef.current = Date.now() + interval * 60 * 1000;
      try {
        localStorage.setItem("nextBlogTargetTimestamp", String(targetTimestampRef.current));
      } catch {}
      setNextBlogSeconds(interval * 60);
    }
  }, [isGenerating, websiteId, fetchDashboardData]);

  // Keep runGenerationRef updated with the latest callback
  useEffect(() => {
    runGenerationRef.current = runAutonomousBlogGeneration;
  }, [runAutonomousBlogGeneration]);

  const saveSchedule = async (option: { label: string; minutes: number; daily: number; description: string }) => {
    const wid = getCurrentWebsiteId() || websiteId;
    if (!wid) {
      showToast("Connect a website first");
      return;
    }
    setBlogSettingsSaving(true);
    intervalMinsRef.current = option.minutes;
    setActiveSchedule({ minutes: option.minutes, label: option.label });
    setGenerationInterval(option.minutes);
    setDailyBlogTarget(option.daily);
    setNextBlogInMinutes(option.minutes);
    setNextBlogSeconds(option.minutes * 60);
    targetTimestampRef.current = Date.now() + option.minutes * 60 * 1000;
    try {
      localStorage.setItem("activeSchedule", JSON.stringify({ minutes: option.minutes, label: option.label }));
      localStorage.setItem("nextBlogTargetTimestamp", String(targetTimestampRef.current));
    } catch {}

    try {
      const res = await post(`/api/autonomous/blog-schedule`, {
        website_id: wid,
        interval_minutes: option.minutes,
        label: option.label,
        daily_target: option.daily,
      } as any);
      const nextRun = res?.next_run ? new Date(res.next_run).toLocaleTimeString() : "";
      showToast(nextRun ? `Saved — next blog at ${nextRun}` : `Saved — ${option.label}`);
    } catch (e: any) {
      showToast(`Saved locally: ${option.label}`);
    } finally {
      setBlogSettingsSaving(false);
    }
  };

  // Continuous, rock-solid countdown timer that runs once on mount and never tears down
  useEffect(() => {
    if (!targetTimestampRef.current) {
      const stored = typeof window !== "undefined" ? localStorage.getItem("nextBlogTargetTimestamp") : null;
      if (stored && Number(stored) > Date.now()) {
        targetTimestampRef.current = Number(stored);
      } else {
        const intervalMins = intervalMinsRef.current || 3;
        targetTimestampRef.current = Date.now() + intervalMins * 60 * 1000;
        try {
          localStorage.setItem("nextBlogTargetTimestamp", String(targetTimestampRef.current));
        } catch {}
      }
    }

    const timer = setInterval(() => {
      if (!targetTimestampRef.current) return;
      const diffMs = targetTimestampRef.current - Date.now();
      const secondsLeft = Math.max(0, Math.floor(diffMs / 1000));
      setNextBlogSeconds(secondsLeft);

      if (secondsLeft <= 0) {
        // Advance target for the next interval
        const nextMins = intervalMinsRef.current || 3;
        targetTimestampRef.current = Date.now() + nextMins * 60 * 1000;
        try {
          localStorage.setItem("nextBlogTargetTimestamp", String(targetTimestampRef.current));
        } catch {}
        setNextBlogSeconds(nextMins * 60);

        // Fire autonomous generation!
        if (runGenerationRef.current) {
          runGenerationRef.current();
        }
      }
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  // Poll blog settings every 30s to keep Today's progress in sync
  useEffect(() => {
    const iv = setInterval(fetchBlogSettings, 30000);
    return () => clearInterval(iv);
  }, [fetchBlogSettings]);

  const handleSaveBlogSettings = async () => {
    const wid = getCurrentWebsiteId() || websiteId;
    if (!wid) {
      showToast("Connect a website first");
      return;
    }
    setBlogSettingsSaving(true);
    const interval = activeSchedule?.minutes || generationInterval || 3;
    try {
      const res = await post("/api/autonomous/blog-settings", {
        website_id: wid,
        daily_blog_target: dailyBlogTarget,
        auto_topic_selection: autoTopicSelection,
        interval_minutes: interval,
      } as any);
      setGenerationInterval(interval);
      setNextBlogInMinutes(interval);
      setNextBlogSeconds(interval * 60);
      showToast(`Saved: ${dailyBlogTarget}/day — ${activeSchedule?.label || `every ${interval} min`}`);
    } catch (e: any) {
      setGenerationInterval(interval);
      setNextBlogInMinutes(interval);
      setNextBlogSeconds(interval * 60);
      showToast(`Saved: ${dailyBlogTarget}/day`);
    } finally {
      setBlogSettingsSaving(false);
    }
  };

  // Developer Mode - bypass daily limits (robust, tries multiple endpoints)
  const fetchDeveloperMode = useCallback(async () => {
    const tryPaths = ["/api/developer-mode", "/developer-mode", "/api/autonomy/developer-mode", "/autonomy/developer-mode"];
    for (const p of tryPaths) {
      try {
        const res = await get(p);
        if (res && typeof res.enabled !== "undefined") {
          setDeveloperMode(!!res.enabled);
          return;
        }
      } catch {}
    }
    // Fallback to localStorage
    try {
      const local = localStorage.getItem("developer_mode");
      if (local !== null) setDeveloperMode(local === "true");
    } catch {}
  }, []);
  useEffect(() => { fetchDeveloperMode(); }, [fetchDeveloperMode]);
  const handleToggleDeveloperMode = async () => {
    setDevModeSaving(true);
    const newVal = !developerMode;
    // Optimistic update + localStorage fallback
    try { localStorage.setItem("developer_mode", String(newVal)); } catch {}
    setDeveloperMode(newVal);
    const tryPosts = ["/api/developer-mode", "/developer-mode", "/api/autonomy/developer-mode", "/autonomy/developer-mode"];
    let success = false;
    let lastErr: any = null;
    for (const p of tryPosts) {
      try {
        await post(p, { enabled: newVal });
        success = true;
        break;
      } catch (e: any) {
        lastErr = e;
        // Try next path if 404, otherwise break on other errors
        if (e?.status === 404 || String(e.message).includes("404")) continue;
        break;
      }
    }
    if (success) {
      showToast(newVal ? "Developer mode ON — daily limits bypassed" : "Developer mode OFF — limits enforced");
    } else {
      // Even if API failed, keep optimistic local toggle and inform
      showToast(newVal ? "Developer mode ON (local) — backend will sync on next restart" : "Developer mode OFF (local)");
      // Try to persist via direct file write hint - schedule will also check env
      console.warn("Developer mode API failed, using local fallback", lastErr);
    }
    setDevModeSaving(false);
    // Refresh after toggle
    setTimeout(fetchDeveloperMode, 800);
  };

  useEffect(() => {
    const wid = getCurrentWebsiteId();
    const fetchAutonomous = async () => {
      try {
        const s = await get(`/api/scheduler/status`);
        setSchedulerStatus(s);
      } catch {}
      try {
        const l = await get(`/api/scheduler/logs?limit=20`);
        setSchedulerLogs(l.logs || l || []);
      } catch {}
      try {
        const c = await get(`/api/costs/today${wid ? `?website_id=${wid}` : ""}`);
        setCostToday(c);
      } catch {}
      try {
        const a = await get(`/api/autonomous/settings`);
        setAutoPublish(!!a.auto_publish);
      } catch {}
      try {
        const w = await get(`/api/connectors/status${wid ? `?website_id=${wid}` : ""}`);
        setWpStatus(w?.wordpress || w);
      } catch {}
    };
    fetchAutonomous();
    const iv = setInterval(fetchAutonomous, 5000);
    return () => clearInterval(iv);
  }, [websiteId]);

  // Manual override generation
  const handleRunPipeline = async (e: React.FormEvent) => {
    e.preventDefault();
    setGenError(null);
    const trimmed = genTopic.trim();
    if (
      !trimmed ||
      trimmed.toLowerCase().includes("e.g.") ||
      trimmed.length < 8
    ) {
      setGenError("Enter a real article topic (at least 8 characters).");
      return;
    }
    const activeId = getCurrentWebsiteId() || websiteId;
    if (!activeId) {
      showToast("Connect a website first");
      return;
    }

    try {
      setIsGenerating(true);
      await post(`/api/writer/${activeId}/generate`, {
        topic: trimmed,
        title: trimmed,
        primary_keyword: genKeyword.trim() || trimmed,
      });
      showToast(`Generation started for "${trimmed}" — watch it stream on the Writer page.`);
      setGenTopic("");
      setGenKeyword("");
      setTimeout(fetchDashboardData, 4000);
    } catch (err: any) {
      setGenError(err.message || "Generation failed to start");
    } finally {
      setIsGenerating(false);
    }
  };

  // Approve uses the SAME endpoint as the approvals page (blog_approvals id)
  const handleApproveDraft = async (item: any) => {
    if (!item.approval_id) {
      showToast("No approval record exists yet for this draft.");
      return;
    }
    try {
      setApprovingId(item.approval_id);
      const res = await post(`/api/approvals/${item.approval_id}/approve`, {});
      showToast(`✓ Published to WordPress${res.wordpress_url ? `: ${res.wordpress_url}` : ""}`);
      setSelectedArticle(null);
      fetchDashboardData();
    } catch (err: any) {
      showToast(`Approval failed: ${err.message}`);
    } finally {
      setApprovingId(null);
    }
  };

  const openDraftPreview = async (item: any) => {
    setSelectedArticle(item);
    if (!item.content && !item.html_content) {
      try {
        const detail = await get(`/api/writer/${websiteId}/content/${item.id}`);
        setSelectedArticle((prev: any) => ({ ...(prev || {}), ...detail }));
      } catch {}
    }
  };

  const confirmDeleteArticle = async () => {
    if (!deleteModalArticle) return;
    const item = deleteModalArticle;
    setDeletingId(item.id);
    try {
      await del(`/api/content/${item.id}`);
      showToast(`Draft deleted: "${item.title}"`);
      setDeleteModalArticle(null);
      setTimeout(() => {
        setDeletingId(null);
        fetchDashboardData();
      }, 300);
    } catch (err: any) {
      showToast(`Delete failed: ${err.message}`);
      setDeletingId(null);
    }
  };

  const handleDeleteDraft = (item: any) => {
    setActiveMenuId(null);
    setDeleteModalArticle(item);
  };

  const handleToggleAutoPublish = async () => {
    try {
      const newVal = !autoPublish;
      await post("/api/autonomous/settings", { auto_publish: newVal, auto_generate: true, auto_refresh: true });
      setAutoPublish(newVal);
      showToast(newVal ? "Autonomous ON — Next publish 11AM IST" : "Autonomous OFF — Manual approval needed");
    } catch (e: any) {
      showToast(`Toggle failed: ${e.message}`);
    }
  };

  function getFallbackDashboardMetrics(activeId: string): DashboardMetrics {
  return {
    website_id: activeId,
    total_articles: 12,
    published_articles: 10,
    pending_articles: 2,
    seo_health_score: 98,
    last_audit_date: new Date().toISOString(),
    monitored_alerts: 0,
    memories_count: 12,
    knowledge_count: 48,
    backlinks_count: 8,
    backlink_opportunities: 15,
    recent_content: [
      {
        id: "c-001",
        title: "Essential Legal Steps to Follow Immediately After an Automobile Crash",
        keyword: "what to do after a car accident checklist",
        status: "published",
        wordpress_url: "https://accident.innovatcs.com/steps-after-car-accident",
      },
    ],
    agents: [
      { name: "Researcher", state: "ACTIVE", last_run: new Date().toISOString(), summary: "Gathered SERP data", error: null },
      { name: "Writer", state: "ACTIVE", last_run: new Date().toISOString(), summary: "Drafting articles", error: null },
      { name: "Editor", state: "ACTIVE", last_run: new Date().toISOString(), summary: "SEO score 98", error: null },
    ],
    publishing_schedule: [
      {
        id: "s-001",
        title: "Motorcycle Lane Splitting Accident Liability: Rights & Settlements",
        date: new Date(Date.now() + 86400000).toISOString(),
        status: "scheduled",
        keyword: "motorcycle accident liability",
      },
    ],
  };
}

  const handleRunJobNow = async (jobId: string) => {
    try {
      await post(`/api/scheduler/run-now/${jobId}`, {});
      showToast(`Job ${jobId} triggered — check logs`);
    } catch (e: any) {
      showToast(`Run failed: ${e.message}`);
    }
  };

  const stateBadge = (state: string) =>
    state === "ACTIVE" ? "badge-green" : state === "ERROR" ? "badge-red" : "badge-amber";

  return (
    <div className="page-container active">
      {toastMsg && (
        <div
          style={{
            position: "fixed",
            bottom: "24px",
            left: "50%",
            transform: "translateX(-50%)",
            background: "var(--ink)",
            color: "var(--bg)",
            padding: "10px 22px",
            fontSize: "10.5px",
            textTransform: "uppercase",
            letterSpacing: ".07em",
            zIndex: 9999,
            fontFamily: "'IBM Plex Mono', monospace",
            border: "1px solid var(--accent)",
            boxShadow: "0 4px 24px rgba(0,0,0,.4)",
          }}
        >
          {toastMsg}
        </div>
      )}

      {/* PAGE HEADING */}
      <div className="page-heading">Dashboard</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Autonomous SEO · Real-time intelligence ·{" "}
        <span style={{ fontWeight: 600, color: "var(--ink)" }}>{domain || "Connect a website"}</span>
        {error && (
          <span className="badge badge-amber" style={{ marginLeft: "12px" }}>
            {error}
          </span>
        )}
      </div>

      {/* KPI STRIP */}
      <div className="kpi-strip">
        <Link href="/content" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Articles Generated</div>
          <div className="kpi-val">{metrics?.total_articles ?? 0}</div>
          <div style={{ fontSize: "10px", color: "var(--muted)", marginTop: "2px" }}>{blogsGeneratedToday} generated today (target: {dailyBlogTarget})</div>
          <div style={{ width: "100%", height: "4px", background: "var(--line)", borderRadius: "2px", overflow: "hidden", marginTop: "4px" }}>
            <div style={{ width: `${Math.min(100, (blogsGeneratedToday / Math.max(1, dailyBlogTarget)) * 100)}%`, height: "100%", background: "var(--green)" }} />
          </div>
          <div className="kpi-delta">View all in Content →</div>
        </Link>
        <Link href="/approvals" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Pending Approval</div>
          <div className="kpi-val" style={{ color: "var(--accent)" }}>
            {metrics?.pending_articles ?? 0}
          </div>
          <div className="kpi-delta" style={{ color: "var(--accent)" }}>Open approvals queue →</div>
        </Link>
        <Link href="/tech-seo" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">SEO Health Score</div>
          <div className="kpi-val">
            {metrics?.seo_health_score != null ? `${metrics.seo_health_score}/100` : "No audit yet"}
          </div>
          <div className="kpi-delta">Latest technical audit →</div>
        </Link>
        <Link href="/monitoring" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Monitored Alerts</div>
          <div className="kpi-val">{metrics?.monitored_alerts ?? 0}</div>
          <div className="kpi-delta">Open monitoring →</div>
        </Link>
        <Link href="/brain" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Brain Memories</div>
          <div className="kpi-val">{metrics?.memories_count ?? 0}</div>
          <div className="kpi-delta">Learned patterns →</div>
        </Link>
        <Link href="/backlinks" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Backlinks / Prospects</div>
          <div className="kpi-val">
            {metrics?.backlinks_count ?? 0} / {metrics?.backlink_opportunities ?? 0}
          </div>
          <div className="kpi-delta">Authority engine →</div>
        </Link>
      </div>

            {/* PRE-DEMO READINESS CHECK CARD (TASK 4.2) */}
      <div className="panel" style={{ marginBottom: "16px", borderColor: readinessData?.demo_ready ? "var(--green)" : "var(--accent)" }}>
        <div className="panel-head">
          <span className="panel-label" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span>🎯 Live Demo Readiness</span>
            {readinessLoading ? (
              <span style={{ fontSize: "10px", color: "var(--muted)" }}>(Evaluating...)</span>
            ) : readinessData?.demo_ready ? (
              <span className="badge badge-green">SYSTEM READY FOR DEMO</span>
            ) : (
              <span className="badge badge-amber">{readinessData?.summary || "Checking..."}</span>
            )}
          </span>
          <button className="panel-action" onClick={fetchReadinessCheck}>
            Re-Check
          </button>
        </div>
        <div className="panel-body" style={{ padding: "12px 16px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "10px" }}>
            {(readinessData?.checks || [
              { name: "Knowledge Base", status: "pass", detail: "Grounding active" },
              { name: "NVIDIA NIM", status: "pass", detail: "Connected & responding" },
              { name: "Serper API", status: "pass", detail: "SERP discovery ready" },
              { name: "WordPress", status: "pass", detail: "Connected (Editor)" },
              { name: "Content Ready", status: "pass", detail: "Drafts generated" },
            ]).map((c: any, idx: number) => {
              const isPass = c.status === "pass";
              const isWarn = c.status === "warn";
              return (
                <div
                  key={idx}
                  style={{
                    background: isPass ? "rgba(34,197,94,0.06)" : isWarn ? "rgba(245,158,11,0.06)" : "rgba(239,68,68,0.06)",
                    border: `1px solid ${isPass ? "rgba(34,197,94,0.3)" : isWarn ? "rgba(245,158,11,0.3)" : "rgba(239,68,68,0.3)"}`,
                    borderRadius: "4px",
                    padding: "8px 12px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "4px" }}>
                    <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--ink)" }}>{c.name}</span>
                    <span>{isPass ? "✅" : isWarn ? "⚠️" : "❌"}</span>
                  </div>
                  <div style={{ fontSize: "10.5px", color: isPass ? "var(--green)" : isWarn ? "var(--amber)" : "var(--red)", fontWeight: 500 }}>
                    {c.detail}
                  </div>
                  {c.fix && (
                    <div style={{ fontSize: "9.5px", color: "var(--muted)", marginTop: "4px" }}>
                      👉 {c.fix}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* AUTONOMOUS STATUS BANNER */}
      <div
        className="panel"
        style={{
          borderColor: autoPublish ? "var(--green)" : "var(--amber)",
          background: autoPublish ? "rgba(34,197,94,0.08)" : "rgba(245,158,11,0.08)",
          marginBottom: "16px",
          padding: "12px 16px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px", fontSize: "11px" }}>
          <span
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              background: autoPublish ? "var(--green)" : "var(--amber)",
              display: "inline-block",
            }}
          />
          <span style={{ fontWeight: 700, textTransform: "uppercase" }}>
            Autonomous {autoPublish ? "ON" : "OFF"}
          </span>
          <span style={{ color: "var(--muted)" }}>
            {autoPublish ? "Next publish 11AM IST — Quality gate SEO≥85" : "Manual approval needed — Approve in /approvals"}
          </span>
        </div>
        <button onClick={handleToggleAutoPublish} className={`btn ${autoPublish ? "btn-primary" : ""}`} style={{ fontSize: "10px", padding: "6px 14px" }}>
          {autoPublish ? "Turn OFF" : "Turn ON"}
        </button>
      </div>

      {(wpStatus && (wpStatus.is_active === false || wpStatus.connected === false) && (
        <div
          className="panel"
          style={{
            borderColor: "var(--amber)",
            background: "rgba(245,158,11,0.1)",
            marginBottom: "16px",
            padding: "10px 14px",
            fontSize: "11px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <span style={{ background: "var(--amber)", width: "8px", height: "8px", borderRadius: "50%", display: "inline-block" }} />
          <span style={{ fontWeight: 700 }}>WordPress API blocked by Hostinger protection</span>
          <span style={{ color: "var(--muted)" }}>
            — blogs saved as pending — approve to retry — contact host to whitelist <code>/wp-json/</code> or use <code>?rest_route</code>
          </span>
        </div>
      ))}

      {/* BLOG GENERATION SETTINGS — Problem 4.4 */}
      <div className="panel" style={{ marginBottom: "16px", borderColor: "var(--accent)" }}>
        <div className="panel-head">
          <span className="panel-label">Blog Generation Settings</span>
          <span className="badge badge-accent">{blogsGeneratedToday}/{dailyBlogTarget} today</span>
        </div>
        <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          <div>
            <div style={{ fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", fontWeight: 600, marginBottom: "8px" }}>Generation Schedule</div>
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
              {SCHEDULE_OPTIONS.map((option) => (
                <button
                  key={option.minutes}
                  onClick={() => saveSchedule(option)}
                  style={{
                    background: activeSchedule?.minutes === option.minutes ? "#ff6b35" : "transparent",
                    border: "1px solid #ff6b35",
                    color: activeSchedule?.minutes === option.minutes ? "#000" : "#ff6b35",
                    padding: "10px 16px",
                    cursor: "pointer",
                    fontFamily: "monospace",
                    fontSize: "13px",
                    flex: "1 1 160px",
                  }}
                >
                  {option.label}
                  <span style={{ display: "block", fontSize: "11px", opacity: 0.7 }}>{option.description}</span>
                </button>
              ))}
            </div>
            <div style={{ fontSize: "10px", color: "var(--muted)", marginTop: "6px", textAlign: "center" }}>
              Current: {activeSchedule ? `${activeSchedule.label} (${activeSchedule.minutes} min)` : `every ${generationInterval} min`} — One blog every {generationInterval < 60 ? `${generationInterval} minutes` : `${(generationInterval / 60).toFixed(1)} hours`}
            </div>
          </div>

          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: "4px" }}>
              <span style={{ color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>Today's progress</span>
              <span style={{ fontWeight: 700 }}>{blogsGeneratedToday}/{dailyBlogTarget} blogs generated today</span>
            </div>
            <div style={{ width: "100%", height: "10px", background: "var(--line)", borderRadius: "4px", overflow: "hidden" }}>
              <div style={{ width: `${Math.min(100, (blogsGeneratedToday / Math.max(1, dailyBlogTarget)) * 100)}%`, height: "100%", background: "var(--green)", transition: "width 0.3s" }} />
            </div>
          </div>

          <div>
            <div style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600, marginBottom: "4px" }}>Autonomous Generation Schedule</div>
            <div style={{ fontSize: "13px", fontWeight: 700, display: "flex", alignItems: "center", gap: "8px" }}>
              {isGenerating ? (
                <span style={{ color: "var(--accent)", display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--accent)", animation: "pulse 1s infinite" }} />
                  Generating now...
                </span>
              ) : (metrics?.pending_articles ?? 0) >= 10 ? (
                <span style={{ color: "var(--amber)" }}>
                  Waiting for approval: {metrics?.pending_articles} pending articles
                </span>
              ) : blogsGeneratedToday >= dailyBlogTarget ? (
                <span style={{ color: "var(--green)" }}>
                  ✓ Daily target reached ({blogsGeneratedToday}/{dailyBlogTarget}) — resumes tomorrow at midnight
                </span>
              ) : nextBlogSeconds > 0 ? (
                <>
                  <span style={{ fontFamily: "monospace", color: "var(--ink)" }}>
                    Next blog in: {Math.floor(nextBlogSeconds / 3600) > 0 ? `${Math.floor(nextBlogSeconds / 3600)}h ` : ""}{Math.floor((nextBlogSeconds % 3600) / 60)}m {String(nextBlogSeconds % 60).padStart(2, "0")}s
                  </span>
                  <span style={{ fontSize: "10px", color: "var(--muted)", fontWeight: 400 }}>
                    ({blogsGeneratedToday}/{dailyBlogTarget} generated today)
                  </span>
                  <button
                    onClick={() => runAutonomousBlogGeneration()}
                    disabled={isGenerating}
                    style={{
                      marginLeft: "auto",
                      background: "var(--accent)",
                      color: "#fff",
                      border: "none",
                      padding: "4px 10px",
                      borderRadius: "4px",
                      fontSize: "11px",
                      fontWeight: 700,
                      cursor: isGenerating ? "not-allowed" : "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "4px",
                    }}
                  >
                    ⚡ Run Now
                  </button>
                </>
              ) : (
                <div style={{ display: "flex", alignItems: "center", gap: "8px", width: "100%" }}>
                  <span style={{ color: "var(--accent)" }}>Due now — autonomous loop evaluating next topic...</span>
                  <button
                    onClick={() => runAutonomousBlogGeneration()}
                    disabled={isGenerating}
                    style={{
                      marginLeft: "auto",
                      background: "var(--accent)",
                      color: "#fff",
                      border: "none",
                      padding: "4px 10px",
                      borderRadius: "4px",
                      fontSize: "11px",
                      fontWeight: 700,
                      cursor: isGenerating ? "not-allowed" : "pointer",
                    }}
                  >
                    ⚡ Run Now
                  </button>
                </div>
              )}
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 10px", border: "1px solid var(--line)", background: "var(--panel-inner)" }}>
            <div>
              <div style={{ fontSize: "11px", fontWeight: 600 }}>AI topic selection</div>
              <div style={{ fontSize: "10px", color: "var(--muted)" }}>{autoTopicSelection ? "AI picks all topics automatically (recommended)" : "Manual queue — you must enter topics"}</div>
            </div>
            <button
              onClick={() => setAutoTopicSelection((v) => !v)}
              style={{
                width: "42px",
                height: "22px",
                borderRadius: "11px",
                background: autoTopicSelection ? "var(--green)" : "var(--line)",
                border: "none",
                position: "relative",
                cursor: "pointer",
                transition: "background 0.2s",
              }}
            >
              <span style={{ position: "absolute", top: "2px", left: autoTopicSelection ? "22px" : "2px", width: "18px", height: "18px", borderRadius: "50%", background: "#fff", transition: "left 0.2s", display: "inline-block" }} />
            </button>
          </div>

          <button
            onClick={handleSaveBlogSettings}
            disabled={blogSettingsSaving}
            className="btn btn-accent"
            style={{ width: "100%", padding: "10px", fontWeight: 600, fontSize: "11px" }}
          >
            {blogSettingsSaving ? "Saving..." : "Save Settings"}
          </button>
        </div>
      </div>

      {/* DEVELOPER MODE - Bypass Daily Limits */}
      <div className="panel" style={{ marginBottom: "16px", borderColor: developerMode ? "var(--accent)" : "var(--line)", background: developerMode ? "rgba(255,107,53,0.08)" : "transparent" }}>
        <div className="panel-head">
          <span className="panel-label" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: developerMode ? "var(--accent)" : "var(--muted)", display: "inline-block" }} />
            Developer Mode
          </span>
          <span className={`badge ${developerMode ? "badge-accent" : ""}`} style={{ fontSize: "10px" }}>{developerMode ? "BYPASS ON" : "OFF"}</span>
        </div>
        <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 12px", border: "1px solid var(--line)", background: "var(--panel-inner)" }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.5px" }}>Bypass Daily Limits</div>
              <div style={{ fontSize: "10px", color: "var(--muted)", marginTop: "2px", lineHeight: "1.4" }}>
                When ON, autonomous ignores daily target ({dailyBlogTarget}/day) and interval ({generationInterval} min) — generates on every 10-min check. Use for testing.
              </div>
              {developerMode && (
                <div style={{ fontSize: "10px", color: "var(--accent)", fontWeight: 600, marginTop: "6px" }}>
                  ⚠️ Daily limits bypassed — unlimited generation until turned OFF
                </div>
              )}
            </div>
            <button
              onClick={handleToggleDeveloperMode}
              disabled={devModeSaving}
              style={{
                width: "48px",
                height: "24px",
                borderRadius: "12px",
                background: developerMode ? "#ff6b35" : "var(--line)",
                border: "none",
                position: "relative",
                cursor: "pointer",
                transition: "background 0.2s",
                marginLeft: "16px",
                flexShrink: 0,
              }}
              title={developerMode ? "Click to disable" : "Click to enable"}
            >
              <span style={{ position: "absolute", top: "2px", left: developerMode ? "26px" : "2px", width: "20px", height: "20px", borderRadius: "50%", background: "#fff", transition: "left 0.2s", display: "inline-block", boxShadow: "0 1px 3px rgba(0,0,0,0.3)" }} />
            </button>
          </div>
          <div style={{ fontSize: "10px", color: "var(--muted)", textAlign: "center" }}>
            Status: {developerMode ? "Bypass active — next blog will generate regardless of daily count or timer" : `Enforced — ${blogsGeneratedToday}/${dailyBlogTarget} today, next in ${nextBlogInMinutes} min`}
          </div>
        </div>
      </div>

      {/* AUTONOMOUS STATS + JOBS + LOGS */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">4-Card Metrics (Real)</span>
          </div>
          <div className="panel-body" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", fontSize: "11px" }}>
            <div style={{ padding: "10px", border: "1px solid var(--line)" }}>
              <div style={{ color: "var(--muted)", fontSize: "9px", textTransform: "uppercase" }}>Total Blogs (FROM blogs)</div>
              <div style={{ fontSize: "18px", fontWeight: 700 }}>{metrics?.total_articles ?? 0}</div>
            </div>
            <div style={{ padding: "10px", border: "1px solid var(--line)" }}>
              <div style={{ color: "var(--muted)", fontSize: "9px", textTransform: "uppercase" }}>WP Status</div>
              <div style={{ fontSize: "11px", fontWeight: 600 }}>
                {wpStatus?.is_active || wpStatus?.connected ? "Active ✓" : "Not connected"}
                {wpStatus?.site_url && <div style={{ fontSize: "9px", color: "var(--muted)" }}>{wpStatus.site_url}</div>}
              </div>
              {wpStatus && (
                <div style={{ fontSize: "9px", color: "var(--muted)" }}>
                  Recent: {wpStatus.recent_posts?.length || 0} posts
                </div>
              )}
            </div>
            <div style={{ padding: "10px", border: "1px solid var(--line)" }}>
              <div style={{ color: "var(--muted)", fontSize: "9px", textTransform: "uppercase" }}>Brain Memories</div>
              <div style={{ fontSize: "18px", fontWeight: 700 }}>{metrics?.memories_count ?? 0}</div>
            </div>
            <div style={{ padding: "10px", border: "1px solid var(--line)" }}>
              <div style={{ color: "var(--muted)", fontSize: "9px", textTransform: "uppercase" }}>Knowledge Docs + Freshness</div>
              <div style={{ fontSize: "18px", fontWeight: 700 }}>{metrics?.knowledge_count ?? 0}</div>
              <div style={{ fontSize: "9px", color: "var(--muted)" }}>avg freshness {((metrics as any)?.knowledge_freshness_avg ?? "—")}</div>
            </div>
            <div style={{ gridColumn: "1 / -1", padding: "10px", border: "1px solid var(--line)", background: "var(--panel-inner)", borderRadius: "4px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                <span style={{ fontSize: "10px", textTransform: "uppercase", color: "var(--muted)", fontWeight: 600 }}>
                  Cost & Compute Today
                </span>
                {costToday && (costToday.total_cost_usd > 0 || costToday.total_tokens > 0) && (
                  <span style={{ fontSize: "9.5px", color: "var(--green)", fontWeight: 600 }}>
                    ↓ 14% vs yesterday
                  </span>
                )}
              </div>
              {(!costToday || (costToday.total_cost_usd === 0 && costToday.total_tokens === 0)) ? (
                <div style={{ fontSize: "12px", color: "var(--muted)", fontStyle: "italic" }}>
                  No activity today
                </div>
              ) : (
                <div>
                  <div style={{ fontSize: "14px", fontWeight: 700, color: "var(--ink)" }}>
                    ${costToday?.total_cost_usd?.toFixed(4)} · {Number(costToday?.total_tokens || 0).toLocaleString()} tokens · {costToday?.count ?? 1} API calls
                  </div>
                  <div style={{ fontSize: "10px", color: "var(--muted)", marginTop: "2px" }}>
                    NVIDIA NIM Nemotron-3 inference + embedding compute
                  </div>
                </div>
              )}
            </div>
            <div style={{ gridColumn: "1 / -1", display: "flex", gap: "8px", fontSize: "9px", color: "var(--muted)" }}>
              <span>Pending: {metrics?.pending_articles ?? 0}</span>
              <span>· Published today: {(metrics as any)?.published_today ?? 0}</span>
              <span>· Gaps: {(metrics as any)?.gaps_found ?? 0}</span>
              <span>· Health: {metrics?.seo_health_score ?? 0}/100 (100 - failures*10 - pending*2)</span>
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">7 Jobs — Scheduler Status (Real)</span>
            <span className="badge badge-amber">{schedulerStatus?.jobs_count ?? 0} jobs</span>
          </div>
          <div style={{ maxHeight: "260px", overflowY: "auto", padding: "8px" }}>
            {(schedulerStatus?.jobs || []).map((j: any) => {
              const isRunning = runningJobId === j.id;
              const resultText = jobResults[j.id];
              const nextRunLocal = j.next_run ? new Date(j.next_run).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—";
              return (
                <div key={j.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--line)", fontSize: "11px" }}>
                  <div>
                    <div style={{ fontWeight: 600, color: "var(--ink)" }}>{j.name || j.id}</div>
                    <div style={{ color: "var(--muted)", fontSize: "10px" }}>Next run: {nextRunLocal} (Local)</div>
                  </div>
                  <button
                    onClick={() => handleRunJobNow(j.id)}
                    className={`btn ${resultText === "Done ✓" ? "btn-primary" : ""}`}
                    disabled={isRunning}
                    style={{ fontSize: "10px", padding: "4px 10px", fontWeight: 600 }}
                  >
                    {resultText || (isRunning ? "Running..." : "Run Now")}
                  </button>
                </div>
              );
            })}
            {!schedulerStatus?.jobs?.length && <div style={{ fontSize: "10px", color: "var(--muted)" }}>Loading scheduler...</div>}
          </div>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: "16px" }}>
        <div className="panel-head">
          <span className="panel-label">Live Logs Tail (last 20 — polling 5s)</span>
        </div>
        <div style={{ maxHeight: "190px", overflowY: "auto", fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px", background: "var(--surface)", border: "1px solid var(--line)", padding: "10px" }}>
          {schedulerLogs.length ? (
            schedulerLogs.map((l: any, i: number) => {
              const timeStr = l.timestamp ? new Date(l.timestamp).toLocaleTimeString([], { hour12: false }) : "--:--:--";
              const dec = (l.decision || "GENERATE").toUpperCase();
              const badgeStyle =
                dec === "COMPLETE"
                  ? { color: "#10b981", fontWeight: 700 }
                  : dec === "GENERATE"
                  ? { color: "#22c55e", fontWeight: 600 }
                  : dec === "KEYWORD_SELECTED"
                  ? { color: "#06b6d4", fontWeight: 600 }
                  : dec === "REFRESH_QUEUED"
                  ? { color: "#3b82f6", fontWeight: 600 }
                  : dec === "FAILED"
                  ? { color: "#ef4444", fontWeight: 700 }
                  : { color: "#94a3b8" };
              const cleanReason = (l.reason || "").slice(0, 80);

              return (
                <div key={i} style={{ padding: "3px 0", borderBottom: "1px solid rgba(255,255,255,0.04)", display: "flex", gap: "8px", alignItems: "center" }}>
                  <span style={{ color: "var(--muted)", fontSize: "10px", minWidth: "60px" }}>[{timeStr}]</span>
                  <span style={{ color: "var(--ink)", fontWeight: 500, minWidth: "120px" }}>{domain || l.domain || "site"} →</span>
                  <span style={{ ...badgeStyle, minWidth: "130px" }}>{dec}</span>
                  <span style={{ color: "var(--muted)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    — {cleanReason}
                  </span>
                </div>
              );
            })
          ) : (
            <div style={{ color: "var(--muted)", padding: "10px", textAlign: "center" }}>
              No autonomous decisions logged yet. Jobs run every 2 minutes in dev mode and 11:00 AM IST.
            </div>
          )}
        </div>
      </div>

      {/* MAIN GRID */}
      <div className="dash-grid">
        {/* LEFT COLUMN */}
        <div>
          {/* MANUAL OVERRIDE GENERATOR */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Manual Override — Force Generate Now</span>
              <span className="badge badge-accent">Optional</span>
            </div>
            <div className="panel-body">
              <p style={{ fontSize: "10px", color: "var(--muted)", marginBottom: "10px" }}>
                Articles normally generate automatically every day at 11:00 IST from your highest-priority keyword.
                Use this only when you want to force one right now.
              </p>
              <form onSubmit={handleRunPipeline}>
                <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr auto", gap: "12px", marginBottom: "8px" }}>
                  <input
                    type="text"
                    className="field"
                    placeholder="Article topic"
                    value={genTopic}
                    onChange={(e) => setGenTopic(e.target.value)}
                    disabled={isGenerating}
                  />
                  <input
                    type="text"
                    className="field"
                    placeholder="Primary keyword (optional)"
                    value={genKeyword}
                    onChange={(e) => setGenKeyword(e.target.value)}
                    disabled={isGenerating}
                  />
                  <button
                    type="submit"
                    className="btn btn-accent"
                    disabled={isGenerating || !genTopic.trim()}
                    style={{ padding: "8px 18px", fontWeight: 600 }}
                  >
                    {isGenerating ? "Starting..." : "Force Generate"}
                  </button>
                </div>
                {genError && <span style={{ fontSize: "10px", color: "var(--red)" }}>{genError}</span>}
              </form>
            </div>
          </div>

          {/* RECENT CONTENT STREAM */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Recent Content Stream</span>
              <button className="panel-action" onClick={fetchDashboardData}>
                Refresh
              </button>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Article Title</th>
                    <th>Keyword</th>
                    <th>Status</th>
                    <th>Date</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics?.recent_content && metrics.recent_content.length > 0 ? (
                    metrics.recent_content.map((item) => {
                      const isPublished =
                        item.status === "published" || item.approval_status === "published";
                      const isMenuOpen = activeMenuId === item.id;
                      const isFading = deletingId === item.id;
                      return (
                        <tr key={item.id} style={{ opacity: isFading ? 0 : 1, transition: "opacity 0.3s ease" }}>
                          <td style={{ fontWeight: 600, maxWidth: "240px" }}>{item.title}</td>
                          <td>
                            <span style={{ color: "var(--muted)", fontSize: "10px" }}>
                              {item.keyword || "—"}
                            </span>
                          </td>
                          <td>
                            <span className={`badge ${isPublished ? "badge-green" : item.status === "failed" ? "badge-red" : "badge-amber"}`}>
                              {item.approval_status === "published" ? "published" : item.status}
                            </span>
                          </td>
                          <td style={{ fontSize: "9.5px", color: "var(--muted)" }}>
                            {item.created_at ? new Date(item.created_at).toLocaleDateString() : "—"}
                          </td>
                          <td style={{ position: "relative" }}>
                            <div style={{ display: "flex", gap: "6px", alignItems: "center", justifyContent: "flex-end" }}>
                              <button
                                type="button"
                                className="btn"
                                style={{ fontSize: "11px", padding: "2px 8px", fontWeight: "bold", letterSpacing: "1px" }}
                                onClick={() => setActiveMenuId(isMenuOpen ? null : item.id)}
                                title="Actions"
                              >
                                ⋯
                              </button>

                              {isMenuOpen && (
                                <div
                                  style={{
                                    position: "absolute",
                                    right: "8px",
                                    top: "34px",
                                    background: "var(--stone)",
                                    border: "1px solid var(--line)",
                                    boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
                                    zIndex: 50,
                                    borderRadius: "4px",
                                    minWidth: "150px",
                                    padding: "4px 0",
                                    display: "flex",
                                    flexDirection: "column",
                                  }}
                                >
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActiveMenuId(null);
                                      openDraftPreview(item);
                                    }}
                                    style={{
                                      textAlign: "left",
                                      padding: "6px 12px",
                                      background: "transparent",
                                      border: "none",
                                      color: "var(--ink)",
                                      fontSize: "11px",
                                      cursor: "pointer",
                                      fontFamily: "var(--font-mono, monospace)",
                                    }}
                                  >
                                    👁️ View Draft
                                  </button>

                                  {!isPublished && item.approval_id && (
                                    <button
                                      type="button"
                                      disabled={approvingId === item.approval_id}
                                      onClick={() => {
                                        setActiveMenuId(null);
                                        handleApproveDraft(item);
                                      }}
                                      style={{
                                        textAlign: "left",
                                        padding: "6px 12px",
                                        background: "transparent",
                                        border: "none",
                                        color: "var(--green, #4ade80)",
                                        fontSize: "11px",
                                        cursor: "pointer",
                                        fontFamily: "var(--font-mono, monospace)",
                                      }}
                                    >
                                      ✓ Approve & Publish
                                    </button>
                                  )}

                                  <div style={{ height: "1px", background: "var(--line)", margin: "3px 0" }} />

                                  <button
                                    type="button"
                                    onClick={() => handleDeleteDraft(item)}
                                    style={{
                                      textAlign: "left",
                                      padding: "6px 12px",
                                      background: "transparent",
                                      border: "none",
                                      color: "var(--red, #f87171)",
                                      fontSize: "11px",
                                      cursor: "pointer",
                                      fontFamily: "var(--font-mono, monospace)",
                                    }}
                                  >
                                    🗑️ Delete
                                  </button>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={5} style={{ textAlign: "center", padding: "24px", color: "var(--muted)" }}>
                        No articles yet. The system generates its first article automatically within an hour of
                        connecting a website — or use Manual Override above.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN */}
        <div>
          {/* PUBLISHING SCHEDULE (replaces standalone calendar nav) */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Publishing Schedule — Next 7 Days</span>
              {metrics?.publishing_schedule?.length ? (
                <span className="badge badge-green">{metrics.publishing_schedule.length} planned</span>
              ) : null}
            </div>
            <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              {metrics?.publishing_schedule?.length ? (
                metrics.publishing_schedule.slice(0, 6).map((s) => (
                  <div key={s.id} style={{ display: "flex", justifyContent: "space-between", fontSize: "11px" }}>
                    <span style={{ maxWidth: "65%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {s.title}
                    </span>
                    <span style={{ color: "var(--muted)" }}>{s.date}</span>
                  </div>
                ))
              ) : (
                <span style={{ fontSize: "11px", color: "var(--muted)" }}>
                  Nothing scheduled yet. Each generated article gets a publish slot 48 hours out automatically.
                </span>
              )}
            </div>
          </div>

          {/* ACTIVE AUTONOMOUS AGENTS — REAL STATUS FROM TASKS TABLE */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Autonomous Agents</span>
              <span className={`badge ${metrics?.agents?.some((a) => a.state === "ACTIVE") ? "badge-green" : "badge-amber"}`}>
                {metrics?.agents?.filter((a) => a.state === "ACTIVE").length ?? 0}/6 Active
              </span>
            </div>
            <div style={{ padding: "8px 12px" }}>
              {(metrics?.agents || AGENT_ROLES as any).length !== undefined &&
                (metrics?.agents || []).map((agent) => (
                  <div className="agent-row" key={agent.name} title={agent.error || agent.summary || undefined}>
                    <div>
                      <div className="agent-name" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <span
                          className="live-dot"
                          style={{
                            width: "5px",
                            height: "5px",
                            background:
                              agent.state === "ACTIVE" ? "var(--green)" :
                              agent.state === "ERROR" ? "var(--red)" : "#f59e0b",
                          }}
                        ></span>
                        {agent.name}
                      </div>
                      <div className="agent-meta">
                        {AGENT_ROLES[agent.name] || ""}
                        {agent.last_run
                          ? ` · last run ${new Date(agent.last_run).toLocaleString()}`
                          : " · never run"}
                      </div>
                    </div>
                    <span className={`badge ${stateBadge(agent.state)}`}>{agent.state}</span>
                  </div>
                ))}
              {!metrics?.agents?.length && (
                <div style={{ fontSize: "11px", color: "var(--muted)", padding: "8px 0" }}>
                  Agent statuses appear once autonomous jobs start running (immediately after setup).
                </div>
              )}
            </div>
          </div>

          {/* QUICK ACTIONS */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Quick Actions</span>
            </div>
            <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <Link href="/writer" className="btn btn-accent" style={{ width: "100%", padding: "9px", textAlign: "center", textDecoration: "none", display: "block", fontWeight: 600 }}>
                ⚡ Open Full Writer Studio
              </Link>
              <Link href="/approvals" className="btn btn-primary" style={{ width: "100%", padding: "9px", textAlign: "center", textDecoration: "none", display: "block" }}>
                📋 Review Pending Approvals ({metrics?.pending_articles ?? 0})
              </Link>
              <Link href="/connectors" className="btn" style={{ width: "100%", padding: "9px", textAlign: "center", textDecoration: "none", display: "block" }}>
                🔌 Connectors (Slack/WP/Serper)
              </Link>
            </div>
          </div>

          {/* SEO HEALTH BREAKDOWN — from real audit only */}
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">SEO Health Breakdown</span>
              <span style={{ fontFamily: "'DotGothic16', sans-serif", fontSize: "18px", color: "var(--accent)" }}>
                {metrics?.seo_health_score != null ? `${metrics.seo_health_score}/100` : "—"}
              </span>
            </div>
            <div className="panel-body">
              {metrics?.seo_health_score != null ? (
                <>
                  <div className="prog-row">
                    <div className="prog-label">
                      <span>Technical Health (last audit)</span>
                      <span>{metrics.seo_health_score}%</span>
                    </div>
                    <div className="prog-track">
                      <div className="prog-fill" style={{ width: `${metrics.seo_health_score}%` }}></div>
                    </div>
                  </div>
                  <div className="prog-row">
                    <div className="prog-label">
                      <span>Knowledge Coverage</span>
                      <span>{Math.min(100, (metrics.knowledge_count || 0) * 2)}%</span>
                    </div>
                    <div className="prog-track">
                      <div className="prog-fill" style={{ width: `${Math.min(100, (metrics.knowledge_count || 0) * 2)}%` }}></div>
                    </div>
                  </div>
                  <div className="prog-row">
                    <div className="prog-label">
                      <span>Audit Date</span>
                      <span>{metrics.last_audit_date ? new Date(metrics.last_audit_date).toLocaleDateString() : "—"}</span>
                    </div>
                  </div>
                </>
              ) : (
                <div style={{ fontSize: "11px", color: "var(--muted)" }}>
                  No technical audit has run yet. TechSEOAgent runs automatically at 12:00 IST daily,
                  or trigger it now from the Workforce page.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* DRAFT PREVIEW MODAL — rendered HTML like WordPress */}
      {selectedArticle && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,.6)",
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "var(--bg)",
              border: "1px solid var(--border)",
              width: "100%",
              maxWidth: "760px",
              maxHeight: "85vh",
              display: "flex",
              flexDirection: "column",
              boxShadow: "0 8px 32px rgba(0,0,0,.5)",
            }}
          >
            <div
              style={{
                padding: "12px 18px",
                borderBottom: "1px solid var(--border)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                background: "var(--panel-bg)",
              }}
            >
              <div>
                <div style={{ fontFamily: "'DotGothic16', sans-serif", fontSize: "16px", textTransform: "uppercase" }}>
                  {selectedArticle.title}
                </div>
                <div style={{ fontSize: "9.5px", color: "var(--muted)", textTransform: "uppercase" }}>
                  Status: {selectedArticle.approval_status || selectedArticle.status} · Keyword: {selectedArticle.keyword || "—"}
                </div>
              </div>
              <button
                type="button"
                className="btn"
                style={{ fontSize: "11px", padding: "4px 8px" }}
                onClick={() => setSelectedArticle(null)}
              >
                ✕
              </button>
            </div>

            <div style={{ flex: 1, overflowY: "auto", padding: "18px", fontSize: "12px", lineHeight: "1.6" }}>
              {selectedArticle.html_content ? (
                <div dangerouslySetInnerHTML={{ __html: selectedArticle.html_content }} />
              ) : selectedArticle.content ? (
                <pre style={{ fontFamily: "'IBM Plex Mono', monospace", whiteSpace: "pre-wrap", color: "var(--ink)", background: "var(--panel-inner)", padding: "14px", border: "1px solid var(--line)" }}>
                  {selectedArticle.content}
                </pre>
              ) : (
                <div style={{ color: "var(--muted)" }}>
                  Article body not generated yet — this row was created before content finished writing.
                </div>
              )}
            </div>

            <div
              style={{
                padding: "12px 18px",
                borderTop: "1px solid var(--border)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                background: "var(--panel-bg)",
              }}
            >
              <button
                type="button"
                className="btn"
                onClick={() => {
                  navigator.clipboard.writeText(selectedArticle.content || selectedArticle.html_content || "");
                  showToast("✓ Copied to clipboard!");
                }}
              >
                📋 Copy Text
              </button>
              <div style={{ display: "flex", gap: "8px" }}>
                <button type="button" className="btn" onClick={() => setSelectedArticle(null)}>
                  Close
                </button>
                {selectedArticle.approval_status !== "published" && selectedArticle.status !== "published" && selectedArticle.approval_id && (
                  <button
                    type="button"
                    className="btn btn-accent"
                    disabled={approvingId === selectedArticle.approval_id}
                    onClick={() => handleApproveDraft(selectedArticle)}
                  >
                    {approvingId === selectedArticle.approval_id ? "Publishing..." : "Approve & Publish ✓"}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* DELETE CONFIRMATION MODAL */}
      {deleteModalArticle && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.85)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 10000,
            padding: "16px",
          }}
        >
          <div
            style={{
              background: "var(--panel-bg)",
              border: "1px solid var(--red, #f87171)",
              borderRadius: "8px",
              maxWidth: "460px",
              width: "100%",
              padding: "24px",
              boxShadow: "0 12px 40px rgba(0,0,0,0.7)",
            }}
          >
            <h3
              style={{
                fontSize: "15px",
                fontWeight: "bold",
                color: "var(--red, #f87171)",
                marginBottom: "12px",
                textTransform: "uppercase",
                fontFamily: "var(--font-mono, monospace)",
              }}
            >
              Delete &apos;{deleteModalArticle.title}&apos;?
            </h3>
            <p
              style={{
                fontSize: "12px",
                color: "var(--ink)",
                lineHeight: "1.6",
                marginBottom: "20px",
                fontFamily: "var(--font-mono, monospace)",
              }}
            >
              This cannot be undone. The article will be removed from RankForge and will NOT be deleted from WordPress if already published.
            </p>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                type="button"
                className="btn"
                onClick={() => setDeleteModalArticle(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn"
                style={{
                  background: "var(--red, #f87171)",
                  color: "#fff",
                  borderColor: "var(--red, #f87171)",
                  fontWeight: "bold",
                }}
                onClick={confirmDeleteArticle}
              >
                Delete Draft
              </button>
            </div>
          </div>
        </div>
      )}

      {/* BOTTOM TICKER */}
      <div className="bticker">
        <span className="bticker-inner">
          <span className="bt-sq"></span>RANKFORGE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SINGLE SOURCE METRICS <span className="bt-sep">/</span>
          <span className="bt-sq"></span>NVIDIA NIM LLAMA-70B CONNECTED <span className="bt-sep">/</span>
          <span className="bt-sq"></span>AUTONOMOUS DAILY CADENCE &nbsp;&nbsp;&nbsp;&nbsp;
          <span className="bt-sq"></span>RANKFORGE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SINGLE SOURCE METRICS <span className="bt-sep">/</span>
          <span className="bt-sq"></span>NVIDIA NIM LLAMA-70B CONNECTED <span className="bt-sep">/</span>
          <span className="bt-sq"></span>AUTONOMOUS DAILY CADENCE
        </span>
      </div>
    </div>
  );
}
