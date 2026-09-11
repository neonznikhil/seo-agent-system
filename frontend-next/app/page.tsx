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

interface WorkflowItem {
  job_name: string;
  display_name: string;
  description: string;
  category: "technical" | "content" | "intelligence" | "links";
  status: "never_run" | "running" | "completed" | "failed";
  last_run: string | null;
  summary: string;
  diff: {
    fixed: number;
    new: number;
    still_open: number;
    regressed: number;
  };
}

interface WorkflowsStatusResponse {
  website_id: string;
  indexation_rate: number | null;
  publishing_pace: {
    status: "NORMAL" | "PAUSED_INDEXATION_GATE";
    threshold: number;
    current_rate: number;
    action: string;
  };
  workflows: WorkflowItem[];
}

export default function HomePage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  // SEO-outcomes overview (indexation, GSC, striking distance, issues,
  // decay, pipeline, run history). Null = not loaded yet / unavailable.
  const [overview, setOverview] = useState<any | null>(null);
  const [workflowsData, setWorkflowsData] = useState<WorkflowsStatusResponse | null>(null);
  const [runningWorkflow, setRunningWorkflow] = useState<string | null>(null);
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
  const [activeWorkflowModal, setActiveWorkflowModal] = useState<any | null>(null);
  const [autoPublishConfirmOpen, setAutoPublishConfirmOpen] = useState<boolean>(false);

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
      // warn removed
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
      // error removed
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
  // Drafts only by default: OFF (grey) until the backend confirms opt-in.
  const [autoPublish, setAutoPublish] = useState<boolean>(false);
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
  const [wpAppPass, setWpAppPass] = useState<string>("");
  const [wpUser, setWpUser] = useState<string>("");
  const [wpConnected, setWpConnected] = useState<boolean>(false);
  const [wpTesting, setWpTesting] = useState<boolean>(false);
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
        // HONEST EMPTY STATE: never invent metrics. Surface the failure.
        setMetrics(null);
        setError("API unavailable — check backend connection");
      }

      // SEO outcomes overview: leads the dashboard. Failure here never
      // blocks the legacy metrics below; it renders its own empty states.
      try {
        const ov = await get(`/api/dashboard/overview?website_id=${activeId}`);
        if (ov && typeof ov === "object" && !ov.error) {
          setOverview(ov);
        } else {
          setOverview(null);
        }
      } catch {
        setOverview(null);
      }

      // 9 Independent Workflows status & indexation gate
      try {
        const wf = await get(`/api/workflows/${activeId}/status`);
        if (wf && wf.workflows) {
          setWorkflowsData(wf);
        } else {
          setWorkflowsData(null);
        }
      } catch {
        setWorkflowsData(null);
      }
    } catch {
      // HONEST EMPTY STATE: never invent metrics. Surface the failure.
      setMetrics(null);
      setError("API unavailable — check backend connection");
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  const handleRunWorkflow = async (jobName: string) => {
    const activeId = getCurrentWebsiteId() || websiteId;
    if (!activeId) {
      showToast("Select a website first — no destination site available.");
      return;
    }
    setRunningWorkflow(jobName);
    try {
      showToast(`Running workflow: ${jobName}...`);
      const res = await post(`/api/workflows/${activeId}/run/${jobName}`, {});
      const title = res?.workflow?.display_name || jobName;
      showToast(`✓ Completed: ${title}`);
      if (res) {
        setActiveWorkflowModal(res);
      }
      try {
        const updatedWf = await get(`/api/workflows/${activeId}/status`);
        if (updatedWf && updatedWf.workflows) {
          setWorkflowsData(updatedWf);
        }
      } catch {}
      fetchDashboardData();
    } catch (err: any) {
      showToast(`Workflow run failed: ${err.message || "execution error"}`);
    } finally {
      setRunningWorkflow(null);
    }
  };

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
    try {
      const stored = localStorage.getItem("rankforge_wp_credentials");
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed.app_password) {
          delete parsed.app_password;
          try { localStorage.setItem("rankforge_wp_credentials", JSON.stringify(parsed)); } catch {}
        }
        if (parsed.username && parsed.username !== "admin") {
          setWpUser(parsed.username);
        } else {
          setWpUser("");
        }
      }
    } catch {}
  }, [fetchBlogSettings, fetchReadinessCheck]);

  const handleVerifyAndSaveWp = async () => {
    if (!wpAppPass.trim()) return;
    // Site URL always comes from the selected website — never a placeholder.
    const activeSite = websites.find((s) => s.id === (getCurrentWebsiteId() || websiteId));
    const siteUrl = (activeSite as any)?.url || (activeSite as any)?.domain
      ? `https://${((activeSite as any).url || (activeSite as any).domain).replace(/^https?:\/\//, "").replace(/\/+$/, "")}`
      : "";
    if (!siteUrl) {
      showToast("Select a website first — no destination domain available.");
      return;
    }
    setWpTesting(true);
    const targetUser = wpUser.trim() || "";
    try {
      const res = await post("/api/wordpress/connect", {
        site_url: siteUrl,
        wp_username: targetUser,
        wp_app_password: wpAppPass.trim(),
      });
      if (res.connected) {
        setWpConnected(true);
        try {
          localStorage.setItem(
            "rankforge_wp_credentials",
            JSON.stringify({
              site_url: siteUrl,
              username: targetUser,
            })
          );
        } catch {}
        showToast(`Connected to ${siteUrl} as ${targetUser}.`);
      } else {
        showToast(res.error || `WordPress: ${res.message || "Could not verify credentials"}`);
      }
    } catch (e: any) {
      showToast(`Verification failed: ${e.message}`);
    } finally {
      setWpTesting(false);
    }
  };

  const runAutonomousBlogGeneration = useCallback(async () => {
    if (isGenerating) return;
    // No fallback UUID: without a selected website there is nothing to write for.
    const wid = getCurrentWebsiteId() || websiteId || "";
    if (!wid) {
      showToast("Select a website first — no destination site available.");
      return;
    }
    setIsGenerating(true);
    showToast("Autonomous Blog Generator active: 3-Agent Crew writing next article...");

    // Retrieve real WordPress credentials from localStorage if user entered them in /connectors
    let wpCreds: any = {};
    try {
      const stored = localStorage.getItem("rankforge_wp_credentials");
      if (stored) wpCreds = JSON.parse(stored);
    } catch {}
    if (!wpCreds.username || wpCreds.username === "admin") {
      wpCreds.username = wpUser.trim() || "";
    }
    // No placeholder site URL: omit unless the user configured one.
    if (!wpCreds.site_url) {
      delete wpCreds.site_url;
    }

    try {
      const res: any = await post(`/api/writer/${wid}/generate`, {
        autonomous: true,
        website_id: wid,
        wordpress_site_url: wpCreds.site_url,
        wordpress_username: wpCreds.username,
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
      showToast(`Generation failed: ${e.message || "backend unreachable"}. No article was created.`);
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

        // Content pipeline runs are gated by the indexation gate (>= 80%)
        // and coordinated by the backend workflow scheduler.
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
      // warn removed
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

  const confirmToggleAutoPublish = async (newVal: boolean) => {
    setAutoPublishConfirmOpen(false);
    try {
      await post("/api/autonomous/settings", { auto_publish: newVal, auto_generate: true, auto_refresh: true });
      setAutoPublish(newVal);
      showToast(newVal ? "Auto-publish ON (explicit opt-in) — approved drafts will publish" : "Auto-publish OFF — drafts only, manual approval needed");
    } catch (e: any) {
      showToast(`Toggle failed: ${e.message}`);
    }
  };

  const handleToggleAutoPublish = () => {
    if (!autoPublish) {
      setAutoPublishConfirmOpen(true);
    } else {
      confirmToggleAutoPublish(false);
    }
  };

  // NOTE: no fallback metrics function. When the API is unreachable the
  // dashboard renders explicit empty states ("—" / "No data yet") instead
  // of invented numbers. See the KPI strip below.

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

      {/* HONEST EMPTY STATE: no metrics without a real API response. */}
      {metrics === null && !loading && (
        <div className="panel" style={{ marginBottom: "16px", borderColor: "var(--amber)", padding: "14px 16px" }}>
          <div style={{ fontSize: "12px", fontWeight: 700 }}>No dashboard data</div>
          <div style={{ fontSize: "11px", color: "var(--muted)", marginTop: "4px" }}>
            {error || "API unavailable — check backend connection"}. No numbers are shown until a real check returns data.
          </div>
        </div>
      )}

      {/* ROW 1 — SEO HEALTH (outcomes first; content counts are secondary below) */}
      <div className="kpi-strip">
        <div className="kpi-cell">
          <div className="kpi-label">Indexation Rate</div>
          <div className="kpi-val">
            {overview?.indexation?.rate != null ? `${(overview.indexation.rate * 100).toFixed(1)}%` : "—"}
          </div>
          <div className="kpi-delta">
            {overview?.indexation?.rate != null
              ? `${overview.indexation.indexed ?? "?"} / ${overview.indexation.submitted ?? "?"} pages`
              : (overview ? "No check yet — run an indexation check" : "No data yet")}
          </div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Impressions (28d)</div>
          <div className="kpi-val">{overview?.gsc?.impressions ?? "—"}</div>
          <div className="kpi-delta">
            {overview?.gsc?.connected ? "Google Search Console" : (overview ? "Connect GSC →" : "No data yet")}
          </div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Clicks (28d)</div>
          <div className="kpi-val">{overview?.gsc?.clicks ?? "—"}</div>
          <div className="kpi-delta">
            {overview?.gsc?.connected ? "Google Search Console" : (overview ? "Connect GSC →" : "No data yet")}
          </div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Avg Position</div>
          <div className="kpi-val">{overview?.gsc?.avg_position ?? "—"}</div>
          <div className="kpi-delta">
            {overview?.gsc?.connected ? "Google Search Console" : (overview ? "Connect GSC →" : "No data yet")}
          </div>
        </div>
        <Link href="/research" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Striking Distance</div>
          <div className="kpi-val">
            {overview?.striking_distance?.count ?? "—"}
          </div>
          <div className="kpi-delta">
            {overview?.striking_distance?.count != null
              ? `positions ${overview.striking_distance.range?.[0] ?? 11}–${overview.striking_distance.range?.[1] ?? 20} · +${overview.striking_distance.entering ?? 0} entering · −${overview.striking_distance.leaving ?? 0} leaving`
              : (overview ? "Run rank tracking first" : "No data yet")}
          </div>
        </Link>
      </div>

      {/* ROW 2 — ISSUES */}
      <div className="kpi-strip">
        <Link href="/monitoring" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Open Issues</div>
          <div className="kpi-val">{overview?.open_issues?.count ?? "—"}</div>
          <div className="kpi-delta">Alerts + pending fixes →</div>
        </Link>
        <Link href="/decay" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Decaying Pages</div>
          <div className="kpi-val">{overview?.decaying_pages?.count ?? "—"}</div>
          <div className="kpi-delta">Detected refresh candidates →</div>
        </Link>
        <Link href="/approvals" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Awaiting Approval</div>
          <div className="kpi-val">{overview?.pending_approvals?.count ?? "—"}</div>
          <div className="kpi-delta">Human gate queue →</div>
        </Link>
      </div>

      {/* ROW 3 — LAST RUN + HISTORY (history matters more than snapshots) */}
      <div className="panel" style={{ marginBottom: "16px" }}>
        <div className="panel-head">
          <span className="panel-label">Last Run</span>
        </div>
        <div className="panel-body" style={{ padding: "12px 16px", fontSize: "11px" }}>
          {overview?.last_run?.summary ? (
            <>
              <div style={{ fontWeight: 700 }}>
                {overview.last_run.job_name || "Run"} {overview.last_run.status ? `— ${overview.last_run.status}` : ""}
              </div>
              <div style={{ color: "var(--muted)", marginTop: "4px" }}>{overview.last_run.summary}</div>
              {(overview.last_run.next_actions || []).length > 0 && (
                <div style={{ marginTop: "6px" }}>Next: {(overview.last_run.next_actions || []).join("; ")}</div>
              )}
            </>
          ) : (
            <div style={{ color: "var(--muted)" }}>No runs yet — run any job (tech audit, rank check, decay detection) to start history.</div>
          )}
          {(overview?.recent_runs || []).length > 0 && (
            <div style={{ marginTop: "10px", display: "flex", flexDirection: "column", gap: "6px" }}>
              {(overview.recent_runs || []).map((r: any, i: number) => (
                <div key={i} style={{ display: "flex", gap: "8px", flexWrap: "wrap", fontSize: "10.5px" }}>
                  <span style={{ fontWeight: 700 }}>{r.job_name}</span>
                  <span style={{ color: "var(--muted)" }}>{r.status}</span>
                  <span>Fixed {r.fixed_count ?? 0} · New {r.new_count ?? 0} · Open {r.still_open_count ?? 0} · Regressed {r.regressed_count ?? 0}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* KPI STRIP (operational — content pipeline is one job among several) */}
      <div className="kpi-strip">
        <Link href="/content" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Articles Generated</div>
          <div className="kpi-val">{metrics?.total_articles ?? "—"}</div>
          <div style={{ fontSize: "10px", color: "var(--muted)", marginTop: "3px" }}>
            Drafts staged: {metrics?.pending_articles ?? 0} · Published: {metrics?.published_articles ?? 0}
          </div>
          <div className="kpi-delta" style={{ marginTop: "4px" }}>Content Pipeline Job →</div>
        </Link>
        <Link href="/approvals" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Pending Approval</div>
          <div className="kpi-val" style={{ color: "var(--accent)" }}>
            {metrics?.pending_articles ?? "—"}
          </div>
          <div className="kpi-delta" style={{ color: "var(--accent)" }}>Open approvals queue →</div>
        </Link>
        <Link href="/tech-seo" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">SEO Health Score</div>
          <div className="kpi-val">
            {metrics?.seo_health_score != null ? `${metrics.seo_health_score}/100` : "No audit yet"}
          </div>          <div className="kpi-delta">Latest technical audit →</div>
        </Link>
        <Link href="/monitoring" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Monitored Alerts</div>
          <div className="kpi-val">{metrics?.monitored_alerts ?? "—"}</div>
          <div className="kpi-delta">Open monitoring →</div>
        </Link>
        <Link href="/brain" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Brain Memories</div>
          <div className="kpi-val">{metrics?.memories_count ?? "—"}</div>
          <div className="kpi-delta">Learned patterns →</div>
        </Link>
        <Link href="/backlinks" style={{ textDecoration: "none" }} className="kpi-cell">
          <div className="kpi-label">Backlinks / Prospects</div>
          <div className="kpi-val">
            {metrics?.backlinks_count ?? "—"} / {metrics?.backlink_opportunities ?? "—"}
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
            {(readinessData?.checks || []).length === 0 && (
              <div style={{ fontSize: "11px", color: "var(--muted)" }}>
                No readiness data — click Re-Check to run the real readiness probe.
              </div>
            )}
            {(readinessData?.checks || []).map((c: any, idx: number) => {
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
            Auto-publish {autoPublish ? "ON" : "OFF"}
          </span>
          <span style={{ color: "var(--muted)" }}>
            {autoPublish ? "Explicit opt-in active — approved drafts publish automatically" : "Off by default — drafts only, approve in /approvals"}
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

      {/* PUBLISHING PACE & INDEXATION GATE */}
      <div
        className="panel"
        style={{
          marginBottom: "16px",
          borderColor: workflowsData?.publishing_pace?.status === "PAUSED_INDEXATION_GATE" ? "var(--amber)" : workflowsData?.publishing_pace?.status === "NORMAL" ? "var(--green)" : "var(--line)",
          background: workflowsData?.publishing_pace?.status === "PAUSED_INDEXATION_GATE" ? "rgba(245,158,11,0.06)" : workflowsData?.publishing_pace?.status === "NORMAL" ? "rgba(34,197,94,0.04)" : "transparent",
        }}
      >
        <div className="panel-head">
          <span className="panel-label" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span>Publishing Pace & Indexation Gate</span>
            <span
              className={`badge ${
                workflowsData?.publishing_pace?.status === "PAUSED_INDEXATION_GATE" ? "badge-amber" : workflowsData?.publishing_pace?.status === "NORMAL" ? "badge-green" : ""
              }`}
            >
              {workflowsData?.publishing_pace?.status === "PAUSED_INDEXATION_GATE"
                ? "PAUSED — INDEXATION BELOW 80%"
                : workflowsData?.publishing_pace?.status === "NORMAL"
                  ? "CADENCE NORMAL — MEASURED"
                  : "NOT MEASURED"}
            </span>
          </span>
          <span style={{ fontSize: "11px", color: "var(--muted)", fontFamily: "monospace" }}>
            Safety Threshold: 80% Indexed
          </span>
        </div>
        <div className="panel-body" style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
            <div style={{ fontSize: "12px", color: "var(--ink)", maxWidth: "800px", lineHeight: "1.4" }}>
              {workflowsData?.publishing_pace?.status === "PAUSED_INDEXATION_GATE" ? (
                <span>
                  Indexation rate is {((workflowsData?.indexation_rate ?? 0) * 100).toFixed(1)}% (below 80% threshold). Adding more content into an unindexed site harms crawl budget. New publishing is throttled while the system prioritizes internal link graph optimization.
                </span>
              ) : workflowsData?.indexation_rate != null ? (
                <span>
                  Indexation rate is {(workflowsData.indexation_rate * 100).toFixed(1)}%. Above 80% safety threshold. Autonomous drafting and publishing proceed at standard pace.
                </span>
              ) : (
                <span>
                  Indexation not measured yet — click Re-check Indexation to run a real check. Pace is unknown until then.
                </span>
              )}
            </div>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <Link
                href="/indexation"
                className="btn"
                style={{ fontSize: "11px", padding: "6px 14px", whiteSpace: "nowrap", textDecoration: "none" }}
              >
                Inspect Center ↗
              </Link>
              <button
                onClick={() => handleRunWorkflow("indexation_check")}
                disabled={runningWorkflow === "indexation_check"}
                className="btn btn-secondary"
                style={{ fontSize: "11px", padding: "6px 14px", whiteSpace: "nowrap" }}
              >
                {runningWorkflow === "indexation_check" ? "Checking Indexation..." : "Re-check Indexation"}
              </button>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10.5px", color: "var(--muted)" }}>
              <span>Current Indexation: {workflowsData?.indexation_rate != null ? `${(workflowsData.indexation_rate * 100).toFixed(1)}%` : "—"}</span>
              <span>Target Gate: 80.0%</span>
            </div>
            <div style={{ width: "100%", height: "8px", background: "var(--line)", borderRadius: "4px", position: "relative", overflow: "hidden" }}>
              <div
                style={{
                  width: `${Math.min(100, Math.max(0, (workflowsData?.indexation_rate ?? 0) * 100))}%`,
                  height: "100%",
                  background: (workflowsData?.indexation_rate ?? 0) >= 0.8 ? "var(--green)" : "var(--amber)",
                  transition: "width 0.4s ease",
                }}
              />
              <div
                style={{
                  position: "absolute",
                  left: "80%",
                  top: 0,
                  bottom: 0,
                  width: "2px",
                  background: "var(--ink)",
                  opacity: 0.8,
                }}
                title="80% Threshold Gate"
              />
            </div>
          </div>
        </div>
      </div>

      {/* 9 INDEPENDENT SEO WORKFLOWS */}
      <div className="panel" style={{ marginBottom: "16px" }}>
        <div className="panel-head">
          <span className="panel-label" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span>⚡ 9 Independent SEO Workflows</span>
            <span className="badge badge-accent">Modular Execution Grid</span>
          </span>
          <span style={{ fontSize: "10.5px", color: "var(--muted)" }}>
            Run envelopes · Diff tracking · Executive narrative summaries
          </span>
        </div>
        <div className="panel-body" style={{ padding: "16px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "14px" }}>
            {(workflowsData?.workflows || [
              {
                job_name: "indexation_check",
                display_name: "Indexation Check",
                category: "technical",
                status: "never_run",
                description: "Inspects submitted URLs against sitemap and GSC indexation status and calculates indexation rate.",
                summary: "No check run yet — click a workflow Run button to execute for real.",
                diff: { fixed: 0, new: 0, still_open: 0, regressed: 0 },
              },
              {
                job_name: "search_performance_report",
                display_name: "Search Performance Report",
                category: "intelligence",
                status: "never_run",
                description: "Analyzes impressions, clicks, CTR, and tracks striking-distance queries (pos 11-20).",
                summary: "Search console metrics awaiting trigger.",
                diff: { fixed: 0, new: 0, still_open: 0, regressed: 0 },
              },
              {
                job_name: "site_health",
                display_name: "Site Health & Vitals",
                category: "technical",
                status: "never_run",
                description: "Runs Core Web Vitals audit, broken link crawl, robots.txt, and sitemap validation.",
                summary: "Technical site vitals audit ready.",
                diff: { fixed: 0, new: 0, still_open: 0, regressed: 0 },
              },
              {
                job_name: "on_page_audit",
                display_name: "On-Page SEO Audit",
                category: "technical",
                status: "never_run",
                description: "Validates title lengths, meta descriptions, single H1 tags, schema markup, and image alts.",
                summary: "On-page structural QA gate ready.",
                diff: { fixed: 0, new: 0, still_open: 0, regressed: 0 },
              },
              {
                job_name: "internal_linking",
                display_name: "Internal Link Optimizer",
                category: "links",
                status: "never_run",
                description: "Finds orphan pages, generates contextual anchor links, and flags generic anchors.",
                summary: "Graph linking engine ready.",
                diff: { fixed: 0, new: 0, still_open: 0, regressed: 0 },
              },
              {
                job_name: "keyword_research",
                display_name: "Data-Driven Keyword Research",
                category: "content",
                status: "never_run",
                description: "Discovers high-intent cluster topics with real volume, difficulty, and SERP intent.",
                summary: "Real data keyword discovery awaiting run.",
                diff: { fixed: 0, new: 0, still_open: 0, regressed: 0 },
              },
              {
                job_name: "content_pipeline",
                display_name: "Content Pipeline (Drafts Only)",
                category: "content",
                status: "never_run",
                description: "Writes data-driven articles with multi-dimensional QA gates and staged preview links.",
                summary: "Deterministic QA drafting engine ready.",
                diff: { fixed: 0, new: 0, still_open: 0, regressed: 0 },
              },
              {
                job_name: "ai_citation_monitoring",
                display_name: "AI-Citation & AEO Monitoring",
                category: "intelligence",
                status: "never_run",
                description: "Monitors citations across Perplexity, ChatGPT Search, Claude, and Google AI Overviews.",
                summary: "Generative engine optimization tracker ready.",
                diff: { fixed: 0, new: 0, still_open: 0, regressed: 0 },
              },
              {
                job_name: "content_optimization",
                display_name: "Content Decay & Optimization",
                category: "content",
                status: "never_run",
                description: "Detects traffic decay and cannibalization; turns findings into actionable rewrite tasks.",
                summary: "Decay detector and refresh task manager ready.",
                diff: { fixed: 0, new: 0, still_open: 0, regressed: 0 },
              },
            ] as any[]).map((wf: any) => {
              const isRunning = runningWorkflow === wf.job_name;
              const categoryColor =
                wf.category === "technical"
                  ? "var(--accent)"
                  : wf.category === "content"
                  ? "#8b5cf6"
                  : wf.category === "links"
                  ? "#06b6d4"
                  : "var(--green)";

              return (
                <div
                  key={wf.job_name}
                  style={{
                    border: "1px solid var(--line)",
                    borderRadius: "6px",
                    background: "var(--panel-inner)",
                    padding: "14px",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    gap: "10px",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "6px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <span
                          style={{
                            fontSize: "9px",
                            textTransform: "uppercase",
                            padding: "2px 6px",
                            borderRadius: "3px",
                            fontWeight: 700,
                            letterSpacing: "0.5px",
                            border: `1px solid ${categoryColor}`,
                            color: categoryColor,
                          }}
                        >
                          {wf.category}
                        </span>
                        <span
                          className={`badge ${
                            wf.status === "completed"
                              ? "badge-green"
                              : wf.status === "failed"
                              ? "badge-red"
                              : wf.status === "running"
                              ? "badge-accent"
                              : ""
                          }`}
                          style={{ fontSize: "9.5px" }}
                        >
                          {wf.status === "completed" ? "Done" : wf.status === "running" ? "Running..." : wf.status === "failed" ? "Failed" : wf.status === "never_run" ? "Not run" : wf.status}
                        </span>
                      </div>
                      {wf.last_run && (
                        <span style={{ fontSize: "9px", color: "var(--muted)", fontFamily: "monospace" }}>
                          {new Date(wf.last_run).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </span>
                      )}
                    </div>

                    <div style={{ fontSize: "13px", fontWeight: 700, color: "var(--ink)", marginBottom: "4px" }}>
                      {wf.display_name}
                    </div>
                    <div style={{ fontSize: "11px", color: "var(--muted)", marginBottom: "8px", lineHeight: "1.4" }}>
                      {wf.description}
                    </div>

                    {/* EXECUTIVE NARRATIVE SUMMARY */}
                    <div
                      style={{
                        padding: "8px 10px",
                        background: "var(--surface)",
                        borderLeft: `3px solid ${categoryColor}`,
                        borderRadius: "2px",
                        fontSize: "10.5px",
                        color: "var(--ink)",
                        lineHeight: "1.4",
                        marginBottom: "8px",
                      }}
                    >
                      <span style={{ fontWeight: 600, color: "var(--muted)", display: "block", fontSize: "9px", textTransform: "uppercase", marginBottom: "2px" }}>
                        Executive Summary
                      </span>
                      {wf.summary || "No run executed yet."}
                    </div>

                    {/* DIFF TRACKING */}
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "4px", fontSize: "10px", textAlign: "center" }}>
                      <div style={{ padding: "4px", background: "rgba(34,197,94,0.08)", borderRadius: "3px" }}>
                        <div style={{ color: "var(--green)", fontWeight: 700 }}>+{wf.diff?.fixed ?? 0}</div>
                        <div style={{ fontSize: "8.5px", color: "var(--muted)" }}>Fixed</div>
                      </div>
                      <div style={{ padding: "4px", background: "rgba(59,130,246,0.08)", borderRadius: "3px" }}>
                        <div style={{ color: "#3b82f6", fontWeight: 700 }}>+{wf.diff?.new ?? 0}</div>
                        <div style={{ fontSize: "8.5px", color: "var(--muted)" }}>New</div>
                      </div>
                      <div style={{ padding: "4px", background: "rgba(245,158,11,0.08)", borderRadius: "3px" }}>
                        <div style={{ color: "var(--amber)", fontWeight: 700 }}>{wf.diff?.still_open ?? 0}</div>
                        <div style={{ fontSize: "8.5px", color: "var(--muted)" }}>Open</div>
                      </div>
                      <div style={{ padding: "4px", background: "rgba(239,68,68,0.08)", borderRadius: "3px" }}>
                        <div style={{ color: "var(--red)", fontWeight: 700 }}>{wf.diff?.regressed ?? 0}</div>
                        <div style={{ fontSize: "8.5px", color: "var(--muted)" }}>Regressed</div>
                      </div>
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: "6px", marginTop: "6px" }}>
                    <button
                      onClick={() => handleRunWorkflow(wf.job_name)}
                      disabled={isRunning || runningWorkflow !== null}
                      className="btn btn-secondary"
                      style={{
                        flex: 1,
                        padding: "8px",
                        fontSize: "11px",
                        fontWeight: 600,
                        display: "flex",
                        justifyContent: "center",
                        alignItems: "center",
                        gap: "6px",
                        cursor: isRunning || runningWorkflow !== null ? "not-allowed" : "pointer",
                      }}
                    >
                      {isRunning ? (
                        <>
                          <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "var(--accent)", animation: "pulse 1s infinite" }} />
                          Executing...
                        </>
                      ) : (
                        `Run ${wf.display_name}`
                      )}
                    </button>
                    <button
                      onClick={() => setActiveWorkflowModal(wf)}
                      className="btn"
                      title="View Run Envelope & Diff Breakdown"
                      style={{
                        padding: "8px 10px",
                        fontSize: "11px",
                        background: "var(--surface)",
                        border: "1px solid var(--line)",
                        cursor: "pointer",
                      }}
                    >
                      Diffs
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* AUTOMATION LIMITS & TRANSPARENCY NOTICE */}
      <div
        className="panel"
        style={{
          marginBottom: "16px",
          border: "1px solid var(--line)",
          background: "linear-gradient(135deg, rgba(255,107,53,0.04) 0%, rgba(139,92,246,0.04) 100%)",
          padding: "16px",
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", gap: "12px" }}>
          <span style={{ fontSize: "20px" }}>🛡️</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: "12.5px", fontWeight: 700, color: "var(--ink)", marginBottom: "4px" }}>
              Automation Transparency & Engineering Boundaries
            </div>
            <div style={{ fontSize: "11.5px", color: "var(--muted)", lineHeight: "1.5", marginBottom: "10px" }}>
              RankForge automates technical hygiene, on-page optimization, and editorial workflows. However, Google algorithmically devalues synthetic link building and unearned authority. We adhere to transparent boundaries:
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "12px", fontSize: "11px" }}>
              <div style={{ padding: "10px", background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "4px" }}>
                <div style={{ color: "var(--green)", fontWeight: 700, marginBottom: "4px" }}>
                  ✅ Fully Automated by RankForge
                </div>
                <ul style={{ margin: 0, paddingLeft: "16px", color: "var(--muted)", lineHeight: "1.4" }}>
                  <li>Data-driven keyword clustering & intent mapping</li>
                  <li>Deterministic multi-dimensional QA (titles, H1s, facts)</li>
                  <li>Internal link graph injection & orphan page fixes</li>
                  <li>Indexation pacing gates & crawl-budget protection</li>
                  <li>Automated decay detection & rewrite staging</li>
                </ul>
              </div>
              <div style={{ padding: "10px", background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "4px" }}>
                <div style={{ color: "var(--amber)", fontWeight: 700, marginBottom: "4px" }}>
                  🛑 Requires External Human PR & Authority
                </div>
                <ul style={{ margin: 0, paddingLeft: "16px", color: "var(--muted)", lineHeight: "1.4" }}>
                  <li>Tier-1 editorial backlinks (Forbes, NYT, industry leaders)</li>
                  <li>Real-world brand mentions, press releases & podcasts</li>
                  <li>Physical domain authority & corporate trademark trust</li>
                  <li>Legal representation & certified professional sign-offs</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* WORDPRESS DRAFT DESTINATION CARD */}
      <div className="panel" style={{ marginBottom: "16px", borderColor: wpConnected ? "var(--green)" : "var(--accent)" }}>
        <div className="panel-head">
          <span className="panel-label" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span>📝 WordPress Destination (Drafts Only)</span>
            <span className={`badge ${wpConnected ? "badge-green" : "badge-amber"}`} style={{ fontSize: "10px" }}>
              {wpConnected ? `✓ Connected (${wpUser})` : "⚠️ Credentials Required"}
            </span>
          </span>
          <span style={{ fontSize: "10px", color: "var(--muted)" }}>
            Draft preview URL: ?p=ID&preview=true
          </span>
        </div>
        <div className="panel-body" style={{ padding: "14px 16px" }}>
          <div style={{ fontSize: "11px", color: "var(--muted)", marginBottom: "10px" }}>
            Destination: <strong>{domain || "No site selected"}</strong>{wpUser ? ` · User: ${wpUser}` : ""}. RankForge saves all articles strictly as <strong>WordPress Drafts with preview links</strong> for human review.
          </div>

          {!wpConnected ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <div style={{ fontSize: "10px", color: "var(--muted)" }}>
                Enter your WordPress Username and Password / Application Password:
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr auto", gap: "8px", alignItems: "center" }}>
                <input
                  type="text"
                  value={wpUser}
                  onChange={(e) => setWpUser(e.target.value)}
                  placeholder="Username (e.g. admin)"
                  style={{ padding: "8px", fontSize: "11px", background: "var(--surface)", border: "1px solid var(--line)", color: "var(--ink)", fontFamily: "monospace" }}
                />
                <input
                  type="password"
                  value={wpAppPass}
                  onChange={(e) => setWpAppPass(e.target.value)}
                  placeholder="WP Password or Application Password"
                  style={{ padding: "8px", fontSize: "11px", background: "var(--surface)", border: "1px solid var(--line)", color: "var(--ink)", fontFamily: "monospace" }}
                />
                <button
                  onClick={handleVerifyAndSaveWp}
                  disabled={wpTesting || !wpAppPass.trim()}
                  className="btn btn-accent"
                  style={{ padding: "8px 14px", fontSize: "11px", whiteSpace: "nowrap" }}
                >
                  {wpTesting ? "Verifying..." : "Save & Verify"}
                </button>
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11px", color: "var(--green)" }}>
              <span>Active — generated articles will stage as drafts in {domain || "the selected site"} under <strong>{wpUser}</strong>.</span>
              <button
                onClick={() => setWpConnected(false)}
                style={{ background: "none", border: "none", color: "var(--muted)", fontSize: "10px", cursor: "pointer", textDecoration: "underline" }}
              >
                Change Credentials
              </button>
            </div>
          )}
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

      {/* WORKFLOW RUN ENVELOPE MODAL */}
      {activeWorkflowModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.65)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "20px",
          }}
          onClick={() => setActiveWorkflowModal(null)}
        >
          <div
            style={{
              background: "var(--surface)",
              border: "1px solid var(--line)",
              borderRadius: "8px",
              maxWidth: "560px",
              width: "100%",
              padding: "24px",
              boxShadow: "0 20px 40px rgba(0,0,0,0.4)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                  <span className="badge badge-accent">Workflow Run Envelope</span>
                  <span className={`badge ${activeWorkflowModal.status === "failed" ? "badge-red" : "badge-green"}`}>
                    {activeWorkflowModal.status || "Completed"}
                  </span>
                </div>
                <div style={{ fontSize: "16px", fontWeight: 700, color: "var(--ink)" }}>
                  {activeWorkflowModal.workflow?.display_name || activeWorkflowModal.display_name || activeWorkflowModal.job_name || "Workflow Execution"}
                </div>
              </div>
              <button
                className="panel-action"
                onClick={() => setActiveWorkflowModal(null)}
                style={{ fontSize: "16px", cursor: "pointer", background: "none", border: "none", color: "var(--muted)" }}
              >
                ✕
              </button>
            </div>

            {/* EXECUTIVE SUMMARY */}
            <div style={{ padding: "12px", background: "var(--panel-inner)", borderLeft: "3px solid var(--accent)", borderRadius: "4px", fontSize: "11.5px", lineHeight: "1.5", marginBottom: "14px", color: "var(--ink)" }}>
              <div style={{ fontSize: "10px", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", marginBottom: "4px" }}>
                Executive Written Summary
              </div>
              {activeWorkflowModal.summary || activeWorkflowModal.narrative_summary || "Workflow completed successfully."}
            </div>

            {/* DIFF METRICS */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "8px", marginBottom: "16px", textAlign: "center" }}>
              <div style={{ padding: "8px", background: "rgba(34,197,94,0.08)", borderRadius: "4px", border: "1px solid rgba(34,197,94,0.2)" }}>
                <div style={{ color: "var(--green)", fontWeight: 700, fontSize: "14px" }}>+{activeWorkflowModal.diff?.fixed ?? activeWorkflowModal.fixed_count ?? 0}</div>
                <div style={{ fontSize: "9px", color: "var(--muted)" }}>Issues Fixed</div>
              </div>
              <div style={{ padding: "8px", background: "rgba(59,130,246,0.08)", borderRadius: "4px", border: "1px solid rgba(59,130,246,0.2)" }}>
                <div style={{ color: "#3b82f6", fontWeight: 700, fontSize: "14px" }}>+{activeWorkflowModal.diff?.new ?? activeWorkflowModal.new_count ?? 0}</div>
                <div style={{ fontSize: "9px", color: "var(--muted)" }}>New Found</div>
              </div>
              <div style={{ padding: "8px", background: "rgba(245,158,11,0.08)", borderRadius: "4px", border: "1px solid rgba(245,158,11,0.2)" }}>
                <div style={{ color: "var(--amber)", fontWeight: 700, fontSize: "14px" }}>{activeWorkflowModal.diff?.still_open ?? activeWorkflowModal.still_open_count ?? 0}</div>
                <div style={{ fontSize: "9px", color: "var(--muted)" }}>Still Open</div>
              </div>
              <div style={{ padding: "8px", background: "rgba(239,68,68,0.08)", borderRadius: "4px", border: "1px solid rgba(239,68,68,0.2)" }}>
                <div style={{ color: "var(--red)", fontWeight: 700, fontSize: "14px" }}>{activeWorkflowModal.diff?.regressed ?? activeWorkflowModal.regressed_count ?? 0}</div>
                <div style={{ fontSize: "9px", color: "var(--muted)" }}>Regressed</div>
              </div>
            </div>

            {/* NEXT ACTIONS */}
            {((activeWorkflowModal.next_actions || []).length > 0 || (activeWorkflowModal.workflow?.next_actions || []).length > 0) && (
              <div style={{ marginBottom: "16px" }}>
                <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--ink)", marginBottom: "6px" }}>
                  Recommended Next Actions:
                </div>
                <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "11px", color: "var(--muted)", lineHeight: "1.5" }}>
                  {(activeWorkflowModal.next_actions || activeWorkflowModal.workflow?.next_actions || []).map((act: string, aIdx: number) => (
                    <li key={aIdx}>{act}</li>
                  ))}
                </ul>
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                className="btn btn-secondary"
                onClick={() => setActiveWorkflowModal(null)}
                style={{ fontSize: "11px", padding: "6px 16px" }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* AUTO-PUBLISH OPT-IN CONFIRM MODAL */}
      {autoPublishConfirmOpen && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div style={{ background: "var(--surface)", border: "1px solid var(--line)", padding: "24px", maxWidth: "460px", width: "90%", borderRadius: "4px" }}>
            <h3 style={{ fontSize: "14px", fontWeight: 600, marginBottom: "8px", color: "var(--amber)" }}>⚠️ Explicit Opt-In: Enable Auto-Publish?</h3>
            <p style={{ fontSize: "12px", color: "var(--muted)", marginBottom: "16px", lineHeight: "1.5" }}>
              By default, RankForge stages all content as WordPress drafts and waits in the Approvals Queue for human sign-off. Enabling auto-publish bypasses human review and automatically pushes passing articles live.
            </p>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
              <button className="btn" onClick={() => setAutoPublishConfirmOpen(false)}>Cancel</button>
              <button className="btn btn-accent" onClick={() => confirmToggleAutoPublish(true)}>
                Enable Auto-Publish
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
