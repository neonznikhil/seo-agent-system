"use client";

import { useEffect, useState, useRef } from "react";
import { get, post, createSSE } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface ContentItem {
  id: string;
  title: string;
  status: string;
  pipeline_status: string;
  ai_search_score: number;
  information_gain_score: number;
  created_at: string;
}

interface PipelineLog {
  step_number: number;
  step_name: string;
  phase: string;
  status: string;
  thought?: string;
  created_at: string;
}

interface ExpertReview {
  expert_name: string;
  score: number;
  issues: any[];
  passed: boolean;
  reviewed_at: string;
}

export default function WriterPage() {
  const [topic, setTopic] = useState("");
  const [contentList, setContentList] = useState<ContentItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [userId, setUserId] = useState<string>("");
  const [activeContentId, setActiveContentId] = useState<string | null>(null);
  const [pipelineLogs, setPipelineLogs] = useState<PipelineLog[]>([]);
  const [expertReviews, setExpertReviews] = useState<ExpertReview[]>([]);
  const [currentPhase, setCurrentPhase] = useState<string | null>(null);
  const [totalSteps, setTotalSteps] = useState(0);
  const [pipelineStatus, setPipelineStatus] = useState<string | null>(null);

  useEffect(() => {
    setUserId(localStorage.getItem("userId") || "");
    loadContent();
  }, []);

  const loadContent = async () => {
    try {
      setLoading(true);
      const websiteId = getCurrentWebsiteId();
      const data = await get(`/writer/${websiteId}/content`);
      setContentList(Array.isArray(data) ? data : data?.data || []);
      setError(null);
    } catch (e) {
      console.error("Failed to load content", e);
      setContentList([]);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic.trim()) return;
    try {
      setGenerating(true);
      setPipelineLogs([]);
      setExpertReviews([]);
      const websiteId = getCurrentWebsiteId();
      const result = await post(`/writer/${websiteId}/generate`, { topic: topic.trim() }, { "X-User-Id": userId });
      const contentId = result.content_id || result.id;
      setActiveContentId(contentId);
      setTopic("");
      loadContent();
      startPipelineSSE(websiteId, contentId);
    } catch (e: any) {
      setError(e.message || "Failed to generate content");
    } finally {
      setGenerating(false);
    }
  };

  const startPipelineSSE = (websiteId: string, contentId: string) => {
    const source = createSSE(`/writer/${websiteId}/pipeline/${contentId}/live`, (event: MessageEvent) => {
      if (event.type === "complete") {
        setPipelineStatus("completed");
        return;
      }
      try {
        const data = JSON.parse(event.data);
        if (data.logs) setPipelineLogs(data.logs);
        if (data.expert_reviews) setExpertReviews(data.expert_reviews);
        if (data.current_phase) setCurrentPhase(data.current_phase);
        if (data.total_steps) setTotalSteps(data.total_steps);
      } catch {
        // ignore parse errors
      }
    });
    return () => {
      if (source) source.close();
    };
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      completed: "bg-green-500 text-paper",
      running: "bg-blue-400 text-ink",
      pending: "bg-stone text-muted",
      failed: "bg-red-500 text-paper",
      needs_human: "bg-yellow-400 text-ink",
      draft: "bg-line text-muted",
      published: "bg-green-500 text-paper",
    };
    return colors[status] || "bg-stone text-muted";
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2 text-[11px] text-muted">
          <span className="w-2 h-2 bg-accent" />
          <span>Writer</span>
        </div>
        <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">Content Writer</h1>
        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">Generate Content</div>
          <div className="h-12 bg-line animate-pulse" />
        </div>
        <div className="bg-stone border border-ink p-4 space-y-3">
          <div className="text-xs text-muted uppercase tracking-wider mono-font">Recent Content</div>
          {[...Array(3)].map((_, i) => (
            <div key={i} className="border border-line p-3">
              <div className="h-4 bg-line animate-pulse mb-2" />
              <div className="h-3 bg-line animate-pulse w-1/2" />
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
          <span>Writer</span>
        </div>
        <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">Content Writer</h1>
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
        <span>Writer</span>
      </div>
      <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">Content Writer</h1>

      <form onSubmit={handleGenerate} className="bg-stone border border-ink p-4">
        <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">Generate New Content</div>
        <div className="flex gap-2">
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Enter topic or keyword..."
            className="field flex-1"
          />
          <button type="submit" disabled={generating || !topic.trim()} className="btn btn-accent">
            {generating ? "Generating..." : "Generate"}
          </button>
        </div>
        <div className="text-[10px] text-muted mono-font mt-2">User ID: {userId}</div>
      </form>

      {activeContentId && pipelineStatus !== "completed" && (
        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">Live Pipeline</div>
          {currentPhase && (
            <div className="text-[10px] mono-font text-accent mb-2">Phase: {currentPhase.replace(/_/g, ' ')}</div>
          )}
          <div className="h-1 bg-line mb-3">
            <div className="h-full bg-accent transition-all" style={{ width: `${totalSteps > 0 ? (totalSteps / 111) * 100 : 0}%` }} />
          </div>
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {pipelineLogs.slice(-20).map((log, i) => (
              <div key={i} className="flex items-center gap-2 text-[10px] mono-font border-b border-line last:border-b-0 py-1">
                <span className="text-muted w-16">[{log.step_number}]</span>
                <span className="flex-1 text-ink">{log.step_name.replace(/_/g, ' ')}</span>
                <span className={`px-1 ${log.status === 'completed' ? 'text-green-500' : log.status === 'running' ? 'text-accent' : 'text-muted'}`}>{log.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {expertReviews.length > 0 && (
        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">Expert Reviews</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {expertReviews.map((review, i) => (
              <div key={i} className="border border-line p-2 text-center">
                <div className="text-[9px] text-muted mono-font uppercase">{review.expert_name.replace(/_/g, ' ')}</div>
                <div className={`text-lg font-bold dot-font ${review.passed ? 'text-green-500' : 'text-red-500'}`}>{review.score}</div>
                <div className="text-[8px] mono-font text-muted">{review.passed ? 'PASS' : 'FAIL'}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-stone border border-ink p-4">
        <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Recent Content</div>
        <div className="space-y-2">
          {contentList.length === 0 ? (
            <div className="text-center py-8 text-muted mono-font text-sm">No content generated yet</div>
          ) : (
            contentList.map((item) => (
              <div key={item.id} className="border border-ink p-3 hover:bg-line transition-colors">
                <div className="flex justify-between items-start">
                  <div>
                    <div className="mono-font text-sm">{item.title}</div>
                    <div className="text-[10px] text-muted mono-font mt-1">
                      Status: {item.status} | Pipeline: {item.pipeline_status}
                    </div>
                    <div className="flex gap-2 mt-1">
                      <span className={`text-[10px] px-2 py-0.5 mono-font ${getStatusColor(item.status)}`}>
                        AI Score: {item.ai_search_score || 0}
                      </span>
                      <span className={`text-[10px] px-2 py-0.5 mono-font ${getStatusColor(item.status)}`}>
                        Info Gain: {item.information_gain_score || 0}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
