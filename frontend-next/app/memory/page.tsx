"use client";

import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface MemoryItem {
  id: string;
  keyword: string;
  ctr: string;
  impressions: string;
}

export default function MemoryPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [memoryItems, setMemoryItems] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      setLoading(true);
      const websiteId = getCurrentWebsiteId();
      const data = await get(`/knowledge/search?q=${encodeURIComponent(searchQuery)}&website_id=${websiteId}`);
      const items: MemoryItem[] = Array.isArray(data)
        ? data.map((kb: any, index: number) => ({
            id: kb.id || `kb-${index}`,
            keyword: kb.title || kb.fact || `Item ${index + 1}`,
            ctr: kb.ctr ?? "0.0%",
            impressions: kb.impressions ?? "0",
          }))
        : [];
      setMemoryItems(items);
      setError(null);
    } catch (e) {
      setError("Search failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    async function fetchMemoryItems() {
      try {
        setLoading(true);
        const websiteId = getCurrentWebsiteId();
        const data = await get(`/memory/${websiteId}`);
        if (data && data.knowledge_base) {
          const items: MemoryItem[] = data.knowledge_base.map((kb: any, index: number) => ({
            id: kb.id || `kb-${index}`,
            keyword: kb.fact?.substring(0, 50) || `Fact ${index + 1}`,
            ctr: kb.ctr ?? "0.0%",
            impressions: kb.impressions ?? "0",
          }));
          setMemoryItems(items);
        } else {
          setMemoryItems([]);
        }
        setError(null);
      } catch (err) {
        setError("Backend not running - run uvicorn main:app --reload in backend");
        setMemoryItems([]);
      } finally {
        setLoading(false);
      }
    }

    fetchMemoryItems();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <h1 className="text-3xl font-bold dot-font">MEMORY</h1>
        </div>
        <div className="bg-paper border border-ink p-4">
          <div className="flex gap-2 mb-3">
            <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="flex-1 px-3 py-2 border border-ink text-[11px] mono-font" placeholder="Search knowledge base..." />
            <button className="px-4 py-2 bg-ink text-paper text-[11px] mono-font">
              <span className="w-2 h-2 bg-accent inline-block mr-1" />
              Search
            </button>
          </div>
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="border border-line p-3">
                <div className="text-sm mono-font">Loading memory item...</div>
                <div className="text-[10px] text-muted mono-font">Loading... imp / Loading... CTR</div>
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
        <div className="flex items-center gap-4">
          <h1 className="text-3xl font-bold dot-font">MEMORY</h1>
        </div>
        <div className="bg-paper border border-ink p-4">
          <div className="flex gap-2 mb-3">
            <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="flex-1 px-3 py-2 border border-ink text-[11px] mono-font" placeholder="Search knowledge base..." />
            <button className="px-4 py-2 bg-ink text-paper text-[11px] mono-font">
              <span className="w-2 h-2 bg-accent inline-block mr-1" />
              Search
            </button>
          </div>
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="border border-line p-3">
                <div className="text-sm mono-font">Backend offline</div>
                <div className="text-[10px] text-muted mono-font">Backend offline imp / Backend offline CTR</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (memoryItems.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <h1 className="text-3xl font-bold dot-font">MEMORY</h1>
        </div>
        <div className="bg-paper border border-ink p-4">
          <div className="flex gap-2 mb-3">
            <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="flex-1 px-3 py-2 border border-ink text-[11px] mono-font" placeholder="Search knowledge base..." />
            <button className="px-4 py-2 bg-ink text-paper text-[11px] mono-font">
              <span className="w-2 h-2 bg-accent inline-block mr-1" />
              Search
            </button>
          </div>
          <div className="text-xs text-muted mono-font mb-2">RECENT MEMORIES</div>
          <div className="text-xs text-muted mono-font">No knowledge base items found</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <h1 className="text-3xl font-bold dot-font">MEMORY</h1>
      </div>
      <div className="bg-paper border border-ink p-4">
        <div className="flex gap-2 mb-3">
          <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="flex-1 px-3 py-2 border border-ink text-[11px] mono-font" placeholder="Search knowledge base..." />
          <button className="px-4 py-2 bg-ink text-paper text-[11px] mono-font" onClick={handleSearch}>
            <span className="w-2 h-2 bg-accent inline-block mr-1" />
            Search
          </button>
        </div>
        <div className="text-xs text-muted mono-font mb-2">RECENT MEMORIES</div>
        <div className="space-y-2">
          {memoryItems.map((item) => (
            <div key={item.id} className="border border-line p-3">
              <div className="text-sm mono-font">{item.keyword}</div>
              <div className="text-[10px] text-muted mono-font">
                {item.impressions} imp / {item.ctr} CTR
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
