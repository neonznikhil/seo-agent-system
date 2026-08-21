"use client";

import { useEffect, useState } from "react";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface PipelineLog {
  phase: string;
  step_number: number;
  step_name: string;
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

interface Content {
  id: string;
  title: string;
  status: string;
  pipeline_status: string;
  ai_search_score: number;
  information_gain_score: number;
  created_at: string;
}

interface ContentDetail extends Content {
  content?: string;
  expert_reviews?: ExpertReview[];
  logs?: PipelineLog[];
}

export default function ContentPage() {
  const [contentList, setContentList] = useState<Content[]>([]);
  const [selectedContent, setSelectedContent] = useState<ContentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [userId, setUserId] = useState<string>("dashboard_user");

  useEffect(() => {
    setUserId(localStorage.getItem("userId") || "nikhil");
    loadContent();
  }, []);

  const loadContent = async () => {
    setLoading(true);
    try {
      const websiteId = getCurrentWebsiteId();
      const data = await get(`/writer/${websiteId}/content`);
      setContentList(data || []);
    } catch (e) {
      console.error("Failed to load content", e);
    }
    setLoading(false);
  };

  const viewContent = async (id: string) => {
    try {
      const websiteId = getCurrentWebsiteId();
      const detail = await get(`/writer/${websiteId}/content/${id}`);
      setSelectedContent(detail);
    } catch (e) {
      console.error("Failed to view content", e);
    }
  };

  const publishContent = async (contentId: string) => {
    try {
      const websiteId = getCurrentWebsiteId();
      const result = await post(
        `/writer/${websiteId}/content/${contentId}/publish`,
        {},
        { "X-User-Id": userId }
      );
      alert("Published successfully!");
      loadContent();
    } catch (e: any) {
      if (e.message.includes("403")) {
        alert("Human approval required - X-User-Id missing");
      } else {
        alert("Publish failed: " + e.message);
      }
    }
  };

  const getPhaseColor = (status: string) => {
    const colors: Record<string, string> = {
      completed: "bg-green-100 text-green-800",
      running: "bg-blue-100 text-blue-800",
      pending: "bg-gray-100 text-gray-800",
      failed: "bg-red-100 text-red-800",
      needs_human: "bg-orange-100 text-orange-800"
    };
    return colors[status] || "bg-stone";
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">CONTENT PIPELINE</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[...Array(6)].map((_, i) => (
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
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">CONTENT PIPELINE</h1>
        <div className="text-xs mono-font">
          User ID: {userId}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-2">
          <div className="bg-stone border border-ink p-4">
            <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">CONTENT STATUS</div>
            <div className="space-y-2">
              {contentList.map(content => (
                <div key={content.id} className="border border-ink p-3 hover:bg-line transition-colors">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-mono text-sm">{content.title}</div>
                      <div className="text-xs text-muted mono-font">
                        Status: {content.status} | Pipeline: {content.pipeline_status}
                      </div>
                      <div className="flex gap-2 mt-1">
                        <span className="text-xs px-2 py-1 bg-green-100 text-green-800 rounded">
                          AI Score: {content.ai_search_score || 0}
                        </span>
                        <span className="text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded">
                          Info Gain: {content.information_gain_score || 0}
                        </span>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => viewContent(content.id)}
                        className="text-xs px-2 py-1 bg-accent text-stone border border-ink"
                      >
                        View
                      </button>
                      {content.status === "pending_approval" && (
                        <button
                          onClick={() => publishContent(content.id)}
                          className="text-xs px-2 py-1 bg-red-500 text-stone border border-ink"
                        >
                          Publish
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              {contentList.length === 0 && (
                <div className="text-center py-8 text-muted mono-font">
                  No content found. Generate new content via pipeline.
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          {selectedContent && (
            <>
              <div className="bg-stone border border-ink p-4">
                <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">
                  PIPELINE PROGRESS
                </div>
                 <div className="space-y-1">
                  {selectedContent.logs && selectedContent.logs.length > 0 ? (
                    (() => {
                      const logs = selectedContent.logs!;
                      return [...new Set(logs.map((l) => l.phase))].map((phase) => {
                        const phaseLogs = logs.filter((l) => l.phase === phase);
                        const completed = phaseLogs.filter((l) => l.status === "completed").length;
                        const status = completed === phaseLogs.length ? "completed" : completed > 0 ? "running" : "pending";
                        return (
                          <div key={phase} className="flex justify-between items-center">
                            <span className="text-xs mono-font">{phase.replace(/_/g, " ")}</span>
                            <span className={`text-xs px-2 py-1 rounded ${getPhaseColor(status)}`}>
                              {status === "completed" ? "✓" : status === "running" ? `${completed}/${phaseLogs.length}` : "○"}
                            </span>
                          </div>
                        );
                      });
                    })()
                  ) : (
                    <div className="text-xs text-muted mono-font">No pipeline logs yet</div>
                  )}
                </div>
              </div>

              <div className="bg-stone border border-ink p-4">
                <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">
                  EXPERT REVIEWS
                </div>
                {selectedContent.expert_reviews && selectedContent.expert_reviews.length > 0 ? (
                  <div className="space-y-2">
                    {selectedContent.expert_reviews.map((review) => (
                      <div key={review.expert_name} className="text-xs">
                        <div className="flex justify-between">
                          <span className="mono-font">{review.expert_name}</span>
                          <span className={review.passed ? "text-green-600" : "text-red-600"}>
                            {review.score}/100
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-xs text-muted mono-font">No expert reviews yet</div>
                )}
              </div>

              <div className="bg-stone border border-ink p-4">
                <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">
                  ACTION REQUIRED
                </div>
                <button
                  onClick={() => publishContent(selectedContent.id)}
                  className="w-full text-xs px-2 py-1 bg-red-500 text-stone border border-ink hover:bg-red-600"
                >
                  Approve & Publish (needs X-User-Id: {userId})
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}