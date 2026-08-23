"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { 
  Zap, CheckCircle2, Clock, FileText, Globe, Database, BookOpen, 
  Brain, AlertCircle, Play, ArrowRight, RefreshCw, Terminal, ExternalLink,
  ShieldCheck, Activity, BarChart3
} from "lucide-react";

export default function DashboardPage() {
  const [stats, setStats] = useState({
    total_blogs: 0,
    published_today: 0,
    pending_approvals: 0,
    brain_memories: 0,
    knowledge_docs: 0,
    wordpress_connected: false,
    nvidia_connected: false,
    supabase_connected: false,
  });

  const [autonomousOn, setAutonomousOn] = useState(true);
  const [schedulerStatus, setSchedulerStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  // Load stats and scheduler data
  const fetchData = useCallback(async () => {
    try {
      // 1. Fetch overview stats
      const autoRes = await fetch("http://localhost:8000/api/autonomy");
      if (autoRes.ok) {
        const data = await autoRes.json();
        setStats((prev) => ({
          ...prev,
          total_blogs: data.total_blogs || 0,
          published_today: data.published_today || 0,
          pending_approvals: data.pending_approvals || 0,
          brain_memories: data.brain_memories || 0,
          knowledge_docs: data.knowledge_docs || 0,
        }));
        if (data.scheduler) setSchedulerStatus(data.scheduler);
      }

      // 2. Fetch connectors status
      const connRes = await fetch("http://localhost:8000/api/connectors/status");
      if (connRes.ok) {
        const cData = await connRes.json();
        setStats((prev) => ({
          ...prev,
          wordpress_connected: cData.wordpress?.connected || false,
          nvidia_connected: cData.nvidia?.connected || false,
          supabase_connected: cData.supabase?.connected || false,
        }));
        if (cData.autonomous) {
          setAutonomousOn(cData.autonomous.auto_publish ?? true);
        }
      }

      // 3. Fetch live scheduler logs
      const logRes = await fetch("http://localhost:8000/api/scheduler/logs?limit=10");
      if (logRes.ok) {
        const logData = await logRes.json();
        setLogs(Array.isArray(logData) ? logData : []);
      }
    } catch (e) {
      console.warn("Dashboard poll warning:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    // 5-second live polling interval
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // Trigger manual job run
  const handleTriggerJob = async (jobName) => {
    try {
      await fetch(`http://localhost:8000/api/scheduler/run-now/${jobName}`, { method: "POST" });
      fetchData();
    } catch (e) {
      console.warn("Trigger job failed:", e);
    }
  };

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-200 p-6 md:p-8">
      {/* Top Autonomous Status Banner */}
      <div className="max-w-7xl mx-auto mb-8">
        <div
          className={`p-4 rounded-xl border flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-lg transition ${
            autonomousOn
              ? "bg-emerald-950/40 border-emerald-500/30 text-emerald-300"
              : "bg-amber-950/40 border-amber-500/30 text-amber-300"
          }`}
        >
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${autonomousOn ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400"}`}>
              <Zap className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm tracking-wide uppercase">
                  {autonomousOn ? "🤖 Fully Autonomous Engine ACTIVE" : "⚙️ Manual Mode — Human Approval Required"}
                </span>
                <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              </div>
              <p className="text-xs opacity-80 mt-0.5">
                {autonomousOn
                  ? "Next scheduled article publish: Tomorrow at 11:00 AM IST · 7 daily cron jobs operating seamlessly"
                  : "Automatic publishing paused. Articles are staged in /approvals queue awaiting human sign-off."}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/connectors"
              className="py-1.5 px-3 bg-gray-900/80 hover:bg-gray-800 border border-gray-700 text-xs font-medium rounded-lg text-white transition"
            >
              Toggle Mode in Connectors
            </Link>
          </div>
        </div>
      </div>

      {/* 4 Stats Cards Grid */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {/* Total Blogs */}
        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Total SEO Articles</span>
            <FileText className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">{stats.total_blogs}</div>
          <p className="text-[11px] text-gray-500 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" /> Published Today: {stats.published_today}
          </p>
        </div>

        {/* WordPress Connected */}
        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">WordPress CMS</span>
            <Globe className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">
            {stats.wordpress_connected ? "Connected" : "Disconnected"}
          </div>
          <p className="text-[11px] text-gray-500">
            {stats.wordpress_connected ? "accident.innovatcs.com (REST API)" : "Configure in /connectors"}
          </p>
        </div>

        {/* Brain Memories */}
        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Brain Memory Rules</span>
            <Brain className="w-4 h-4 text-pink-400" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">{stats.brain_memories}</div>
          <p className="text-[11px] text-gray-500">Learned content & engagement rules</p>
        </div>

        {/* Knowledge Base */}
        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Grounded Knowledge</span>
            <BookOpen className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">{stats.knowledge_docs}</div>
          <p className="text-[11px] text-gray-500">pgvector verified business chunks</p>
        </div>
      </div>

      {/* Main Grid: Scheduler Jobs + Secondary Actions */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Left Column: 7 Scheduled Autonomous Jobs */}
        <div className="lg:col-span-2 bg-gray-900/80 border border-gray-800 rounded-xl p-6 shadow-xl">
          <div className="flex items-center justify-between border-b border-gray-800 pb-4 mb-4">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-blue-400" />
              <h3 className="font-semibold text-sm text-white">Autonomous Cron Cadence (Asia/Kolkata)</h3>
            </div>
            <span className="text-xs text-gray-500 font-mono">7 Autonomous Jobs</span>
          </div>

          <div className="space-y-3">
            {[
              { id: "daily_search", time: "09:00 AM", name: "Daily Search & Trends", agent: "ResearchAgent", desc: "SERP trends & competitor keywords via Tavily" },
              { id: "knowledge_sync", time: "09:30 AM", name: "Knowledge Sync & Statutes", agent: "KnowledgeAgent", desc: "Re-scrape stale competitor docs & Texas laws" },
              { id: "brain_learn", time: "10:00 AM", name: "Brain Auto-Learn", agent: "BrainAutopilotAgent", desc: "Synthesize analytics data into winning rules" },
              { id: "content_refresh", time: "10:30 AM", name: "Autonomous Content Refresh", agent: "SupervisorAgent", desc: "Refresh 2 decaying articles with 2026 facts" },
              { id: "auto_new_page", time: "11:00 AM", name: "Autonomous Article Writer", agent: "WriterPipeline", desc: "Generate & direct publish high-volume SEO pages" },
              { id: "backlink_prospecting", time: "11:30 AM", name: "Backlink Prospecting Loop", agent: "BacklinkAgent", desc: "4-module qualification & outreach drafts" },
              { id: "seo_report_aeo_tracking", time: "12:00 PM", name: "AEO Citation Tracking", agent: "AEOAgent", desc: "LLM buyer intent query tracking & schema injection" },
            ].map((job) => (
              <div
                key={job.id}
                className="bg-gray-950/70 border border-gray-800/80 hover:border-gray-700 rounded-lg p-3 flex items-center justify-between gap-3 transition"
              >
                <div className="flex items-center gap-3">
                  <div className="text-center font-mono py-1 px-2 bg-gray-900 border border-gray-800 rounded text-[11px] text-blue-400 min-w-[70px]">
                    {job.time}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-gray-200">{job.name}</span>
                      <span className="text-[10px] bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded font-mono">
                        {job.agent}
                      </span>
                    </div>
                    <p className="text-[11px] text-gray-500 mt-0.5">{job.desc}</p>
                  </div>
                </div>

                <button
                  onClick={() => handleTriggerJob(job.id)}
                  className="py-1 px-2.5 bg-gray-800 hover:bg-blue-600 text-gray-300 hover:text-white rounded text-[11px] font-medium transition flex items-center gap-1 border border-gray-700 hover:border-blue-500"
                  title="Run this job immediately"
                >
                  <Play className="w-3 h-3" /> Run Now
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: Quick Navigation & Secondary Actions */}
        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-6 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 border-b border-gray-800 pb-4 mb-4">
              <Activity className="w-4 h-4 text-emerald-400" />
              <h3 className="font-semibold text-sm text-white">System Controls</h3>
            </div>

            <div className="space-y-3">
              <Link
                href="/workforce"
                className="p-3 bg-gray-950 border border-gray-800 hover:border-blue-500/50 rounded-lg flex items-center justify-between transition group"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-500/10 text-blue-400 rounded-lg">
                    <Zap className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold text-white group-hover:text-blue-400 transition">Workforce Graph Canvas</h4>
                    <p className="text-[11px] text-gray-500">View and chat with 25+ specialized AI agents</p>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-gray-600 group-hover:text-blue-400 transition" />
              </Link>

              <Link
                href="/knowledge"
                className="p-3 bg-gray-950 border border-gray-800 hover:border-emerald-500/50 rounded-lg flex items-center justify-between transition group"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-emerald-500/10 text-emerald-400 rounded-lg">
                    <BookOpen className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold text-white group-hover:text-emerald-400 transition">Edit Knowledge Base</h4>
                    <p className="text-[11px] text-gray-500">Upload business facts & competitor intelligence</p>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-gray-600 group-hover:text-emerald-400 transition" />
              </Link>

              <Link
                href="/connectors"
                className="p-3 bg-gray-950 border border-gray-800 hover:border-purple-500/50 rounded-lg flex items-center justify-between transition group"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-purple-500/10 text-purple-400 rounded-lg">
                    <ShieldCheck className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold text-white group-hover:text-purple-400 transition">Test Connections</h4>
                    <p className="text-[11px] text-gray-500">Verify NVIDIA, Supabase, and WordPress proxy</p>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-gray-600 group-hover:text-purple-400 transition" />
              </Link>

              <Link
                href="/approvals"
                className="p-3 bg-gray-950 border border-gray-800 hover:border-amber-500/50 rounded-lg flex items-center justify-between transition group"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-amber-500/10 text-amber-400 rounded-lg">
                    <CheckCircle2 className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold text-white group-hover:text-amber-400 transition">View Approvals Queue</h4>
                    <p className="text-[11px] text-gray-500">Review staged drafts if manual mode is enabled</p>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-gray-600 group-hover:text-amber-400 transition" />
              </Link>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-gray-800">
            <Link
              href="/generate"
              className="w-full py-2.5 px-4 bg-gray-800 hover:bg-gray-700 text-white rounded-lg text-xs font-medium transition flex items-center justify-center gap-2 border border-gray-700"
            >
              Manual Generate (Optional)
            </Link>
          </div>
        </div>
      </div>

      {/* Live Scheduler Log Tail */}
      <div className="max-w-7xl mx-auto bg-gray-900/80 border border-gray-800 rounded-xl p-6 shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-800 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-emerald-400" />
            <h3 className="font-semibold text-sm text-white">Live Autonomous Scheduler Logs</h3>
          </div>
          <span className="text-[11px] text-gray-500 font-mono flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" /> Polling live every 5s
          </span>
        </div>

        <div className="bg-gray-950 p-4 rounded-lg border border-gray-800 font-mono text-xs max-h-48 overflow-y-auto space-y-1.5">
          {logs.length === 0 ? (
            <div className="text-gray-600">No recent scheduler execution logs available.</div>
          ) : (
            logs.map((l, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className="text-gray-500 text-[10px]">
                  {l.timestamp ? new Date(l.timestamp).toLocaleTimeString() : "--:--:--"}
                </span>
                <span className={`font-semibold text-[11px] ${l.status === "completed" ? "text-emerald-400" : l.status === "error" ? "text-red-400" : "text-blue-400"}`}>
                  [{l.job}]
                </span>
                <span className="text-gray-300">{l.message}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
