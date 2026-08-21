"use client";

import { useEffect, useState } from "react";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface SERPResult {
  rank: number;
  url: string;
  title: string;
  description: string;
  has_table: boolean;
  word_count: number;
  h1?: string;
  h2s?: string[];
}

interface GSCKeyword {
  query: string;
  clicks: number;
  impressions: number;
  position: number;
  ctr: number;
}

export default function ResearchPage() {
  const [query, setQuery] = useState("");
  const [serpResults, setSerpResults] = useState<SERPResult[]>([]);
  const [gscKeywords, setGscKeywords] = useState<GSCKeyword[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"serp" | "gsc">("gsc");

  const websiteId = getCurrentWebsiteId();

  const loadGSC = async () => {
    try {
      setError(null);
      const data = await get(`/gsc/keywords/${websiteId}`);
      setGscKeywords(data?.keywords || []);
    } catch (e: any) {
      setError(e.message || "Failed to load GSC data");
    }
  };

  const runSERP = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    try {
      setLoading(true);
      setError(null);
      const data = await get(`/serp-analysis/${websiteId}?query=${encodeURIComponent(query.trim())}`);
      const results = data?.results || data?.serp_results || data?.top_results || [];
      setSerpResults(Array.isArray(results) ? results : []);
    } catch (e: any) {
      setError(e.message || "Failed to run SERP analysis");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGSC();
  }, [websiteId]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[11px] text-muted">
          <span className="w-2 h-2 bg-accent rounded-full" />
          <span>Research</span>
        </div>
      </div>

      <div>
        <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">Research</h1>
        <p className="text-[11px] text-muted uppercase tracking-widest mono-font mt-1">
          SERP analysis + GSC keywords
        </p>
      </div>

      <div className="bg-stone border border-ink p-4">
        <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">Run SERP Analysis</div>
        <form onSubmit={runSERP} className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter keyword to analyze..."
            className="field flex-1"
          />
          <button type="submit" disabled={loading || !query.trim()} className="btn btn-accent">
            {loading ? "Analyzing..." : "Analyze"}
          </button>
        </form>
      </div>

      {error && (
        <div className="bg-stone border border-red-500 p-4">
          <div className="text-[11px] mono-font text-red-500">{error}</div>
        </div>
      )}

      <div className="flex gap-2 border-b border-ink">
        <button onClick={() => setActiveTab("gsc")} className={`px-4 py-2 text-[10px] mono-font uppercase tracking-widest ${activeTab === "gsc" ? "border-b-2 border-accent text-accent" : "text-muted hover:text-ink"}`}>
          GSC Keywords
        </button>
        <button onClick={() => setActiveTab("serp")} className={`px-4 py-2 text-[10px] mono-font uppercase tracking-widest ${activeTab === "serp" ? "border-b-2 border-accent text-accent" : "text-muted hover:text-ink"}`}>
          SERP Results
        </button>
      </div>

      {activeTab === "gsc" && (
        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">GSC Keywords</div>
          {gscKeywords.length === 0 ? (
            <div className="text-[11px] text-muted mono-font py-4">No GSC data - Connect GSC in /settings</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Query</th>
                    <th>Clicks</th>
                    <th>Impressions</th>
                    <th>Position</th>
                    <th>CTR</th>
                  </tr>
                </thead>
                <tbody>
                  {gscKeywords.slice(0, 50).map((kw, i) => (
                    <tr key={i}>
                      <td className="font-medium">{kw.query}</td>
                      <td>{kw.clicks}</td>
                      <td>{kw.impressions}</td>
                      <td>{kw.position.toFixed(1)}</td>
                      <td>{(kw.ctr * 100).toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === "serp" && (
        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">SERP Results</div>
          {serpResults.length === 0 ? (
            <div className="text-[11px] text-muted mono-font py-4">No SERP data - Run analysis above</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {serpResults.slice(0, 10).map((result, i) => (
                <div key={i} className="border border-line p-3 hover:border-accent hover:bg-paper transition-colors">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] mono-font text-muted">#{result.rank}</span>
                    <div className="flex gap-2">
                      {result.has_table && <span className="badge badge-green">Table</span>}
                    </div>
                  </div>
                  <div className="mono-font text-sm mb-1">{result.title || result.url}</div>
                  <div className="text-[10px] text-muted mono-font mb-2">{result.description}</div>
                  <div className="flex gap-3 text-[9px] text-muted mono-font">
                    <span>{result.word_count} words</span>
                    {result.h1 && <span>H1: {result.h1}</span>}
                  </div>
                  {result.h2s && result.h2s.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {result.h2s.slice(0, 3).map((h2, j) => (
                        <div key={j} className="text-[9px] text-muted mono-font">H2: {h2}</div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
