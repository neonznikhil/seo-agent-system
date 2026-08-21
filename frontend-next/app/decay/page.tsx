"use client";

import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface DecayItem {
  id: string;
  url: string;
  keyword: string;
  old_rank: number;
  current_rank: number;
  change: number;
  status: string;
}

export default function DecayPage() {
  const [decayItems, setDecayItems] = useState<DecayItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchDecayData() {
      try {
        setLoading(true);
        const websiteId = getCurrentWebsiteId();
        const data = await get(`/decay/${websiteId}/list`);
        const items = data?.decay_logs || data?.items || data || [];
        setDecayItems(Array.isArray(items) ? items : []);
        setError(null);
      } catch (e) {
        setError("Backend not running - run uvicorn main:app --reload in backend");
        setDecayItems([]);
      } finally {
        setLoading(false);
      }
    }

    fetchDecayData();
  }, []);

  const totalDecaying = decayItems.filter((d) => d.status === "decaying" || d.change > 0).length;
  const totalRecovered = decayItems.filter((d) => d.status === "recovered" || d.change < -5).length;

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2 text-[11px] text-muted">
          <span className="w-2 h-2 bg-accent" />
          <span>Decay</span>
        </div>
        <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">Content Decay</h1>
        <div className="grid grid-cols-2 gap-4">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="bg-stone border border-ink p-4">
              <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">Stats</div>
              <div className="h-20 bg-line animate-pulse" />
            </div>
          ))}
        </div>
        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Decaying Pages</div>
          <div className="space-y-2">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-10 border border-line bg-line animate-pulse" />
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
          <span>Decay</span>
        </div>
        <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">Content Decay</h1>
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
        <span>Decay</span>
      </div>
      <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">Content Decay</h1>
      <p className="text-[11px] text-muted uppercase tracking-widest mono-font">
        Track content that has lost rankings over time
      </p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-stone border border-ink p-4">
          <div className="text-[11px] text-muted uppercase tracking-wider mono-font mb-2">Decaying</div>
          <div className="text-2xl font-bold dot-font text-red-500">{totalDecaying}</div>
        </div>
        <div className="bg-stone border border-ink p-4">
          <div className="text-[11px] text-muted uppercase tracking-wider mono-font mb-2">Recovered</div>
          <div className="text-2xl font-bold dot-font text-green-600">{totalRecovered}</div>
        </div>
        <div className="bg-stone border border-ink p-4">
          <div className="text-[11px] text-muted uppercase tracking-wider mono-font mb-2">Total Pages</div>
          <div className="text-2xl font-bold dot-font">{decayItems.length}</div>
        </div>
        <div className="bg-stone border border-ink p-4">
          <div className="text-[11px] text-muted uppercase tracking-wider mono-font mb-2">Avg Change</div>
          <div className="text-2xl font-bold dot-font">
            {decayItems.length > 0
              ? (decayItems.reduce((a, b) => a + b.change, 0) / decayItems.length).toFixed(1)
              : "0.0"}
          </div>
        </div>
      </div>

      <div className="bg-stone border border-ink p-4">
        <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Decaying Pages</div>
        {decayItems.length === 0 ? (
          <div className="text-center py-8 text-muted mono-font text-sm">No decay data available</div>
        ) : (
          <div className="space-y-2">
            {decayItems.map((item, i) => (
              <div key={i} className="flex justify-between items-center border-b border-line pb-2 last:border-b-0">
                <div>
                  <div className="mono-font text-sm">{item.url || `Page ${i + 1}`}</div>
                  <div className="text-[10px] text-muted mono-font">kw: {item.keyword}</div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <div className="text-[10px] text-muted mono-font">
                      {item.old_rank} → {item.current_rank}
                    </div>
                    <div className={`text-[10px] mono-font ${item.change > 0 ? "text-red-500" : "text-green-600"}`}>
                      {item.change > 0 ? `+${item.change}` : item.change}
                    </div>
                  </div>
                  <span
                    className={`text-[10px] px-2 py-0.5 mono-font ${
                      item.change > 0 ? "bg-red-500 text-paper" : "bg-green-500 text-paper"
                    }`}
                  >
                    {item.change > 0 ? "DECAYING" : "RECOVERED"}
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
