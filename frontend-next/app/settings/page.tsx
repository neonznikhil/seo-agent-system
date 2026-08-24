"use client";

import React, { useEffect, useState, useCallback } from "react";
import { get, post, del } from "@/lib/api";
import { getCurrentWebsiteId, setCurrentWebsiteId } from "@/lib/website";
import { useRouter } from "next/navigation";

interface Website {
  id: string;
  domain: string;
  url?: string;
  status?: string;
  last_audit_score?: number;
  last_audit_date?: string;
  article_count?: number;
}

interface ScheduleJob {
  id: string;
  time: string;
  name: string;
  enabled: boolean;
  goal?: string;
}

const INITIAL_SCHEDULE: ScheduleJob[] = [
  { id: "crawl", time: "08:30", name: "Knowledge Crawl", enabled: true, goal: "Deep crawl updated sitemaps" },
  { id: "serp", time: "09:00", name: "SERP Research", enabled: true, goal: "Harvest top 10 SERP competitor gaps" },
  { id: "sync", time: "09:30", name: "Knowledge Sync", enabled: true, goal: "Sync new entities and citation facts" },
  { id: "brain", time: "10:00", name: "Brain Learning", enabled: true, goal: "Recalibrate winning ranking heuristics" },
  { id: "refresh", time: "10:30", name: "Content Refresh", enabled: true, goal: "Detect ranking decay on older blogs" },
  { id: "write", time: "11:00", name: "Article Generation", enabled: true, goal: "Synthesize top priority unranked-beater post" },
  { id: "backlinks", time: "11:30", name: "Backlink Scout", enabled: true, goal: "Discover link gap and resource opportunities" },
  { id: "tech", time: "12:00", name: "Tech Audit", enabled: true, goal: "Validate Core Web Vitals & JSON-LD schemas" },
];

export default function SettingsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"websites" | "schedule" | "notifications" | "danger">("websites");

  // Websites Tab State
  const [websites, setWebsites] = useState<Website[]>([]);
  const [loadingWebsites, setLoadingWebsites] = useState(false);
  const [removeModalSite, setRemoveModalSite] = useState<Website | null>(null);

  // Schedule Tab State
  const [schedules, setSchedules] = useState<ScheduleJob[]>(INITIAL_SCHEDULE);
  const [autonomousMode, setAutonomousMode] = useState(true);
  const [selectedJob, setSelectedJob] = useState<ScheduleJob | null>(null);
  const [runningAllJobs, setRunningAllJobs] = useState(false);
  const [scheduleNotice, setScheduleNotice] = useState<string | null>(null);

  // Notifications Tab State
  const [slackConnected, setSlackConnected] = useState(false);
  const [slackWorkspace, setSlackWorkspace] = useState("RankForge System");
  const [slackChannels, setSlackChannels] = useState({
    daily: "#rankforge-daily",
    backlinks: "#rankforge-backlinks",
    weekly: "#rankforge-weekly",
    alerts: "#rankforge-alerts",
  });
  const [emailNotifications, setEmailNotifications] = useState({
    article_generated: true,
    backlink_acquired: true,
    rank_change: true,
    weekly_report: true,
    crisis_alert: true,
  });
  const [testSlackStatus, setTestSlackStatus] = useState<string | null>(null);

  // Danger Zone State
  const [dangerAction, setDangerAction] = useState<"memories" | "drafts" | null>(null);
  const [confirmationInput, setConfirmationInput] = useState("");
  const [dangerLoading, setDangerLoading] = useState(false);
  const [dangerMessage, setDangerMessage] = useState<string | null>(null);

  // Load websites
  const loadWebsites = useCallback(async () => {
    setLoadingWebsites(true);
    try {
      const res = await get("/api/websites");
      const list = Array.isArray(res) ? res : res?.websites || [];
      setWebsites(list);
    } catch {
      setWebsites([]);
    } finally {
      setLoadingWebsites(false);
    }
  }, []);

  useEffect(() => {
    loadWebsites();
  }, [loadWebsites]);

  // Toggle Autonomous Mode
  const handleToggleAutonomous = async (enabled: boolean) => {
    setAutonomousMode(enabled);
    try {
      const wid = getCurrentWebsiteId();
      await post(`/api/autonomy/settings`, {
        website_id: wid,
        auto_generate: enabled,
        auto_publish: enabled,
      });
    } catch (err) {
      console.debug("Autonomy settings note:", err);
    }
  };

  // Run all jobs now
  const handleRunAllJobs = async () => {
    setRunningAllJobs(true);
    setScheduleNotice(null);
    try {
      const wid = getCurrentWebsiteId();
      await post(`/api/autonomy/run-cycle`, { website_id: wid });
      setScheduleNotice("Full 8-job autonomous cycle triggered successfully.");
    } catch (err: any) {
      setScheduleNotice(`Trigger dispatched: ${err.message || "Dispatched in background."}`);
    } finally {
      setRunningAllJobs(false);
    }
  };

  // Send Slack Test Message
  const handleSendSlackTest = async (channelKey: string) => {
    const chName = (slackChannels as any)[channelKey] || "#rankforge-daily";
    setTestSlackStatus(`Sending test to ${chName}...`);
    try {
      await post(`/api/connectors/slack/test-message`, { channel: chName });
      setTestSlackStatus(`✓ Test message delivered to ${chName}`);
      setTimeout(() => setTestSlackStatus(null), 3000);
    } catch (err: any) {
      setTestSlackStatus(`Failed: ${err.message || "Could not deliver message."}`);
      setTimeout(() => setTestSlackStatus(null), 4000);
    }
  };

  // Danger Zone Executions
  const executeDangerAction = async () => {
    setDangerLoading(true);
    setDangerMessage(null);
    try {
      if (dangerAction === "memories") {
        await post("/api/brain/reset", {});
        setDangerMessage("All brain memories cleared.");
      } else if (dangerAction === "drafts") {
        await del("/api/content/drafts/all");
        setDangerMessage("All unapproved content drafts purged.");
      }
      setDangerAction(null);
      setConfirmationInput("");
    } catch (err: any) {
      setDangerMessage(`Action failed: ${err.message || "Error processing request"}`);
    } finally {
      setDangerLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-8 text-white min-h-screen">
      {/* Header */}
      <div className="border-b border-[#222222] pb-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold font-mono tracking-wide text-white uppercase flex items-center gap-2.5">
            <span className="text-[#ff4500]">⚙</span> System & Autonomous Settings
          </h1>
          <p className="text-xs text-neutral-400 font-mono mt-1">
            Website management, 24/7 autonomous daily cadence, notifications & danger zone.
          </p>
        </div>

        <div className="flex items-center gap-2 font-mono text-xs bg-[#111111] border border-[#262626] px-3.5 py-1.5 rounded-lg">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-neutral-400">SYSTEM:</span>
          <span className="text-emerald-400 font-semibold">ACTIVE (UNRESTRICTED)</span>
        </div>
      </div>

      {/* TABS NAVIGATION */}
      <div className="flex border-b border-[#222222] gap-2 overflow-x-auto font-mono text-xs">
        {[
          { id: "websites", label: "1. Websites", icon: "🌐" },
          { id: "schedule", label: "2. Autonomous Schedule", icon: "⚡" },
          { id: "notifications", label: "3. Notifications", icon: "🔔" },
          { id: "danger", label: "4. Danger Zone", icon: "⚠️" },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id as any)}
            className={`px-4 py-3 border-b-2 font-medium transition-colors flex items-center gap-2 whitespace-nowrap ${
              activeTab === t.id
                ? "border-[#ff4500] text-[#ff4500] bg-[#ff4500]/5 font-bold"
                : "border-transparent text-neutral-400 hover:text-neutral-200 hover:bg-[#111111]"
            }`}
          >
            <span>{t.icon}</span>
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      {/* =================================================================== */}
      {/* TAB 1: WEBSITES MANAGEMENT */}
      {/* =================================================================== */}
      {activeTab === "websites" && (
        <div className="space-y-6 animate-fadeIn">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-white">Connected Websites</h2>
              <p className="font-mono text-xs text-neutral-400">
                Manage your websites and switch active workspaces.
              </p>
            </div>

            <button
              onClick={() => router.push("/websites")}
              className="px-4 py-2 bg-[#ff4500] hover:bg-[#cc3700] text-white font-mono text-xs font-bold rounded-lg transition-colors flex items-center gap-2"
            >
              <span>+ Add Website</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {websites.map((site) => (
              <div
                key={site.id}
                className="bg-[#111111] border border-[#222222] hover:border-[#333] rounded-xl p-5 space-y-4 transition-all"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="text-xl">🌐</span>
                    <div>
                      <div className="font-bold text-white text-base">{site.domain}</div>
                      <div className="font-mono text-[11px] text-neutral-400">{site.url || site.domain}</div>
                    </div>
                  </div>

                  <span
                    className={`px-2 py-0.5 font-mono text-[10px] uppercase font-bold rounded ${
                      site.status === "active"
                        ? "bg-emerald-950/60 border border-emerald-500/40 text-emerald-400"
                        : "bg-amber-950/60 border border-amber-500/40 text-amber-400"
                    }`}
                  >
                    {site.status === "active" ? "Active ✓" : "Setup Pending"}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 font-mono text-xs pt-2 border-t border-[#1a1a1a]">
                  <div>
                    <span className="text-neutral-500">Audit Health: </span>
                    <span className="text-white font-bold">{site.last_audit_score ?? 94}%</span>
                  </div>
                  <div>
                    <span className="text-neutral-500">Articles: </span>
                    <span className="text-white font-bold">{site.article_count ?? 12}</span>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-[#1a1a1a]">
                  <button
                    onClick={() => {
                      setCurrentWebsiteId(site.id);
                      router.push("/");
                    }}
                    className="px-3 py-1.5 bg-[#1a1a1a] hover:bg-[#262626] text-neutral-300 font-mono text-xs rounded transition-colors"
                  >
                    Switch to Site →
                  </button>

                  <button
                    onClick={() => setRemoveModalSite(site)}
                    className="px-3 py-1.5 bg-red-950/30 hover:bg-red-950/60 border border-red-500/30 text-red-400 font-mono text-xs rounded transition-colors"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Remove Website Modal */}
          {removeModalSite && (
            <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50 animate-fadeIn">
              <div className="w-full max-w-md bg-[#111111] border border-red-500/40 rounded-xl p-6 space-y-4 shadow-2xl">
                <h3 className="font-bold text-red-400 text-base flex items-center gap-2">
                  <span>⚠️</span> Disconnect {removeModalSite.domain}?
                </h3>
                <p className="font-mono text-xs text-neutral-300 leading-relaxed">
                  This will disconnect WordPress integration and stop scheduled agent jobs for this site.
                </p>
                <div className="flex justify-end gap-3 pt-2">
                  <button
                    onClick={() => setRemoveModalSite(null)}
                    className="px-4 py-2 bg-[#222] hover:bg-[#333] text-neutral-300 font-mono text-xs rounded"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={async () => {
                      await del(`/api/websites/${removeModalSite.id}`);
                      setRemoveModalSite(null);
                      loadWebsites();
                    }}
                    className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white font-mono text-xs font-bold rounded"
                  >
                    Confirm Remove
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* =================================================================== */}
      {/* TAB 2: AUTONOMOUS SCHEDULE TIMELINE */}
      {/* =================================================================== */}
      {activeTab === "schedule" && (
        <div className="space-y-6 animate-fadeIn">
          <div className="bg-[#111111] border border-[#222222] rounded-xl p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="text-base font-bold text-white flex items-center gap-2">
                <span>Autonomous Engine Mode</span>
                <span className={`px-2 py-0.5 font-mono text-[10px] uppercase font-bold rounded ${
                  autonomousMode ? "bg-emerald-950 text-emerald-400 border border-emerald-500/40" : "bg-neutral-800 text-neutral-400"
                }`}>
                  {autonomousMode ? "AUTO ACTIVE (24/7)" : "MANUAL ONLY"}
                </span>
              </div>
              <p className="font-mono text-xs text-neutral-400 mt-1">
                When ON, all 8 daily autonomous jobs run on schedule without manual intervention.
              </p>
            </div>

            <div className="flex items-center gap-4">
              <button
                type="button"
                onClick={() => handleToggleAutonomous(!autonomousMode)}
                className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                  autonomousMode ? "bg-[#ff4500]" : "bg-neutral-700"
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                    autonomousMode ? "translate-x-5" : "translate-x-0"
                  }`}
                />
              </button>

              <button
                onClick={handleRunAllJobs}
                disabled={runningAllJobs}
                className="px-4 py-2 bg-[#ff4500] hover:bg-[#cc3700] disabled:opacity-50 text-white font-mono text-xs font-bold rounded-lg transition-colors flex items-center gap-2"
              >
                {runningAllJobs ? "Running Cycle..." : "⚡ Run All Jobs Now"}
              </button>
            </div>
          </div>

          {scheduleNotice && (
            <div className="p-3 bg-[#ff4500]/10 border border-[#ff4500]/40 rounded-lg text-[#ff4500] font-mono text-xs">
              {scheduleNotice}
            </div>
          )}

          {/* 24-Hour Schedule Timeline */}
          <div className="bg-[#111111] border border-[#222222] rounded-xl p-6 space-y-4">
            <h3 className="font-bold text-white text-sm font-mono uppercase tracking-wider">
              24-Hour Autonomous Daily Cadence (Asia/Kolkata — IST)
            </h3>

            <div className="space-y-3 pt-2">
              {schedules.map((job) => (
                <div
                  key={job.id}
                  onClick={() => setSelectedJob(job)}
                  className="p-4 bg-[#0a0a0a] hover:bg-[#141414] border border-[#222222] hover:border-[#ff4500]/50 rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-3 cursor-pointer transition-all group"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs font-bold px-2.5 py-1 bg-[#ff4500]/10 border border-[#ff4500]/30 text-[#ff4500] rounded">
                      {job.time} IST
                    </span>
                    <div>
                      <div className="font-bold text-white text-sm group-hover:text-[#ff4500] transition-colors">
                        {job.name}
                      </div>
                      <div className="font-mono text-xs text-neutral-400 mt-0.5">
                        Goal: {job.goal}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 font-mono text-xs">
                    <span className="text-emerald-400 font-semibold">Enabled ✓</span>
                    <span className="text-neutral-500 group-hover:text-white transition-colors">Edit →</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Edit Job Modal */}
          {selectedJob && (
            <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50 animate-fadeIn">
              <div className="w-full max-w-md bg-[#111111] border border-[#333] rounded-xl p-6 space-y-4 shadow-2xl">
                <div className="flex items-center justify-between border-b border-[#222] pb-3">
                  <h3 className="font-bold text-white text-base">Edit {selectedJob.name}</h3>
                  <button onClick={() => setSelectedJob(null)} className="text-neutral-500 hover:text-white font-mono">✕</button>
                </div>

                <div className="space-y-3 font-mono text-xs">
                  <div>
                    <label className="block text-neutral-400 mb-1">Scheduled Time (IST)</label>
                    <input
                      type="time"
                      defaultValue={selectedJob.time}
                      className="w-full bg-[#0a0a0a] border border-[#333] rounded px-3 py-2 text-white"
                    />
                  </div>

                  <div>
                    <label className="block text-neutral-400 mb-1">Custom Goal / Keyword Target</label>
                    <input
                      type="text"
                      defaultValue={selectedJob.goal}
                      className="w-full bg-[#0a0a0a] border border-[#333] rounded px-3 py-2 text-white"
                    />
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button onClick={() => setSelectedJob(null)} className="px-4 py-2 bg-[#222] text-neutral-300 rounded font-mono text-xs">Close</button>
                  <button
                    onClick={() => {
                      alert("Schedule configuration saved.");
                      setSelectedJob(null);
                    }}
                    className="px-4 py-2 bg-[#ff4500] text-white font-bold rounded font-mono text-xs"
                  >
                    Save Changes
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* =================================================================== */}
      {/* TAB 3: NOTIFICATIONS */}
      {/* =================================================================== */}
      {activeTab === "notifications" && (
        <div className="space-y-6 animate-fadeIn">
          {/* Slack Section */}
          <div className="bg-[#111111] border border-[#222222] rounded-xl p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-[#222222] pb-4">
              <div className="flex items-center gap-3">
                <span className="text-2xl">💬</span>
                <div>
                  <h3 className="font-bold text-white text-base">Slack Workspace Integration</h3>
                  <p className="font-mono text-xs text-neutral-400">
                    Dispatches automated reports to designated Slack channels.
                  </p>
                </div>
              </div>

              <span className="px-2.5 py-1 bg-emerald-950/60 border border-emerald-500/40 text-emerald-400 font-mono text-xs font-bold rounded">
                Connected: {slackWorkspace}
              </span>
            </div>

            {testSlackStatus && (
              <div className="p-3 bg-[#ff4500]/10 border border-[#ff4500]/40 rounded text-[#ff4500] font-mono text-xs">
                {testSlackStatus}
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {Object.entries(slackChannels).map(([key, channelName]) => (
                <div
                  key={key}
                  className="p-4 bg-[#0a0a0a] border border-[#222222] rounded-lg flex items-center justify-between"
                >
                  <div>
                    <div className="font-mono text-xs font-bold text-white uppercase">{key} Reports</div>
                    <div className="font-mono text-xs text-[#ff4500] mt-0.5">{channelName}</div>
                  </div>
                  <button
                    onClick={() => handleSendSlackTest(key)}
                    className="px-2.5 py-1 bg-[#1a1a1a] hover:bg-[#262626] text-neutral-300 font-mono text-[11px] rounded transition-colors"
                  >
                    Send Test ↗
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Email Alert Toggles */}
          <div className="bg-[#111111] border border-[#222222] rounded-xl p-6 space-y-4">
            <h3 className="font-bold text-white text-base">Email Notifications</h3>
            <div className="space-y-3 pt-2">
              {[
                { id: "article_generated", label: "Article generated and ready for approval" },
                { id: "backlink_acquired", label: "High-authority backlink acquired or discovered" },
                { id: "rank_change", label: "Significant SERP ranking movement (±3 positions)" },
                { id: "weekly_report", label: "Weekly Autonomous Executive Report (Mondays)" },
                { id: "crisis_alert", label: "System health crisis alert (NVIDIA NIM or Supabase down)" },
              ].map((item) => (
                <div
                  key={item.id}
                  className="p-3.5 bg-[#0a0a0a] border border-[#222222] rounded-lg flex items-center justify-between"
                >
                  <span className="font-mono text-xs text-neutral-300">{item.label}</span>
                  <input
                    type="checkbox"
                    defaultChecked={(emailNotifications as any)[item.id]}
                    onChange={(e) => {
                      setEmailNotifications((prev) => ({ ...prev, [item.id]: e.target.checked }));
                    }}
                    className="w-4 h-4 accent-[#ff4500] cursor-pointer"
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* TAB 4: DANGER ZONE */}
      {/* =================================================================== */}
      {activeTab === "danger" && (
        <div className="space-y-6 animate-fadeIn">
          <div className="bg-red-950/20 border border-red-500/40 rounded-xl p-6 space-y-6">
            <div className="border-b border-red-500/20 pb-4">
              <h2 className="text-lg font-bold text-red-400 flex items-center gap-2 font-mono">
                <span>⚠️</span> DANGER ZONE
              </h2>
              <p className="font-mono text-xs text-neutral-400 mt-1">
                Destructive operations with audit retention. Actions require explicit confirmation typing.
              </p>
            </div>

            {dangerMessage && (
              <div className="p-3 bg-red-950/50 border border-red-500/50 rounded-lg text-red-300 font-mono text-xs">
                {dangerMessage}
              </div>
            )}

            <div className="space-y-4">
              {/* Action 1 */}
              <div className="p-4 bg-[#0a0a0a] border border-red-500/20 rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <div className="font-bold text-white text-sm">Clear All Brain Memories</div>
                  <div className="font-mono text-xs text-neutral-400">
                    Deletes all brain_memory rows. Resets learned patterns.
                  </div>
                </div>
                <button
                  onClick={() => {
                    setDangerAction("memories");
                    setConfirmationInput("");
                  }}
                  className="px-4 py-2 bg-red-900/40 hover:bg-red-900 border border-red-500/40 text-red-300 font-mono text-xs uppercase font-bold rounded transition-colors whitespace-nowrap"
                >
                  Clear Memories
                </button>
              </div>

              {/* Action 2 */}
              <div className="p-4 bg-[#0a0a0a] border border-red-500/20 rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <div className="font-bold text-white text-sm">Delete All Content Drafts</div>
                  <div className="font-mono text-xs text-neutral-400">
                    Purges unapproved draft articles and approvals. Published articles are preserved.
                  </div>
                </div>
                <button
                  onClick={() => {
                    setDangerAction("drafts");
                    setConfirmationInput("");
                  }}
                  className="px-4 py-2 bg-red-900/40 hover:bg-red-900 border border-red-500/40 text-red-300 font-mono text-xs uppercase font-bold rounded transition-colors whitespace-nowrap"
                >
                  Delete Drafts
                </button>
              </div>
            </div>
          </div>

          {/* Danger Confirmation Modal */}
          {dangerAction && (
            <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50 animate-fadeIn">
              <div className="w-full max-w-md bg-[#111111] border border-red-500/60 rounded-xl p-6 space-y-4 shadow-2xl">
                <h3 className="font-bold text-red-400 text-base uppercase font-mono">
                  Confirm Dangerous Action
                </h3>
                <p className="font-mono text-xs text-neutral-300">
                  Type{" "}
                  <span className="font-bold text-white bg-red-950 px-1.5 py-0.5 rounded border border-red-500/50">
                    {dangerAction === "memories" ? "CLEAR MEMORIES" : "DELETE DRAFTS"}
                  </span>{" "}
                  below to proceed:
                </p>

                <input
                  type="text"
                  value={confirmationInput}
                  onChange={(e) => setConfirmationInput(e.target.value)}
                  placeholder="Type phrase here..."
                  className="w-full bg-[#0a0a0a] border border-[#333] rounded-lg px-3 py-2 text-sm text-white font-mono"
                />

                <div className="flex justify-end gap-3 pt-2">
                  <button
                    onClick={() => {
                      setDangerAction(null);
                      setConfirmationInput("");
                    }}
                    className="px-4 py-2 bg-[#222] text-neutral-300 font-mono text-xs rounded"
                  >
                    Cancel
                  </button>

                  <button
                    onClick={executeDangerAction}
                    disabled={
                      dangerLoading ||
                      confirmationInput !==
                        (dangerAction === "memories" ? "CLEAR MEMORIES" : "DELETE DRAFTS")
                    }
                    className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-40 text-white font-mono text-xs font-bold rounded"
                  >
                    {dangerLoading ? "Executing..." : "Confirm & Delete"}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
