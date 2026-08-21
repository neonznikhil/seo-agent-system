"use client";

import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface KnowledgeEntry {
  id: string;
  fact: string;
  source?: string;
  created_at?: string;
}

export default function KnowledgePage() {
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchKnowledge() {
      try {
        setLoading(true);
        const websiteId = getCurrentWebsiteId();
        const data = await get(`/memory/${websiteId}`);
        const knowledgeBase = data?.knowledge_base || [];
        const mapped: KnowledgeEntry[] = Array.isArray(knowledgeBase)
          ? knowledgeBase.map((kb: any, index: number) => ({
              id: kb.id || `kb-${index}`,
              fact: kb.fact || `Knowledge item ${index + 1}`,
              source: kb.source || kb.metadata?.source,
              created_at: kb.created_at,
            }))
          : [];
        setEntries(mapped);
        setError(null);
      } catch (e) {
        setError("Backend not running - run uvicorn main:app --reload in backend");
        setEntries([]);
      } finally {
        setLoading(false);
      }
    }

    fetchKnowledge();
  }, []);

  const filteredEntries = entries.filter((entry) =>
    entry.fact.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2 text-[11px] text-muted">
          <span className="w-2 h-2 bg-accent" />
          <span>Knowledge</span>
        </div>
        <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">Knowledge Base</h1>
        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">Search</div>
          <div className="h-10 bg-line animate-pulse mb-4" />
          <div className="space-y-2">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="border border-line p-3">
                <div className="h-4 bg-line animate-pulse mb-2" />
                <div className="h-3 bg-line animate-pulse w-2/3" />
              </div>
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
          <span>Knowledge</span>
        </div>
        <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">Knowledge Base</h1>
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
        <span>Knowledge</span>
      </div>
      <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">Knowledge Base</h1>
      <p className="text-[11px] text-muted uppercase tracking-widest mono-font">
        {entries.length} entries indexed
      </p>

      <div className="bg-stone border border-ink p-4">
        <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">Search</div>
        <div className="flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search knowledge base..."
            className="field flex-1"
          />
          <button className="btn btn-primary">
            <span className="w-2 h-2 bg-accent inline-block mr-1" />
            Search
          </button>
        </div>
      </div>

      <div className="bg-stone border border-ink p-4">
        <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">
          {searchQuery ? `Results for "${searchQuery}"` : "All Entries"}
        </div>
        <div className="space-y-2">
          {filteredEntries.length === 0 ? (
            <div className="text-center py-8 text-muted mono-font text-sm">
              {searchQuery ? "No matching entries found" : "No knowledge base entries available"}
            </div>
          ) : (
            filteredEntries.map((entry) => (
              <div key={entry.id} className="border border-line p-3">
                <div className="mono-font text-sm">{entry.fact}</div>
                {entry.source && (
                  <div className="text-[10px] text-muted mono-font mt-1">Source: {entry.source}</div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
