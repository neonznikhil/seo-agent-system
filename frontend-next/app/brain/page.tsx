"use client";

import { useEffect, useState, useCallback } from "react";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

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

interface BrainPerformance {
  id: string;
  content_id: string;
  keyword: string;
  position_history: string;
  what_worked: string;
  what_failed: string;
  learned_at: string;
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

export default function BrainPage() {
  const websiteId = getCurrentWebsiteId();
  const [tab, setTab] = useState<"memories" | "performance" | "queue" | "jobs" | "context">("memories");
  const [memories, setMemories] = useState<Memory[]>([]);
  const [performance, setPerformance] = useState<BrainPerformance[]>([]);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [jobs, setJobs] = useState<DailyJob[]>([]);
  const [brainContext, setBrainContext] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [memoryType, setMemoryType] = useState("");

  const fetchMemories = useCallback(async () => {
    const params = new URLSearchParams();
    if (query) params.set("query", query);
    if (memoryType) params.set("memory_type", memoryType);
    const qs = params.toString();
    const data = await get(`/brain/${websiteId}/memories${qs ? `?${qs}` : ""}`);
    setMemories(Array.isArray(data) ? data : []);
  }, [websiteId, query, memoryType]);

  const fetchPerformance = useCallback(async () => {
    const data = await get(`/brain/${websiteId}/performance/all`);
    setPerformance(Array.isArray(data) ? data : []);
  }, [websiteId]);

  const fetchQueue = useCallback(async () => {
    const data = await get(`/brain/${websiteId}/auto-queue`);
    setQueue(Array.isArray(data) ? data : []);
  }, [websiteId]);

  const fetchJobs = useCallback(async () => {
    const data = await get(`/brain/${websiteId}/daily-jobs?days=7`);
    setJobs(Array.isArray(data) ? data : []);
  }, [websiteId]);

  const fetchBrainContext = useCallback(async () => {
    const data = await get(`/brain/${websiteId}/brand-brain`);
    setBrainContext(typeof data === "string" ? data : JSON.stringify(data, null, 2));
  }, [websiteId]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      if (tab === "memories") await fetchMemories();
      if (tab === "performance") await fetchPerformance();
      if (tab === "queue") await fetchQueue();
      if (tab === "jobs") await fetchJobs();
      if (tab === "context") await fetchBrainContext();
    } finally {
      setLoading(false);
    }
  }, [tab, fetchMemories, fetchPerformance, fetchQueue, fetchJobs, fetchBrainContext]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const approveQueue = async (queueId: string) => {
    await post(`/brain/${websiteId}/auto-queue/${queueId}/approve`, {});
    fetchQueue();
  };

  const rejectQueue = async (queueId: string) => {
    await post(`/brain/${websiteId}/auto-queue/${queueId}/reject`, {});
    fetchQueue();
  };

  const runJobNow = async (jobType: string) => {
    await post(`/brain/${websiteId}/run-now`, { job_type: jobType });
    fetchJobs();
  };

  const statusBadge = (status: string) => {
    const color =
      status === "completed" || status === "draft_ready" || status === "published"
        ? "text-green-600 border-green-600"
        : status === "failed" || status === "rejected"
        ? "text-red-600 border-red-600"
        : "text-amber-600 border-amber-600";
    return (
      <span className={`px-2 py-0.5 border text-[10px] mono-font uppercase ${color}`}>
        {status}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold dot-font tracking-tight">BRAIN</h1>
          <p className="text-[11px] text-muted uppercase tracking-widest mono-font mt-1">
            Memory · Learning · Daily Autopilot
          </p>
        </div>
        <button
          type="button"
          onClick={refresh}
          className="px-3 py-1 text-[9px] mono-font uppercase tracking-widest border border-ink hover:bg-paper"
        >
          Refresh
        </button>
      </div>

      <div className="flex gap-2 border-b border-line pb-2">
        {(["memories", "performance", "queue", "jobs", "context"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-3 py-1 text-[10px] mono-font uppercase tracking-widest border ${
              tab === t ? "border-ink bg-paper" : "border-transparent text-muted hover:text-ink"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {loading && (
        <div className="text-[11px] text-muted mono-font py-4">Loading brain data...</div>
      )}

      {!loading && tab === "memories" && (
        <div className="space-y-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search memories..."
              className="flex-1 border border-ink p-2 text-xs mono-font bg-transparent"
            />
            <select
              value={memoryType}
              onChange={(e) => setMemoryType(e.target.value)}
              className="border border-ink p-2 text-xs mono-font bg-transparent"
            >
              <option value="">All types</option>
              <option value="fact">Fact</option>
              <option value="experience">Experience</option>
              <option value="failure">Failure</option>
              <option value="preference">Preference</option>
              <option value="outcome">Outcome</option>
            </select>
            <button
              type="button"
              onClick={fetchMemories}
              className="px-3 py-1 text-[10px] mono-font uppercase tracking-widest border border-ink hover:bg-paper"
            >
              Search
            </button>
          </div>
          <div className="space-y-2">
            {memories.length === 0 && (
              <div className="text-[11px] text-muted mono-font py-4">No memories yet.</div>
            )}
            {memories.map((m) => (
              <div key={m.id} className="border border-ink p-3 bg-stone">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] mono-font uppercase tracking-widest text-accent">
                      {m.memory_type}
                    </span>
                    <span className="text-[10px] mono-font text-muted">
                      confidence {m.confidence}
                    </span>
                  </div>
                  <span className="text-[10px] mono-font text-muted">
                    used {m.times_used} · success {m.times_successful}
                  </span>
                </div>
                <div className="mono-font text-sm mb-1">{m.title}</div>
                <div className="text-[11px] text-muted mono-font line-clamp-2">
                  {m.content}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!loading && tab === "performance" && (
        <div className="space-y-2">
          {performance.length === 0 && (
            <div className="text-[11px] text-muted mono-font py-4">No performance data yet.</div>
          )}
          {performance.map((p) => (
            <div key={p.id} className="border border-ink p-3 bg-stone">
              <div className="mono-font text-sm mb-1">{p.keyword || p.content_id}</div>
              <div className="text-[10px] mono-font text-muted mb-2">
                Learned: {new Date(p.learned_at).toLocaleString()}
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px] mono-font">
                <div>
                  <span className="text-muted">Worked: </span>
                  {p.what_worked || "{}"}
                </div>
                <div>
                  <span className="text-muted">Failed: </span>
                  {p.what_failed || "{}"}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && tab === "queue" && (
        <div className="space-y-2">
          {queue.length === 0 && (
            <div className="text-[11px] text-muted mono-font py-4">No pages in queue.</div>
          )}
          {queue.map((item) => (
            <div key={item.id} className="border border-ink p-3 bg-stone">
              <div className="flex items-center justify-between mb-2">
                <div className="mono-font text-sm">{item.suggested_topic}</div>
                {statusBadge(item.status)}
              </div>
              <div className="text-[11px] mono-font text-muted mb-1">
                Keyword: {item.primary_keyword} · Priority: {item.priority_score} · Source: {item.source}
              </div>
              <div className="text-[11px] mono-font text-muted mb-2">{item.reason}</div>
              <div className="flex gap-2">
                {item.status === "suggested" && (
                  <>
                    <button
                      type="button"
                      onClick={() => approveQueue(item.id)}
                      className="px-2 py-1 text-[9px] mono-font uppercase tracking-widest border border-ink hover:bg-paper"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => rejectQueue(item.id)}
                      className="px-2 py-1 text-[9px] mono-font uppercase tracking-widest border border-ink hover:bg-paper"
                    >
                      Reject
                    </button>
                  </>
                )}
                {item.status === "approved_auto" && (
                  <span className="text-[10px] mono-font text-green-600">Auto approved</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && tab === "jobs" && (
        <div className="space-y-2">
          <div className="flex gap-2 flex-wrap">
            {["daily_search", "daily_cluster_build", "daily_geo_check", "daily_refresh_check", "daily_backlink_check", "daily_new_page_suggestion"].map(
              (jt) => (
                <button
                  key={jt}
                  type="button"
                  onClick={() => runJobNow(jt)}
                  className="px-2 py-1 text-[9px] mono-font uppercase tracking-widest border border-ink hover:bg-paper"
                >
                  Run {jt.replace("daily_", "")}
                </button>
              )
            )}
          </div>
          {jobs.length === 0 && (
            <div className="text-[11px] text-muted mono-font py-4">No jobs yet.</div>
          )}
          {jobs.map((job) => (
            <div key={job.id} className="border border-ink p-3 bg-stone">
              <div className="flex items-center justify-between mb-2">
                <div className="mono-font text-sm">{job.job_type}</div>
                {statusBadge(job.status)}
              </div>
              <div className="text-[10px] mono-font text-muted mb-1">
                Ran: {new Date(job.run_at).toLocaleString()}
              </div>
              {job.error && (
                <div className="text-[10px] mono-font text-red-600 mb-1">Error: {job.error}</div>
              )}
              <div className="text-[11px] mono-font text-muted">{job.result}</div>
            </div>
          ))}
        </div>
      )}

      {!loading && tab === "context" && (
        <div className="border border-ink p-4 bg-stone">
          <div className="text-[11px] mono-font text-muted mb-2">Brand Brain Context</div>
          <pre className="mono-font text-xs whitespace-pre-wrap">{brainContext}</pre>
        </div>
      )}
    </div>
  );
}
