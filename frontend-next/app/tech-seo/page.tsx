"use client";

import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { StatusPieChart } from "@/components/StatusPieChart";
import { getCurrentWebsiteId } from "@/lib/website";

interface Issue {
  severity: "high" | "medium" | "low";
  message: string;
}

export default function TechSeoPage() {
  const [healthScore, setHealthScore] = useState<number | null>(null);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchTechSEOData() {
      try {
        setLoading(true);
        const websiteId = getCurrentWebsiteId();
        const techData = await get(`/tech-seo/${websiteId}`);
        setHealthScore(techData.health_score);
        setIssues(techData.issues || []);
        setError(null);
      } catch (err) {
        setError("Backend not running - run uvicorn main:app --reload in backend");
        setHealthScore(null);
        setIssues([]);
      } finally {
        setLoading(false);
      }
    }

    fetchTechSEOData();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <h1 className="text-3xl font-bold dot-font">TECHNICAL SEO</h1>
        </div>

        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Health Score</div>
          <div className="flex items-center justify-center py-8">
            <div className="w-4 h-4 border-2 border-ink border-t-transparent rounded-full animate-spin" />
          </div>
        </div>

        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Issues</div>
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => (
              <li key={i} className="flex items-center justify-center h-12 border border-[D1CCC4] border-dashed">
                <span className="text-[10px] text-muted mono-font">Loading issue...</span>
              </li>
            ))}
          </div>
        </div>

        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">RECOMMENDATIONS</div>
          <div className="grid grid-cols-2 gap-3">
            <div className="border border-line p-3">
              <div className="text-[10px] text-muted mono-font mb-1">FIX</div>
              <div className="mono-font text-sm">Loading...</div>
            </div>
            <div className="border border-line p-3">
              <div className="text-[10px] text-muted mono-font mb-1">WATCH</div>
              <div className="mono-font text-sm">Loading...</div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <h1 className="text-3xl font-bold dot-font">TECHNICAL SEO</h1>
        </div>

        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Health Score</div>
          <div className="text-[11px] text-ink mono-font text-center py-8">
            {error}
          </div>
        </div>

        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Issues</div>
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => (
              <li key={i} className="flex items-center justify-center h-12 border border-[D1CCC4] border-dashed">
                <span className="text-[10px] text-muted mono-font">Backend offline</span>
              </li>
            ))}
          </div>
        </div>

        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">RECOMMENDATIONS</div>
          <div className="grid grid-cols-2 gap-3">
            <div className="border border-line p-3">
              <div className="text-[10px] text-muted mono-font mb-1">FIX</div>
              <div className="mono-font text-sm">Error loading data</div>
            </div>
            <div className="border border-line p-3">
              <div className="text-[10px] text-muted mono-font mb-1">WATCH</div>
              <div className="mono-font text-sm">Error loading data</div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (healthScore === null) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <h1 className="text-3xl font-bold dot-font">TECHNICAL SEO</h1>
        </div>
        <div className="bg-stone border border-ink p-4 text-center">
          <div className="text-[11px] text-ink mono-font">No data available</div>
        </div>
      </div>
    );
  }

  const getSeverityColor = (severity: Issue["severity"]): string => {
    switch (severity) {
      case "high": return "#FF4D12";
      case "medium": return "#D1CCC4";
      case "low": return "#6B6B6B";
      default: return "#6B6B6B";
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <h1 className="text-3xl font-bold dot-font">TECHNICAL SEO</h1>
      </div>

      <div className="bg-stone border border-ink p-4">
        <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Health Score</div>
        <div className="flex items-center gap-6">
          <div className="text-5xl font-bold dot-font">
            {healthScore}
            <span className="text-[10px] text-muted mono-font">/100</span>
          </div>
          <StatusPieChart data={[
            { label: "Pass", value: healthScore, color: "#FF4D12" },
            { label: "Fail", value: 100 - healthScore, color: "#111" },
          ]} />
        </div>
      </div>

      <div className="bg-stone border border-ink p-4">
        <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Issues</div>
        <ul className="space-y-2">
          {issues.map((issue, i) => (
            <li key={i} className="flex items-center gap-3 border-b border-line pb-2 last:border-b-0">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: getSeverityColor(issue.severity) }} />
              <span className="text-sm mono-font">{issue.message}</span>
              <span className="text-[10px] text-muted mono-font uppercase">{issue.severity}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="bg-stone border border-ink p-4">
        <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">RECOMMENDATIONS</div>
        <div className="grid grid-cols-2 gap-3">
          <div className="border border-line p-3">
            <div className="text-[10px] text-muted mono-font mb-1">FIX</div>
            <div className="mono-font text-sm">{issues.filter((i) => i.severity === "high").length > 0 ? "Fix " + issues.filter((i) => i.severity === "high").length + " high-severity issues" : "No critical fixes needed"}</div>
          </div>
          <div className="border border-line p-3">
            <div className="text-[10px] text-muted mono-font mb-1">WATCH</div>
            <div className="mono-font text-sm">{issues.filter((i) => i.severity === "medium").length > 0 ? "Monitor " + issues.filter((i) => i.severity === "medium").length + " medium issues" : "No items to watch"}</div>
          </div>
        </div>
      </div>
    </div>
  );
}