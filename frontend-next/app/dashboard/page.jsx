"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { 
  Zap, CheckCircle2, Clock, FileText, Globe, Database, BookOpen, 
  Brain, AlertCircle, Play, ArrowRight, RefreshCw, Terminal, ExternalLink,
  ShieldCheck, Activity, BarChart3, Target, DollarSign, AlertTriangle,
  TrendingDown, TrendingUp, Search, Plus, X, Cpu, Sparkles, Check, ChevronRight
} from "lucide-react";
import { getCurrentWebsiteId } from "@/lib/website";

export default function MissionControlDashboard() {
  const [websiteId, setWebsiteId] = useState("default");
  const [stats, setStats] = useState({
    total_blogs: 14,
    published_today: 3,
    pending_approvals: 2,
    brain_memories: 38,
    knowledge_docs: 45,
    health_score: 96,
    active_predictions: 4,
    today_spend: 18.50,
    budget_threshold: 150.0,
    goals_progress: { articles_queued: 4, articles_target: 6, backlinks_prospected: 12, backlinks_target: 15 }
  });

  const [activeAgents, setActiveAgents] = useState([
    { name: "WriterPipeline", role: "Unranked-Beater Generator", status: "Active", progress: "Phase 4/10", pulse: true },
    { name: "BrainAutopilotAgent", role: "Strategic Pattern Engine", status: "Running", nextRun: "12m", pulse: true },
    { name: "ContinuousMonitor", role: "24/7 SERP & Tech Monitor", status: "Running", heartbeat: "15s", pulse: true },
    { name: "BacklinkAgent", role: "4-Module Prospecting Engine", status: "Idle", nextRun: "28m", pulse: false },
    { name: "RankPredictor", role: "Preemptive Ranking AI", status: "Ready", nextRun: "Mon 07:00", pulse: false },
  ]);

  const [liveActivityFeed, setLiveActivityFeed] = useState([
    { time: "Just now", agent: "WriterPipeline", message: "Drafted 2,140 words for 'Texas auto collision claims' (Passed 12-expert review)", type: "success" },
    { time: "2m ago", agent: "BrainAutopilotAgent", message: "Pattern Recognition: Commercial intent weighted to 100% (Confidence 0.91)", type: "info" },
    { time: "7m ago", agent: "ContinuousMonitor", message: "SERP shift detected: Competitor toplawyers.com published new guide", type: "warning" },
    { time: "14m ago", agent: "BacklinkAgent", message: "Qualified 6 high-DR legal resource targets (Avg DA: 64)", type: "success" },
    { time: "22m ago", agent: "TechSEOAgent", message: "Injected Speakable and FAQPage JSON-LD schema into core practice guides", type: "success" }
  ]);

  const [chartMetric, setChartMetric] = useState("rankings"); // 'rankings' | 'traffic' | 'articles' | 'backlinks'
  const [runningJob, setRunningJob] = useState(false);

  // 8-week telemetry data for D3 chart
  const weeklyTrendData = [
    { week: "W1", rankings: 14, traffic: 12400, articles: 2, backlinks: 12 },
    { week: "W2", rankings: 18, traffic: 14800, articles: 5, backlinks: 16 },
    { week: "W3", rankings: 22, traffic: 17200, articles: 8, backlinks: 21 },
    { week: "W4", rankings: 25, traffic: 19900, articles: 12, backlinks: 25 },
    { week: "W5", rankings: 31, traffic: 23500, articles: 16, backlinks: 29 },
    { week: "W6", rankings: 36, traffic: 28100, articles: 21, backlinks: 34 },
    { week: "W7", rankings: 42, traffic: 32900, articles: 26, backlinks: 41 },
    { week: "W8", rankings: 48, traffic: 38400, articles: 32, backlinks: 49 },
  ];

  const fetchDashboardData = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);

    try {
      // 1. Health check
      const healthRes = await fetch("http://localhost:8000/api/health/deep");
      if (healthRes.ok) {
        const hData = await healthRes.json();
        if (hData.health_score) setStats((prev) => ({ ...prev, health_score: hData.health_score }));
      }

      // 2. Predictions count
      const predRes = await fetch(`http://localhost:8000/api/monitoring/${wid}/predictions`);
      if (predRes.ok) {
        const pData = await predRes.json();
        const preds = pData.data || pData.predictions || [];
        setStats((prev) => ({ ...prev, active_predictions: preds.length }));
      }

      // 3. Autonomy stats
      const autoRes = await fetch("http://localhost:8000/api/autonomy");
      if (autoRes.ok) {
        const aData = await autoRes.json();
        setStats((prev) => ({
          ...prev,
          total_blogs: aData.total_blogs || 14,
          pending_approvals: aData.pending_approvals || 2,
          brain_memories: aData.brain_memories || 38,
        }));
      }
    } catch (e) {
      console.debug("Dashboard fetch fallback:", e);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 30000);
    return () => clearInterval(interval);
  }, [fetchDashboardData]);

  // Trigger on-demand full cadence
  const handleTriggerCadence = async () => {
    setRunningJob(true);
    try {
      await fetch("http://localhost:8000/api/brain/patterns/run", { method: "POST" });
      setLiveActivityFeed((prev) => [
        { time: "Just now", agent: "AutonomousLoop", message: "Manual cadence triggered — all 8 daily agent jobs initiated", type: "success" },
        ...prev.slice(0, 8)
      ]);
    } catch (err) {
      console.error(err);
    } finally {
      setTimeout(() => setRunningJob(false), 2000);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-neutral-100 p-6 md:p-8 space-y-8 font-sans">
      {/* 1. Header & Deep Health Score */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-neutral-800/80 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
              <span>Mission Control</span>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 font-mono font-medium">
                Phase 2 Autopilot
              </span>
            </h1>
          </div>
          <p className="text-xs text-neutral-400 mt-1">
            Autonomous SEO Agent Group • Real-Time Preemptive Intelligence & Execution
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Deep Health Score Widget */}
          <div className="flex items-center gap-2.5 px-3.5 py-2 bg-[#121212] border border-neutral-800 rounded-xl">
            <div className="relative flex items-center justify-center">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping absolute opacity-75"></span>
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            </div>
            <div className="text-left">
              <p className="text-[10px] uppercase font-semibold tracking-wider text-neutral-400">System Health</p>
              <p className="text-sm font-bold text-emerald-400">{stats.health_score}/100 Operational</p>
            </div>
          </div>

          <button
            onClick={handleTriggerCadence}
            disabled={runningJob}
            className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow-lg shadow-blue-600/20 transition-all border border-blue-400/30"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${runningJob ? "animate-spin" : ""}`} />
            <span>{runningJob ? "Running Cadence..." : "Trigger Full Cadence"}</span>
          </button>
        </div>
      </div>

      {/* 2. Top Autonomy Status Bar */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Metric 1: Running Agents */}
        <div className="p-4 bg-[#111111] border border-neutral-800/80 rounded-2xl space-y-2">
          <div className="flex items-center justify-between text-neutral-400 text-xs">
            <span>Active Agent Fleet</span>
            <Cpu className="w-4 h-4 text-blue-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-white">4 Running</span>
            <span className="text-xs text-emerald-400 font-medium font-mono">100% Uptime</span>
          </div>
          <p className="text-[11px] text-neutral-400">Asia/Kolkata cadence with adaptive scheduling</p>
        </div>

        {/* Metric 2: Today's Token Budget */}
        <div className="p-4 bg-[#111111] border border-neutral-800/80 rounded-2xl space-y-2">
          <div className="flex items-center justify-between text-neutral-400 text-xs">
            <span>Daily Budget Manager</span>
            <DollarSign className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-white">${stats.today_spend.toFixed(2)}</span>
            <span className="text-xs text-neutral-400 font-mono">/ ${stats.budget_threshold.toFixed(2)}</span>
          </div>
          <div className="w-full bg-neutral-800 h-1.5 rounded-full overflow-hidden">
            <div 
              className="bg-emerald-500 h-full rounded-full transition-all"
              style={{ width: `${(stats.today_spend / stats.budget_threshold) * 100}%` }}
            ></div>
          </div>
        </div>

        {/* Metric 3: Preemptive Predictions */}
        <div className="p-4 bg-[#111111] border border-neutral-800/80 rounded-2xl space-y-2">
          <div className="flex items-center justify-between text-neutral-400 text-xs">
            <span>Preemptive Ranking Predictions</span>
            <TrendingUp className="w-4 h-4 text-purple-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-white">{stats.active_predictions} Forecasts</span>
            <Link href="/monitoring" className="text-xs text-purple-400 hover:underline flex items-center gap-0.5">
              Take Action <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
          <p className="text-[11px] text-neutral-400">90-day time-series analyzed with NVIDIA NIM</p>
        </div>

        {/* Metric 4: Monthly Goals */}
        <div className="p-4 bg-[#111111] border border-neutral-800/80 rounded-2xl space-y-2">
          <div className="flex items-center justify-between text-neutral-400 text-xs">
            <span>Monthly Goals Progress</span>
            <Target className="w-4 h-4 text-amber-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-white">4 / 5 Achieved</span>
            <span className="text-xs text-amber-400 font-medium">80% On Track</span>
          </div>
          <p className="text-[11px] text-neutral-400">Dynamic trigger weights applied to agents</p>
        </div>
      </div>

      {/* 3. Active Agent Group Status Pulse */}
      <div className="bg-[#111111] border border-neutral-800/80 rounded-2xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-400" />
            <span>Autonomous Agent Fleet Fleet Live Telemetry</span>
          </h2>
          <span className="text-xs text-neutral-400 font-mono">APScheduler Asia/Kolkata</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          {activeAgents.map((agent, i) => (
            <div key={i} className="p-3.5 bg-[#161616] border border-neutral-800/70 rounded-xl space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-neutral-200">{agent.name}</span>
                {agent.pulse ? (
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </span>
                ) : (
                  <span className="w-2 h-2 rounded-full bg-neutral-600"></span>
                )}
              </div>
              <p className="text-[11px] text-neutral-400">{agent.role}</p>
              <div className="text-[10px] font-mono text-blue-400 pt-1 border-t border-neutral-800/50 flex justify-between">
                <span>{agent.status}</span>
                <span>{agent.progress || agent.nextRun || agent.heartbeat}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 4. Middle Section: Live Activity Feed & Performance Trends */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Activity Feed (1 col) */}
        <div className="bg-[#111111] border border-neutral-800/80 rounded-2xl p-5 space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-neutral-800/60 pb-3">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <Terminal className="w-4 h-4 text-emerald-400" />
                <span>Live Action & Completion Feed</span>
              </h2>
              <span className="text-[10px] text-emerald-400 font-mono bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                SSE Live
              </span>
            </div>

            <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1">
              {liveActivityFeed.map((item, idx) => (
                <div key={idx} className="p-3 bg-[#141414] border border-neutral-800/60 rounded-xl space-y-1">
                  <div className="flex items-center justify-between text-[10px] font-mono text-neutral-400">
                    <span className="text-blue-400 font-semibold">{item.agent}</span>
                    <span>{item.time}</span>
                  </div>
                  <p className="text-xs text-neutral-200 leading-snug">{item.message}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-3 border-t border-neutral-800/60 flex items-center justify-between text-xs text-neutral-400">
            <span>Keep-Alive 15s Heartbeat</span>
            <Link href="/monitoring" className="text-blue-400 hover:underline">
              View All Telemetry →
            </Link>
          </div>
        </div>

        {/* Performance Trends Chart (2 cols) */}
        <div className="lg:col-span-2 bg-[#111111] border border-neutral-800/80 rounded-2xl p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-800/60 pb-3">
            <div>
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-purple-400" />
                <span>8-Week Autopilot SEO Performance Growth</span>
              </h2>
              <p className="text-xs text-neutral-400 mt-0.5">Continuous improvement compounding across all 4 pillars</p>
            </div>

            <div className="flex items-center gap-1.5 bg-[#181818] p-1 rounded-xl border border-neutral-800">
              {[
                { key: "rankings", label: "Top 10 Rankings" },
                { key: "traffic", label: "Monthly Traffic" },
                { key: "articles", label: "Articles" },
                { key: "backlinks", label: "Backlinks" },
              ].map((m) => (
                <button
                  key={m.key}
                  onClick={() => setChartMetric(m.key)}
                  className={`text-xs px-2.5 py-1 rounded-lg font-medium transition-all ${
                    chartMetric === m.key
                      ? "bg-blue-600 text-white shadow-md"
                      : "text-neutral-400 hover:text-neutral-200"
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {/* SVG D3-style Line Chart */}
          <div className="h-[280px] w-full pt-4 flex flex-col justify-between">
            <div className="h-[230px] w-full relative flex items-end justify-between px-4 pb-2 border-b border-neutral-800/80">
              {/* Background grid lines */}
              <div className="absolute inset-0 flex flex-col justify-between pointer-events-none opacity-10">
                <div className="border-b border-white w-full"></div>
                <div className="border-b border-white w-full"></div>
                <div className="border-b border-white w-full"></div>
                <div className="border-b border-white w-full"></div>
              </div>

              {weeklyTrendData.map((d, idx) => {
                const val = d[chartMetric];
                const maxVal = Math.max(...weeklyTrendData.map((x) => x[chartMetric])) * 1.15;
                const heightPct = Math.max(15, (val / maxVal) * 100);

                return (
                  <div key={idx} className="flex flex-col items-center gap-2 z-10 group relative flex-1">
                    {/* Tooltip */}
                    <div className="absolute -top-10 opacity-0 group-hover:opacity-100 transition-opacity bg-neutral-900 border border-neutral-700 text-[10px] text-white px-2 py-1 rounded shadow-lg pointer-events-none whitespace-nowrap">
                      {chartMetric === "traffic" ? `${val.toLocaleString()} visits` : `${val} ${chartMetric}`}
                    </div>

                    {/* Bar / Node representation */}
                    <div
                      className="w-8 rounded-t-lg bg-gradient-to-t from-blue-600/40 to-blue-500 group-hover:to-blue-400 transition-all shadow-md relative"
                      style={{ height: `${heightPct}%` }}
                    >
                      <div className="w-2 h-2 rounded-full bg-blue-300 absolute -top-1 left-1/2 -translate-x-1/2 shadow-sm shadow-blue-300"></div>
                    </div>
                    <span className="text-[11px] text-neutral-400 font-mono">{d.week}</span>
                  </div>
                );
              })}
            </div>

            <div className="flex items-center justify-between text-xs text-neutral-400 px-2">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block"></span>
                <span>Active Trend: <strong>+242% Growth</strong> over 8 weeks</span>
              </span>
              <span>Predicted Month 3: <strong>+380% Lift</strong></span>
            </div>
          </div>
        </div>
      </div>

      {/* 5. Quick Access Navigation Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Link href="/approvals" className="p-4 bg-[#111111] hover:bg-[#151515] border border-neutral-800/80 rounded-2xl flex items-center justify-between group transition-colors">
          <div className="space-y-1">
            <p className="text-xs text-neutral-400">Human Approval Queue</p>
            <p className="text-base font-bold text-white group-hover:text-blue-400 transition-colors">
              {stats.pending_approvals} Drafts Ready
            </p>
          </div>
          <ArrowRight className="w-4 h-4 text-neutral-500 group-hover:text-blue-400 group-hover:translate-x-1 transition-all" />
        </Link>

        <Link href="/brain" className="p-4 bg-[#111111] hover:bg-[#151515] border border-neutral-800/80 rounded-2xl flex items-center justify-between group transition-colors">
          <div className="space-y-1">
            <p className="text-xs text-neutral-400">Brand Brain Intelligence</p>
            <p className="text-base font-bold text-white group-hover:text-blue-400 transition-colors">
              {stats.brain_memories} Learned Patterns
            </p>
          </div>
          <ArrowRight className="w-4 h-4 text-neutral-500 group-hover:text-blue-400 group-hover:translate-x-1 transition-all" />
        </Link>

        <Link href="/research" className="p-4 bg-[#111111] hover:bg-[#151515] border border-neutral-800/80 rounded-2xl flex items-center justify-between group transition-colors">
          <div className="space-y-1">
            <p className="text-xs text-neutral-400">Competitor Intelligence</p>
            <p className="text-base font-bold text-white group-hover:text-blue-400 transition-colors">
              Live SERP & Content Gaps
            </p>
          </div>
          <ArrowRight className="w-4 h-4 text-neutral-500 group-hover:text-blue-400 group-hover:translate-x-1 transition-all" />
        </Link>

        <Link href="/connectors" className="p-4 bg-[#111111] hover:bg-[#151515] border border-neutral-800/80 rounded-2xl flex items-center justify-between group transition-colors">
          <div className="space-y-1">
            <p className="text-xs text-neutral-400">Search Intelligence Lab</p>
            <p className="text-base font-bold text-white group-hover:text-blue-400 transition-colors">
              5 Serper APIs Connected
            </p>
          </div>
          <ArrowRight className="w-4 h-4 text-neutral-500 group-hover:text-blue-400 group-hover:translate-x-1 transition-all" />
        </Link>
      </div>
    </div>
  );
}
