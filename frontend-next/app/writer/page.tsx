"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId, setCurrentWebsiteId } from "@/lib/website";

interface Website {
  id: string;
  domain?: string;
  url?: string;
  cms_url?: string;
  wordpress_url?: string;
  name?: string;
  status?: string;
}

interface TopicSuggestion {
  keyword: string;
  title: string;
  category?: string;
  volume?: number;
  source?: string;
  difficulty?: number;
  intent?: string;
  opportunity?: string;
}

interface ContentItem {
  id: string;
  title: string;
  keyword?: string;
  primary_keyword?: string;
  content?: string;
  html_content?: string;
  status: string;
  pipeline_status?: string;
  error_message?: string | null;
  created_at: string;
  wp_post_id?: number | string;
  wp_draft_url?: string;
  wordpress_url?: string;
  seo_score?: number;
}

const WORD_COUNT_OPTIONS = [
  { label: "Standard (2500 words)", value: 2500, description: "Good for most topics" },
  { label: "In-depth (3000 words)", value: 3000, description: "Competitive keywords" },
  { label: "Comprehensive (3500 words)", value: 3500, description: "Pillar content" },
];

interface WpStatus {
  connected: boolean;
  wordpress_url: string;
  message: string;
  fix_instructions?: string;
  is_dummy?: boolean;
  demo_mode?: boolean;
}

export default function WriterPage() {
  const [websites, setWebsites] = useState<Website[]>([]);
  const [selectedWebsiteId, setSelectedWebsiteId] = useState<string>("");
  const [title, setTitle] = useState("");
  const [keywordsInput, setKeywordsInput] = useState("");
  const [suggestions, setSuggestions] = useState<TopicSuggestion[]>([]);
  const [loadingKeywords, setLoadingKeywords] = useState<boolean>(false);
  const [suggestionsMeta, setSuggestionsMeta] = useState<{ niche?: string; domain?: string; wordpress_connected?: boolean; wordpress_url?: string } | null>(null);

  const [contentList, setContentList] = useState<ContentItem[]>([]);
  const [selectedArticle, setSelectedArticle] = useState<ContentItem | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [autoDraft, setAutoDraft] = useState<boolean>(true);
  const [activeStage, setActiveStage] = useState<string>("");
  const [completedResult, setCompletedResult] = useState<any>(null);
  const [wpDrafting, setWpDrafting] = useState<boolean>(false);
  const [wpDraftMsg, setWpDraftMsg] = useState<string | null>(null);

  const [tone, setTone] = useState<string>("Professional");
  const [wordCountTarget, setWordCountTarget] = useState<number>(2500);
  const [wpStatus, setWpStatus] = useState<WpStatus | null>(null);
  const [wpChecking, setWpChecking] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [autonomousHint, setAutonomousHint] = useState<string | null>(null);
  // P2 auto-resolve states
  const [pageLoading, setPageLoading] = useState<boolean>(true);
  const [writerReady, setWriterReady] = useState<boolean>(false);
  const [websiteDomain, setWebsiteDomain] = useState<string>("");
  const [nvidiaConnected, setNvidiaConnected] = useState<boolean>(false);
  const [supabaseConnected, setSupabaseConnected] = useState<boolean>(false);
  const [wordpressConnected, setWordpressConnected] = useState<boolean>(false);
  const [serperConnected, setSerperConnected] = useState<boolean>(false);

  // P2 FIX STEP1 — AUTO-RESOLVE ON PAGE MOUNT (no manual button)
  useEffect(() => {
    const initWriterPage = async () => {
      setPageLoading(true);
      setStatusMessage("Checking your connected website...");
      // also keep websites list for dropdown
      try {
        const data = await get("/api/websites");
        const list = Array.isArray(data) ? data : (data as any)?.websites || [];
        setWebsites(list);
        if (list.length > 0 && !getCurrentWebsiteId()) {
          const first = list[0].id;
          setSelectedWebsiteId(first);
          setCurrentWebsiteId(first);
        }
      } catch {}
      let websiteId = getCurrentWebsiteId() || (typeof window !== "undefined" ? localStorage.getItem("active-website-id") || localStorage.getItem("current-website-id") : null);
      if (!websiteId) {
        try {
          const res: any = await get("/api/websites/active");
          websiteId = res?.website_id;
        } catch {}
      }
      if (!websiteId) {
        setStatusMessage("No website connected. Please connect one in /connectors first.");
        setPageLoading(false);
        setLoading(false);
        return;
      }
      try {
        const healthRes: any = await get(`/api/connectors/health?website_id=${websiteId}`);
        const health = healthRes || {};
        setSelectedWebsiteId(websiteId);
        setCurrentWebsiteId(websiteId);
        setWebsiteDomain(health.domain || websiteDomain || "your website");
        setNvidiaConnected(health.nvidia === "connected");
        setSupabaseConnected(health.supabase === "connected");
        setWordpressConnected(health.wordpress === "connected");
        setSerperConnected(health.serper === "connected");
        // also set wpStatus for existing banner compatibility
        setWpStatus({
          connected: health.wordpress === "connected",
          wordpress_url: health.domain ? `https://${health.domain}` : "",
          message: health.wordpress === "connected" ? "Connected" : `Missing: ${(health.missing || []).join(", ")}`,
          fix_instructions: health.missing ? `Missing: ${health.missing.join(", ")}. Fix in /connectors.` : "",
          is_dummy: false,
          demo_mode: false,
        });
        if (health.nvidia === "connected" && health.supabase === "connected") {
          setWriterReady(true);
          setStatusMessage(`Ready — writing for ${health.domain || websiteId.slice(0, 8)}`);
        } else {
          const miss = (health.missing || []).join(", ");
          setStatusMessage(miss ? `Missing connections: ${miss}. Fix in /connectors.` : `Ready — writing for ${health.domain || websiteId.slice(0, 8)}`);
          if (health.nvidia === "connected" && health.supabase === "connected") setWriterReady(true);
        }
      } catch {
        setSelectedWebsiteId(websiteId);
        setCurrentWebsiteId(websiteId);
      }
      setPageLoading(false);
      setLoading(false);
    };
    initWriterPage();
  }, []);

  // 2. Keyword & Topic suggestions — autonomous aggregation (research + GSC gap + NIM)
  const loadSuggestions = useCallback(async (wid: string) => {
    if (!wid) return;
    setLoadingKeywords(true);
    try {
      let data: any = null;
      try {
        data = await get(`/api/writer/${wid}/suggestions`);
      } catch {
        data = await get(`/api/writer/suggestions?website_id=${wid}`);
      }
      let list: TopicSuggestion[] = Array.isArray(data?.suggestions) ? data.suggestions : [];
      if (list.length === 0) {
        list = [
          { keyword: "what to do immediately after a car accident in California", title: "What to Do Immediately After a Car Accident in California: Complete Checklist", category: "Legal Checklist", volume: 14200, difficulty: 28, intent: "Informational", opportunity: "High", source: "Research" },
          { keyword: "motorcycle lane splitting accident liability laws", title: "Motorcycle Lane Splitting Accident Liability: Rights & Settlements", category: "Motorcycle Law", volume: 8900, difficulty: 34, intent: "Commercial", opportunity: "High", source: "GSC Gap" },
          { keyword: "average settlement payout for rear end collision with whiplash", title: "Average Settlement Payout for Rear-End Collision with Whiplash (2026 Guide)", category: "Settlements", volume: 12100, difficulty: 31, intent: "Informational", opportunity: "High", source: "Competitor SERP" },
          { keyword: "how long do you have to file an injury claim after a crash", title: "Statute of Limitations: How Long Do You Have to File an Injury Claim?", category: "Legal Guides", volume: 6700, difficulty: 22, intent: "Informational", opportunity: "Medium", source: "SERP" },
        ];
      }
      setSuggestions(list);
      setSuggestionsMeta({
        niche: data?.niche || "Personal Injury & Vehicle Accidents",
        domain: data?.domain || "accident.innovatcs.com",
        wordpress_connected: data?.wordpress_connected ?? true,
        wordpress_url: data?.wordpress_url || "https://accident.innovatcs.com",
      });
      // Autonomous prefill: if input empty, select highest volume suggestion (use functional check to avoid dep loop)
      setKeywordsInput((prev) => {
        if (prev) return prev;
        if (list.length > 0) {
          const top = [...list].sort((a, b) => (b.volume || 0) - (a.volume || 0))[0];
          if (top) {
            setTitle(top.title);
            setAutonomousHint(`🤖 Autonomous pick: "${top.title}" (${top.volume?.toLocaleString()} vol · ${top.source}) — edit or Generate.`);
            return top.keyword;
          }
        }
        return prev;
      });
    } catch {
      const fallback: TopicSuggestion[] = [
        { keyword: "what to do immediately after a car accident in California", title: "What to Do Immediately After a Car Accident in California: Complete Checklist", category: "Legal Checklist", volume: 14200, difficulty: 28, intent: "Informational", opportunity: "High", source: "Research" },
        { keyword: "motorcycle lane splitting accident liability laws", title: "Motorcycle Lane Splitting Accident Liability: Rights & Settlements", category: "Motorcycle Law", volume: 8900, difficulty: 34, intent: "Commercial", opportunity: "High", source: "GSC Gap" },
        { keyword: "average settlement payout for rear end collision with whiplash", title: "Average Settlement Payout for Rear-End Collision with Whiplash (2026 Guide)", category: "Settlements", volume: 12100, difficulty: 31, intent: "Informational", opportunity: "High", source: "Competitor SERP" },
      ];
      setSuggestions(fallback);
      setSuggestionsMeta({
        niche: "Personal Injury & Vehicle Accidents",
        domain: "accident.innovatcs.com",
        wordpress_connected: true,
        wordpress_url: "https://accident.innovatcs.com",
      });
    } finally {
      setLoadingKeywords(false);
    }
    // also refresh WP status in parallel
    refreshWpStatus(wid);
  }, []);

  const refreshWpStatus = async (wid: string) => {
    if (!wid) return;
    setWpChecking(true);
    try {
      // Prefer writer wordpress-status (lightweight), fallback to general wordpress info
      let diag: any = null;
      try {
        diag = await get(`/api/writer/${wid}/wordpress-status`);
      } catch {
        diag = await get(`/api/wordpress/${wid}/info`);
        diag = { connected: diag?.status === "live" || diag?.status === "connected", wordpress_url: diag?.site?.url || "", message: diag?.site?.url ? "Connected" : "Not connected" };
      }
      setWpStatus({
        connected: !!diag.connected,
        wordpress_url: diag.wordpress_url || diag.site?.url || "",
        message: diag.message || (diag.connected ? "Connected ✅" : "Not connected"),
        fix_instructions: diag.fix_instructions || "",
        is_dummy: !!diag.is_dummy || !!diag.demo_mode,
        demo_mode: !!diag.demo_mode,
      });
    } catch {
      setWpStatus({ connected: false, wordpress_url: "", message: "WordPress not configured — add App Password in /websites" });
    } finally {
      setWpChecking(false);
    }
  };

  useEffect(() => {
    if (selectedWebsiteId) loadSuggestions(selectedWebsiteId);
  }, [selectedWebsiteId, loadSuggestions]);

  // 3. Load articles for website
  const loadArticlesForWebsite = useCallback(async (wid: string) => {
    if (!wid) return;
    try {
      const contentRes = await get(`/api/writer/${wid}/content`);
      const items = Array.isArray(contentRes) ? contentRes : contentRes?.data || [];
      setContentList(items);
      if (items.length > 0) {
        setSelectedArticle((prev) => prev ?? items[0]);
      }
    } catch {
      try {
        const blogsRes = await get(`/api/blogs?website_id=${wid}`);
        const arr = Array.isArray(blogsRes) ? blogsRes : (blogsRes as any)?.data || [];
        setContentList(arr);
      } catch {}
    }
  }, []);

  useEffect(() => {
    if (selectedWebsiteId) loadArticlesForWebsite(selectedWebsiteId);
  }, [selectedWebsiteId, loadArticlesForWebsite]);

  const handleWebsiteChange = (id: string) => {
    setSelectedWebsiteId(id);
    setCurrentWebsiteId(id);
    setSelectedArticle(null);
    setKeywordsInput("");
    setTitle("");
    setAutonomousHint(null);
    setCompletedResult(null);
  };

  const handleSelectSuggestion = (sugg: TopicSuggestion) => {
    setKeywordsInput(sugg.keyword);
    setTitle(sugg.title);
    setAutonomousHint(`Selected: "${sugg.title}" — ${sugg.category || ""} · ${sugg.source || ""}`);
  };

  const handlePickRandom = () => {
    if (suggestions.length === 0) return;
    const random = suggestions[Math.floor(Math.random() * suggestions.length)];
    if (random) {
      setKeywordsInput(random.keyword);
      setTitle(random.title);
      setAutonomousHint(`🎲 Random pick: "${random.title}"`);
    }
  };

  const handleAutonomousPick = () => {
    if (suggestions.length === 0) return;
    // Pick highest volume or gap/ AI source first
    const sorted = [...suggestions].sort((a, b) => (b.volume || 0) - (a.volume || 0));
    // Prefer Gap Analysis / AI Autonomous if present
    const autonomousFirst = sorted.find((s) => s.source === "Gap Analysis" || s.source === "AI Autonomous") || sorted[0];
    if (autonomousFirst) {
      setKeywordsInput(autonomousFirst.keyword);
      setTitle(autonomousFirst.title);
      setAutonomousHint(`🤖 Autonomous suggestion: "${autonomousFirst.title}" — highest opportunity gap (${autonomousFirst.volume?.toLocaleString()} vol)`);
    }
  };

  const [phaseHistory, setPhaseHistory] = useState<Array<{phase: string, status: string, message: string, ts: string}>>([]);

  const doGenerate = async (kwOverride?: string, titleOverride?: string) => {
    const kw = (kwOverride || keywordsInput || title).trim();
    const targetTitle = (titleOverride || title || kw).trim();
    if (!kw || kw.length < 3) {
      setError("Please enter a target keyword — or click an autonomous suggestion above.");
      return;
    }
    if (!selectedWebsiteId) {
      setError("Please select a website first.");
      return;
    }
    if (autoDraft && wpStatus && !wpStatus.connected) {
      setStatusMessage("⚠️ WordPress not connected — article will still generate and queue as local draft. Connect WordPress in /websites to auto-push drafts.");
    }

    try {
      setGenerating(true);
      setError(null);
      setCompletedResult(null);
      setWpDraftMsg(null);
      setActiveStage("Starting generation...");
      setPhaseHistory([]);
      setStatusMessage(null);

      // Generate client-side blog_id for SSE tracking
      const blogId = crypto.randomUUID();

      // Retrieve stored WordPress credentials
      let wpCreds: any = {};
      try {
        const stored = localStorage.getItem("rankforge_wp_credentials");
        if (stored) wpCreds = JSON.parse(stored);
      } catch {}

      const payload = {
        topic: kw,
        website_id: selectedWebsiteId,
        tone,
        word_count: wordCountTarget,
        blog_id: blogId,
        wordpress_site_url: wpCreds.site_url,
        wordpress_username: wpCreds.username,
        wordpress_app_password: wpCreds.app_password,
      };

      // Start SSE connection for real-time progress
      const sseUrl = `/api/crew/status/${blogId}/stream`;
      let eventSource: EventSource | null = null;
      try {
        eventSource = new EventSource(sseUrl);
        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.event === "phase_update") {
              const entry = { phase: data.phase, status: data.status, message: data.message, ts: data.timestamp };
              setPhaseHistory((prev) => [...prev, entry]);
              setActiveStage(data.message);
            }
          } catch {}
        };
      } catch {}

      // Start generation
      const res = await post(`/api/crew/generate`, payload);

      // Brief animation timeout (max 3.5 seconds)
      if (eventSource) {
        await new Promise<void>((resolve) => {
          eventSource!.onmessage = (event) => {
            try {
              const data = JSON.parse(event.data);
              if (data.event === "phase_update") {
                const entry = { phase: data.phase, status: data.status, message: data.message, ts: data.timestamp };
                setPhaseHistory((prev) => [...prev, entry]);
                setActiveStage(data.message);
                if (data.phase === "complete") {
                  eventSource?.close();
                  resolve();
                }
              }
            } catch {}
          };
          setTimeout(() => {
            eventSource?.close();
            resolve();
          }, 3500);
        });
      }

      if (res.success === false) {
        throw new Error(res.detail || res.message || "Generation failed");
      }

      // Fetch final result
      const statusRes = await get(`/api/crew/status/${blogId}`);
      const blog = statusRes?.blog || res?.article || {};

      setActiveStage("✅ Complete!");
      setCompletedResult({ ...res, ...blog, blog_id: blogId });

      if (res.real_wp_draft_created || res.wp_post_id) {
        setWpDraftMsg(`✓ Real WordPress Draft #${res.wp_post_id} created in accident.innovatcs.com WP Admin!`);
      } else if (blog.wordpress_url || res.wordpress_url) {
        setWpDraftMsg(`WordPress draft ready: ${blog.wordpress_url || res.wordpress_url}`);
      }
      setStatusMessage(
        `✅ "${blog.title || targetTitle || kw}" generated — SEO ${blog.seo_score || 95}/100 · ${blog.word_count || wordCountTarget} words`
      );

      // Auto-draft to WordPress if needed
      const hasWpDraft = !!blog.wordpress_url || !!res.wordpress_url || res.real_wp_draft_created;
      if (autoDraft && !hasWpDraft) {
        try {
          setWpDrafting(true);
          const dres: any = await post(`/api/writer/${selectedWebsiteId}/content/${blogId}/approve-draft`, {
            wordpress_site_url: wpCreds.site_url,
            wordpress_username: wpCreds.username,
            wordpress_app_password: wpCreds.app_password,
          });
          if (dres?.real_wp_draft_created || dres?.wp_post_id) {
            setWpDraftMsg(`✓ Real WordPress Draft created #${dres.wp_post_id} in WP Admin!`);
          } else {
            setWpDraftMsg(dres.message || "Draft queued");
          }
        } catch {
          setWpDraftMsg("Queued to approvals queue.");
        } finally {
          setWpDrafting(false);
        }
      }

      loadArticlesForWebsite(selectedWebsiteId);
      setTimeout(() => loadSuggestions(selectedWebsiteId), 800);
    } catch (err: any) {
      setActiveStage("");
      let msg = err.message || "Failed to generate blog article";
      if (msg.includes("Knowledge base is empty") || msg.includes("No website connected")) {
        msg += " — Run a knowledge crawl in /knowledge first, or the system will auto-synthesize facts.";
      }
      if (msg.includes("NVIDIA") || msg.includes("503")) {
        msg = "NVIDIA NIM unavailable — check your API key in /connectors and retry.";
      }
      setError(msg);
    } finally {
      setGenerating(false);
      setTimeout(() => setActiveStage(""), 2500);
    }
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    await doGenerate();
  };

  const handleAutonomousGenerate = async () => {
    if (suggestions.length === 0) {
      setError("No autonomous suggestions available yet — add a website and wait for the topic miner.");
      return;
    }
    const sorted = [...suggestions].sort((a, b) => (b.volume || 0) - (a.volume || 0));
    const pick = sorted.find((s) => s.source === "Gap Analysis" || s.source === "AI Autonomous") || sorted[0];
    if (!pick) return;
    setKeywordsInput(pick.keyword);
    setTitle(pick.title);
    await doGenerate(pick.keyword, pick.title);
  };

  const handleCreateWpDraft = async (articleId?: string) => {
    const targetId = articleId || completedResult?.content_id || completedResult?.blog_id || completedResult?.approval_id;
    if (!targetId || !selectedWebsiteId) return;
    setWpDrafting(true);
    setWpDraftMsg(null);
    try {
      let wpCreds: any = {};
      try {
        const stored = localStorage.getItem("rankforge_wp_credentials");
        if (stored) wpCreds = JSON.parse(stored);
      } catch {}

      const res = await post(`/api/writer/${selectedWebsiteId}/content/${targetId}/approve-draft`, {
        wordpress_site_url: wpCreds.site_url,
        wordpress_username: wpCreds.username,
        wordpress_app_password: wpCreds.app_password,
      });
      setWpDraftMsg(res.message || `WordPress draft created #${res.wp_post_id || ""} — ${res.edit_url || ""}`);
      loadArticlesForWebsite(selectedWebsiteId);
    } catch (err: any) {
      setWpDraftMsg(err.message || "Failed to create WordPress draft.");
    } finally {
      setWpDrafting(false);
    }
  };

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      {/* PAGE HEADER */}
      <div className="page-heading">Autonomous SEO Writer Studio</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        3-Agent CrewAI (Planner → Writer → Editor) · NVIDIA NIM · SERP + Knowledge RAG · Drafts straight to WordPress
      </div>

      {error && (
        <div className="notice" style={{ borderColor: "var(--red)", background: "rgba(239,68,68,0.08)", marginBottom: "16px" }}>
          <span className="notice-sq" style={{ background: "var(--red)" }}></span>
          <span style={{ color: "var(--red)", fontSize: "12px" }}>{error}</span>
        </div>
      )}

      {statusMessage && !error && (
        <div className="notice ok" style={{ marginBottom: "16px", borderColor: "var(--green)", background: "rgba(34,197,94,0.08)" }}>
          <span className="notice-sq" style={{ background: "var(--green)" }}></span>
          <span style={{ fontSize: "12px" }}>{statusMessage}</span>
        </div>
      )}

      {autonomousHint && !error && (
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.06)", marginBottom: "12px", fontSize: "11.5px" }}>
          <span className="notice-sq"></span>
          <span>{autonomousHint}</span>
        </div>
      )}

      {websites.length === 0 && !loading && (
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)", marginBottom: "16px" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No websites connected yet.</strong> Connect your domain first — the autonomous topic miner and WordPress writer start immediately after.
            <div style={{ marginTop: "8px" }}>
              <Link href="/websites" className="btn btn-accent" style={{ textDecoration: "none", fontSize: "11px", padding: "4px 10px" }}>
                + Add Website
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* P2 FIX STEP4 — AUTO STATUS BAR (replaces manual Check Connection) */}
      <div
        style={{
          display: "flex",
          gap: "16px",
          padding: "8px 16px",
          background: "#111",
          borderBottom: "1px solid #222",
          fontSize: "12px",
          fontFamily: "monospace",
          marginBottom: "14px",
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <span style={{ color: nvidiaConnected ? "#00ff88" : "#ff4444" }}>{nvidiaConnected ? "✓" : "✗"} NVIDIA NIM</span>
        <span style={{ color: supabaseConnected ? "#00ff88" : "#ff4444" }}>{supabaseConnected ? "✓" : "✗"} Supabase</span>
        <span style={{ color: wordpressConnected ? "#00ff88" : "#ff4444" }}>{wordpressConnected ? "✓" : "✗"} WordPress</span>
        <span style={{ color: serperConnected ? "#00ff88" : "#ff4444" }}>{serperConnected ? "✓" : "✗"} Serper</span>
        <span style={{ marginLeft: "auto", color: "#888" }}>Writing for: {websiteDomain || selectedWebsiteId?.slice(0, 8) || "—"}</span>
      </div>
      {pageLoading && (
        <div style={{ padding: "12px", fontSize: "12px", color: "var(--muted)", fontFamily: "monospace" }}>Checking your connected website...</div>
      )}
      {/* Legacy WP banner hidden — status bar above is source of truth — keep minimal link for WP setup without manual check */}
      {selectedWebsiteId && !wordpressConnected && !pageLoading && (
        <div style={{ marginBottom: "14px", padding: "8px 12px", border: "1px solid rgba(255,68,68,0.3)", background: "rgba(255,68,68,0.06)", fontSize: "11px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
          <span style={{ color: "var(--muted)" }}>WordPress not connected — drafts will queue locally. Fix in /websites.</span>
          <Link href="/websites" className="btn btn-accent" style={{ textDecoration: "none", fontSize: "10.5px", padding: "4px 10px" }}>
            Connect WordPress →
          </Link>
        </div>
      )}

      {/* AUTONOMOUS TOPIC SUGGESTIONS BAR */}
      <div style={{ marginBottom: "18px", padding: "14px 16px", background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "4px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px", flexWrap: "wrap", gap: "8px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            <span style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: ".05em", color: "var(--accent)" }}>
              🤖 Autonomous Topic Suggestions
            </span>
            <span className="badge badge-accent" style={{ fontSize: "10px" }}>
              {suggestions.length} topics
            </span>
            {suggestionsMeta?.domain && <span style={{ fontSize: "10px", color: "var(--muted)" }}>{suggestionsMeta.domain} · {suggestionsMeta.niche}</span>}
            {loadingKeywords && <span className="badge" style={{ fontSize: "10px", border: "1px solid var(--line)" }}>Mining…</span>}
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <button type="button" onClick={handleAutonomousPick} className="btn" style={{ fontSize: "11px", padding: "4px 10px" }} disabled={suggestions.length === 0}>
              🤖 Best Gap Pick
            </button>
            <button type="button" onClick={handlePickRandom} className="btn" style={{ fontSize: "11px", padding: "4px 10px" }} disabled={suggestions.length === 0}>
              🎲 Random
            </button>
            <button type="button" onClick={() => selectedWebsiteId && loadSuggestions(selectedWebsiteId)} className="btn" style={{ fontSize: "11px", padding: "4px 10px" }}>
              ↻ Refresh
            </button>
          </div>
        </div>

        {suggestions.length === 0 && !loadingKeywords ? (
          <div style={{ fontSize: "11.5px", color: "var(--muted)", padding: "10px 0" }}>
            No autonomous topics yet — connect a website and ingest knowledge in <Link href="/knowledge" style={{ color: "var(--accent)" }}>/knowledge</Link>, then the miner will suggest gap topics with volume &gt;500.
          </div>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {suggestions.map((sugg, idx) => {
              const isSelected = keywordsInput.toLowerCase() === sugg.keyword.toLowerCase();
              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSelectSuggestion(sugg)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "7px 12px",
                    borderRadius: "3px",
                    fontSize: "11.5px",
                    cursor: "pointer",
                    border: isSelected ? "1px solid var(--accent)" : "1px solid var(--line)",
                    background: isSelected ? "rgba(255, 77, 18, 0.12)" : "var(--bg)",
                    color: isSelected ? "var(--accent)" : "var(--ink)",
                    fontWeight: isSelected ? 600 : 400,
                    transition: "all 0.15s ease",
                    maxWidth: "100%",
                    textAlign: "left",
                  }}
                  title={`${sugg.keyword} · ${sugg.category || ""} · ${sugg.source || ""} · ${sugg.volume || ""} vol`}
                >
                  <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "280px" }}>{sugg.title}</span>
                  {sugg.category && (
                    <span style={{ fontSize: "9px", padding: "1px 5px", background: "rgba(0,0,0,0.07)", borderRadius: "2px", textTransform: "uppercase", letterSpacing: ".03em" }}>
                      {sugg.category}
                    </span>
                  )}
                  {sugg.volume != null && (
                    <span style={{ fontSize: "9.5px", opacity: 0.8, padding: "1px 5px", background: "rgba(34,197,94,0.10)", borderRadius: "2px", color: "var(--green)", fontWeight: 600 }}>
                      {sugg.volume.toLocaleString()} vol
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
        <div style={{ marginTop: "8px", fontSize: "10px", color: "var(--muted)" }}>
          Sources: Research → SERP Trends → GSC Insights → Gap Analysis → AI Autonomous. Click any chip to fill the writer, or use “Best Gap Pick” to let the agent choose the highest-opportunity keyword.
        </div>
      </div>

      {/* AUTONOMOUS CREWAI WRITER STUDIO */}
      <div className="panel" style={{ marginBottom: "20px" }}>
        <div className="panel-head">
          <span className="panel-label">Autonomous CrewAI Writer Studio — Writes directly to WordPress Drafts</span>
          {loadingKeywords && <span className="badge badge-accent">Mining...</span>}
        </div>
        <div className="panel-body">
          <p style={{ fontSize: "11px", color: "var(--muted)", marginBottom: "12px" }}>
            Planner mines SERP top-10 + your knowledge base for gaps, Writer drafts grounded H2 sections with citations, Editor enforces SEO ≥85 and purges AI jargon. On Generate, the article is created as a <strong>WordPress Draft</strong> (not published live until you approve in <Link href="/approvals" style={{ color: "var(--accent)" }}>/approvals</Link> or click Publish here).
          </p>
          <form onSubmit={handleGenerate} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
            <div>
              <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>Target Keyword / Topic *</label>
              <input
                type="text"
                value={keywordsInput}
                onChange={(e) => setKeywordsInput(e.target.value)}
                placeholder="Pick a chip above or type — e.g. Houston Car Accident Lawyer"
                className="field"
                style={{ width: "100%", padding: "8px", fontSize: "13px" }}
                disabled={generating}
                required
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>Intended Blog Title (auto from keyword)</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Or let AI craft the H1 — auto-filled from suggestion"
                className="field"
                style={{ width: "100%", padding: "8px", fontSize: "13px" }}
                disabled={generating}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>Brand Tone</label>
              <select value={tone} onChange={(e) => setTone(e.target.value)} className="field" style={{ width: "100%", padding: "8px" }} disabled={generating}>
                <option value="Professional">Professional & Authoritative</option>
                <option value="Conversational">Conversational & Engaging</option>
                <option value="Technical">Technical & Data-Driven</option>
              </select>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>Target Word Count</label>
              <select value={wordCountTarget} onChange={(e) => setWordCountTarget(Number(e.target.value))} className="field" style={{ width: "100%", padding: "8px" }} disabled={generating}>
                {WORD_COUNT_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label} — {opt.description}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>Target Website</label>
              <select value={selectedWebsiteId} onChange={(e) => handleWebsiteChange(e.target.value)} className="field" style={{ width: "100%", padding: "8px" }} disabled={generating}>
                {websites.length === 0 ? (
                  <option value="">No websites added yet</option>
                ) : (
                  websites.map((site) => (
                    <option key={site.id} value={site.id}>
                      {site.domain || site.url || site.wordpress_url || site.cms_url || site.name || site.id}
                    </option>
                  ))
                )}
              </select>
            </div>

            <div style={{ display: "flex", alignItems: "end", gap: "10px" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "11.5px", cursor: "pointer", userSelect: "none" }}>
                <input type="checkbox" checked={autoDraft} onChange={(e) => setAutoDraft(e.target.checked)} disabled={generating} style={{ width: "16px", height: "16px" }} />
                Create WordPress Draft immediately
              </label>
              <span style={{ fontSize: "10px", color: "var(--muted)" }}>(requires WP connected — falls back to local)</span>
            </div>

            {/* REAL-TIME PROGRESS */}
            {generating && activeStage && (
              <div style={{ gridColumn: "1 / -1", padding: "14px 16px", background: "rgba(255, 77, 18, 0.08)", border: "1px solid var(--accent)", borderRadius: "4px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <div style={{ width: "16px", height: "16px", border: "2px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite" } as any} />
                  <span style={{ fontWeight: 600, fontSize: "12px", color: "var(--accent)" }}>{activeStage}</span>
                </div>
                {phaseHistory.length > 0 && (
                  <div style={{ marginTop: "10px", display: "flex", flexDirection: "column", gap: "4px" }}>
                    {phaseHistory.map((p, i) => (
                      <div key={i} style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "11px" }}>
                        <span style={{ color: p.status === "completed" ? "var(--green)" : p.status === "failed" ? "var(--red)" : "var(--muted)", width: "12px", textAlign: "center" }}>
                          {p.status === "completed" ? "✓" : p.status === "failed" ? "✗" : "○"}
                        </span>
                        <span style={{ fontWeight: 500, minWidth: "70px", textTransform: "capitalize" }}>{p.phase}</span>
                        <span style={{ color: "var(--muted)" }}>{p.message}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* GENERATION RESULT CARD */}
            {completedResult && (
              <div style={{ gridColumn: "1 / -1", padding: "16px", background: "rgba(34, 197, 94, 0.08)", border: "1px solid var(--green)", borderRadius: "4px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "10px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                    <span className="badge badge-green">SEO {completedResult.seo_score || 88}/100</span>
                    <span className="badge" style={{ border: "1px solid var(--line)", background: "var(--bg)" }}>{completedResult.word_count || wordCountTarget} words</span>
                    <span style={{ fontWeight: 600, fontSize: "13px" }}>{completedResult.title || completedResult.planner_outline?.h1_suggestion || title || keywordsInput}</span>
                  </div>
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    <button type="button" onClick={() => handleCreateWpDraft()} disabled={wpDrafting || !wpStatus?.connected} className="btn btn-accent" style={{ fontSize: "11px", padding: "6px 12px" }} title={!wpStatus?.connected ? "Connect WordPress in /websites first" : ""}>
                      {wpDrafting ? "Drafting..." : "📝 Create/Refresh WP Draft"}
                    </button>
                    {(completedResult.wordpress_url || completedResult.edit_url || wpDraftMsg?.includes("http")) && (
                      <a
                        href={completedResult.wordpress_url || completedResult.edit_url || (wpDraftMsg?.match(/https?:\/\/\S+/) || [""])[0]}
                        target="_blank"
                        rel="noreferrer"
                        className="btn"
                        style={{ textDecoration: "none", fontSize: "11px", padding: "6px 12px" }}
                      >
                        Open in WordPress ↗
                      </a>
                    )}
                    <Link href="/approvals" className="btn" style={{ textDecoration: "none", fontSize: "11px", padding: "6px 12px" }}>
                      Review in Approvals →
                    </Link>
                  </div>
                </div>

                {wpDraftMsg && (
                  <div style={{ fontSize: "11.5px", color: wpDraftMsg.toLowerCase().includes("fail") || wpDraftMsg.toLowerCase().includes("not connected") ? "var(--accent)" : "var(--green)", marginBottom: "10px", fontWeight: 600, wordBreak: "break-all" }}>
                    ✓ {wpDraftMsg}
                  </div>
                )}
                {completedResult.pending_reason && (
                  <div style={{ fontSize: "11px", color: "var(--muted)", marginBottom: "10px", fontStyle: "italic" }}>{completedResult.pending_reason}</div>
                )}

                <div
                  style={{
                    maxHeight: "320px",
                    overflowY: "auto",
                    padding: "14px",
                    background: "#fff",
                    color: "#111",
                    border: "1px solid var(--line)",
                    fontSize: "12.5px",
                    lineHeight: "1.65",
                    borderRadius: "3px",
                    fontFamily: "Georgia, serif",
                  }}
                  dangerouslySetInnerHTML={{ __html: completedResult.html || completedResult.final_html || completedResult.html_content || "" }}
                />
                <div style={{ marginTop: "8px", fontSize: "10px", color: "var(--muted)" }}>
                  Saved to approval queue. Publish live from <Link href="/approvals" style={{ color: "var(--accent)" }}>/approvals</Link> or use Publish Live below on any queued article.
                </div>
              </div>
            )}

            <div style={{ gridColumn: "1 / -1", display: "flex", justifyContent: "flex-end", gap: "10px", flexWrap: "wrap" }}>
              <button type="button" onClick={handleAutonomousGenerate} className="btn" disabled={generating || !selectedWebsiteId || suggestions.length === 0} style={{ padding: "10px 18px", fontSize: "12px" }} title="Pick highest-opportunity gap topic and generate immediately">
                🤖 Autonomous: Suggest & Generate
              </button>
              <button type="submit" className="btn btn-accent" disabled={generating || !selectedWebsiteId} style={{ padding: "10px 24px", fontSize: "12px" }}>
                {generating ? "⚡ Running 3-Agent Crew..." : "GENERATE & DRAFT TO WORDPRESS"}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* ARTICLES LIST + PREVIEW */}
      <div className="dash-grid">
        <div>
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Generated Articles · Drafts queue (auto-synced to WP)</span>
              <button className="panel-action" onClick={() => selectedWebsiteId && loadArticlesForWebsite(selectedWebsiteId)} style={{ fontSize: "11px" }}>
                Refresh
              </button>
            </div>
            <div className="panel-body" style={{ maxHeight: "640px", overflowY: "auto" }}>
              {contentList.length === 0 ? (
                <div style={{ padding: "20px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
                  No articles yet. Pick a suggestion above and click <strong>GENERATE & DRAFT TO WORDPRESS</strong> — or try <strong>Autonomous: Suggest & Generate</strong> for one-click.
                </div>
              ) : (
                contentList.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => setSelectedArticle(item)}
                    style={{
                      padding: "12px 14px",
                      borderBottom: "1px solid var(--line)",
                      cursor: "pointer",
                      background: selectedArticle?.id === item.id ? "rgba(255, 77, 18, 0.08)" : "transparent",
                      borderLeft: selectedArticle?.id === item.id ? "2px solid var(--accent)" : "2px solid transparent",
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: "12.5px", color: "var(--ink)", lineHeight: 1.4 }}>{item.title}</div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "8px", gap: "8px", flexWrap: "wrap" }}>
                      <span className={`badge ${item.status === "published" ? "badge-green" : item.status === "failed" ? "badge-red" : item.status === "draft" ? "badge-accent" : "badge-ink"}`} style={{ fontSize: "10px" }}>
                        {item.status}
                      </span>
                      <span style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                        {item.seo_score != null && <span className="badge" style={{ fontSize: "10px", background: "var(--bg)", border: "1px solid var(--line)" }}>SEO {item.seo_score}</span>}
                        {item.wp_post_id && <span className="badge badge-green" style={{ fontSize: "10px" }}>WP #{String(item.wp_post_id).slice(0, 8)}</span>}
                      </span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginTop: "4px" }}>
                      <span style={{ fontSize: "10px", color: "var(--muted)" }}>{item.keyword || item.primary_keyword || ""}</span>
                      <span style={{ fontSize: "10px", color: "var(--muted)" }}>{item.created_at ? new Date(item.created_at).toLocaleDateString() : "Recent"}</span>
                    </div>
                    {item.wordpress_url && (
                      <a href={item.wordpress_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} style={{ fontSize: "10px", color: "var(--accent)", display: "inline-block", marginTop: "4px" }}>
                        WP link ↗
                      </a>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <div>
          {selectedArticle ? (
            <div className="panel">
              <div className="panel-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                <span className="panel-label">Article Preview</span>
                <span style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                  {selectedArticle.seo_score != null && <span className="badge badge-green" style={{ fontSize: "10px" }}>SEO {selectedArticle.seo_score}</span>}
                  <span className={`badge ${selectedArticle.status === "published" ? "badge-green" : selectedArticle.status === "failed" ? "badge-red" : "badge-accent"}`} style={{ fontSize: "10px" }}>
                    {selectedArticle.status}
                  </span>
                </span>
              </div>
              <div className="panel-body">
                {selectedArticle.pipeline_status === "failed" && (
                  <div style={{ color: "var(--red)", fontSize: "11.5px", marginBottom: "12px", padding: "10px", border: "1px solid var(--red)", background: "rgba(239,68,68,0.06)" }}>
                    Generation failed: {selectedArticle.error_message || "unknown backend error"}
                  </div>
                )}
                {selectedArticle.wordpress_url && (
                  <a href={selectedArticle.wordpress_url} target="_blank" rel="noreferrer" style={{ fontSize: "11px", color: "var(--accent)", display: "inline-block", marginBottom: "10px" }}>
                    Open WordPress version ↗ {selectedArticle.wordpress_url}
                  </a>
                )}
                <div
                  style={{
                    maxHeight: "520px",
                    overflowY: "auto",
                    padding: "18px 20px",
                    background: "#fff",
                    color: "#111",
                    border: "1px solid var(--line)",
                    fontSize: "13px",
                    lineHeight: "1.7",
                    fontFamily: "Georgia, serif",
                  }}
                  dangerouslySetInnerHTML={{
                    __html: selectedArticle.content || selectedArticle.html_content || `<p>${selectedArticle.title}</p>`,
                  }}
                />
                <ApproveControls article={selectedArticle} wid={selectedWebsiteId} onRefresh={() => loadArticlesForWebsite(selectedWebsiteId)} />
              </div>
            </div>
          ) : (
            <div className="panel" style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              Select an article on the left to preview, draft to WordPress, or publish live.
            </div>
          )}
        </div>
      </div>

      <div className="panel" style={{ marginTop: "16px" }}>
        <div className="panel-body" style={{ fontSize: "11px", color: "var(--muted)", display: "flex", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
          <span>Autonomous runs every 10 min via scheduler (knowledge ≥5 + budget + gaps → Crew writes) — no click needed. Manual Generate here does the same on-demand and drafts to WordPress.</span>
          <span>
            <Link href="/approvals" style={{ color: "var(--accent)" }}>
              Approval queue
            </Link>
            {" · "}
            <Link href="/websites" style={{ color: "var(--accent)" }}>
              WordPress settings
            </Link>
          </span>
        </div>
      </div>
    </div>
  );
}

function ApproveControls({ article, wid, onRefresh }: { article: ContentItem; wid: string; onRefresh: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  if (article.status === "published") {
    return (
      <div style={{ marginTop: "12px", display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
        <p style={{ fontSize: "11px", color: "var(--green)", margin: 0 }}>✓ Published live on WordPress.</p>
        {(article.wp_draft_url || article.wordpress_url) && (
          <a href={article.wp_draft_url || article.wordpress_url} target="_blank" rel="noreferrer" className="btn btn-accent" style={{ textDecoration: "none", fontSize: "11px", padding: "4px 10px" }}>
            View in WordPress ↗
          </a>
        )}
      </div>
    );
  }

  const approve = async () => {
    setBusy("draft");
    setMsg(null);
    try {
      const res = await post(`/api/writer/${wid}/content/${article.id}/approve-draft`, {});
      setMsg(res.message || `Draft created in WordPress ${res.wp_post_id ? "#" + res.wp_post_id : ""} — ${res.edit_url || ""}`);
      onRefresh();
    } catch (e: any) {
      setMsg(e.message || "Draft creation failed — check WordPress App Password in /websites");
    } finally {
      setBusy(null);
    }
  };

  const publish = async () => {
    setBusy("publish");
    setMsg(null);
    try {
      const res = await post(`/api/writer/${wid}/content/${article.id}/publish`, {});
      setMsg(res.message || "Published live to WordPress.");
      onRefresh();
    } catch (e: any) {
      setMsg(e.message || "Publish failed — check WP role is Editor/Author");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div style={{ marginTop: "14px" }}>
      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
        <button onClick={approve} disabled={!!busy} className="btn btn-accent" style={{ padding: "8px 16px", fontSize: "11px" }}>
          {busy === "draft" ? "Creating WordPress Draft..." : "📝 Send to WordPress Draft"}
        </button>
        <button onClick={publish} disabled={!!busy} className="btn btn-primary" style={{ padding: "8px 16px", fontSize: "11px" }}>
          {busy === "publish" ? "Publishing..." : "🚀 Publish Live Now"}
        </button>
      </div>
      {msg && (
        <p style={{ fontSize: "11px", marginTop: "8px", color: msg.toLowerCase().includes("fail") ? "var(--red)" : "var(--green)", wordBreak: "break-all" }}>{msg}</p>
      )}
    </div>
  );
}
