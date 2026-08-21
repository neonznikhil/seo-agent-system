"use client";

import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface Cluster {
  id: string;
  topic: string;
  keywords: string[];
  search_volume: number;
  difficulty: number;
  intent: string;
}

interface ClusterGroup {
  cluster_topic: string;
  keywords: string[];
  avg_volume: number;
  avg_difficulty: number;
}

export default function ClustersPage() {
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [groupedClusters, setGroupedClusters] = useState<ClusterGroup[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchClusters() {
      try {
        setLoading(true);
        const websiteId = getCurrentWebsiteId();
        const data = await get(`/clusters?website_id=${websiteId}`);
        const rawClusters = data || [];
        setClusters(Array.isArray(rawClusters) ? rawClusters : []);
        const groups: ClusterGroup[] = Array.isArray(rawClusters)
          ? rawClusters.map((c: any) => ({
              cluster_topic: c.name || c.cluster_topic || "Unnamed",
              keywords: Array.isArray(c.keywords) ? c.keywords : [],
              avg_volume: c.search_volume || c.avg_volume || 0,
              avg_difficulty: c.difficulty || c.avg_difficulty || 0,
            }))
          : [];
        setGroupedClusters(groups);
        setError(null);
      } catch (e) {
        setError("Backend not running - run uvicorn main:app --reload in backend");
        setClusters([]);
        setGroupedClusters([]);
      } finally {
        setLoading(false);
      }
    }

    fetchClusters();
  }, []);

  const difficultyColor = (d: number) => {
    if (d > 70) return "text-red-500";
    if (d > 40) return "text-yellow-600";
    return "text-green-600";
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2 text-[11px] text-muted">
          <span className="w-2 h-2 bg-accent" />
          <span>Clusters</span>
        </div>
        <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">Keyword Clusters</h1>
        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Cluster Map</div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="border border-line p-4 h-32 bg-line animate-pulse" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2 text-[11px] text-muted">
          <span className="w-2 h-2 bg-accent" />
          <span>Clusters</span>
        </div>
        <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">Keyword Clusters</h1>
        <div className="bg-stone border border-ink p-4 text-center">
          <div className="text-[11px] mono-font">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-[11px] text-muted">
        <span className="w-2 h-2 bg-accent" />
        <span>Clusters</span>
      </div>
      <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">Keyword Clusters</h1>
      <p className="text-[11px] text-muted uppercase tracking-widest mono-font">
        {groupedClusters.length} clusters found
      </p>

      <div className="bg-stone border border-ink p-4">
        <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Cluster Map</div>
        {groupedClusters.length === 0 ? (
          <div className="text-center py-12 text-muted mono-font text-sm">No keyword clusters available</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {groupedClusters.map((cluster, i) => (
              <div key={i} className="border border-ink p-4">
                <div className="text-sm font-bold dot-font mb-2">{cluster.cluster_topic}</div>
                <div className="space-y-1 mb-3">
                  {cluster.keywords.slice(0, 5).map((kw, j) => (
                    <div key={j} className="text-[11px] mono-font text-muted truncate">· {kw}</div>
                  ))}
                  {cluster.keywords.length > 5 && (
                    <div className="text-[10px] text-muted mono-font">+{cluster.keywords.length - 5} more</div>
                  )}
                </div>
                <div className="flex justify-between text-[10px] mono-font">
                  <span className="text-muted">VOL: {cluster.avg_volume.toLocaleString()}</span>
                  <span className={difficultyColor(cluster.avg_difficulty)}>
                    DIFF: {cluster.avg_difficulty}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
