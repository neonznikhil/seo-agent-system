"use client";

import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";
import { StatusPieChart } from "@/components/StatusPieChart";

interface BacklinkItem {
  source_url: string;
  anchor_text: string;
  [key: string]: any;
}

export default function BacklinksPage() {
  const [backlinkKPIs, setBacklinkKPIs] = useState<Array<{ label: string; value: string; change: string }>>([]);
  const [anchorData, setAnchorData] = useState<Array<{ label: string; value: number; color: string }>>([]);
  const [recentBacklinks, setRecentBacklinks] = useState<Array<{ site: string; anchor: string }>>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchBacklinksData() {
      try {
        setLoading(true);
        const websiteId = getCurrentWebsiteId();
        const data = await get(`/backlinks/${websiteId}`);
        if (data) {
          const backlinks: BacklinkItem[] = (data.backlinks || []) as BacklinkItem[];
          const anchorDistribution = (data.anchor_distribution || {}) as Record<string, number>;
          const total = data.total || 0;
          
          // Calculate KPIs from the data
          const referringDomains = new Set(backlinks.map(b => b.source_url).filter(Boolean).map(url => {
            try { return new URL(url).hostname; } catch { return url; }
          })).size;
          
          const domainRating = Math.min(100, Math.floor(referringDomains / 10)); // Simplified DR calculation
          
          setBacklinkKPIs([
            { label: "TOTAL", value: total.toLocaleString(), change: "" },
            { label: "REFERENCES", value: referringDomains.toLocaleString(), change: "" },
            { label: "DR", value: domainRating.toString(), change: "" },
            { label: "DOMAINS", value: referringDomains.toLocaleString(), change: "" },
          ]);
          
          // Convert anchor distribution to chart data
          const anchorItems = Object.entries(anchorDistribution)
            .slice(0, 10) // Limit to top 10
             .map(([label, value]) => ({
               label: label || "Unknown",
               value,
               color: value > 20 ? "#FF4D12" : value > 10 ? "#111" : "#6B6B6B"
             }));
          
          setAnchorData(anchorItems.length > 0 ? anchorItems : [
            { label: "Brand", value: 0, color: "#FF4D12" },
            { label: "Keyword", value: 0, color: "#111" },
            { label: "Generic", value: 0, color: "#6B6B6B" },
          ]);
          
          // Get recent backlinks (most recent 5)
          const recent = backlinks
            .slice(0, 5)
            .map(b => ({
              site: b.source_url ? new URL(b.source_url).hostname : "Unknown",
              anchor: b.anchor_text || "Unknown"
            }));
          
          setRecentBacklinks(recent.length > 0 ? recent : []);
        } else {
          setBacklinkKPIs([
            { label: "TOTAL", value: "0", change: "+0%" },
            { label: "REFERENCES", value: "0", change: "+0%" },
            { label: "DR", value: "0", change: "+0" },
            { label: "DOMAINS", value: "0", change: "+0" },
          ]);
          setAnchorData([
            { label: "Brand", value: 0, color: "#FF4D12" },
            { label: "Keyword", value: 0, color: "#111" },
            { label: "Generic", value: 0, color: "#6B6B6B" },
          ]);
          setRecentBacklinks([]);
        }
        setError(null);
      } catch (err) {
        setError("Backend not running - run uvicorn main:app --reload in backend");
        setBacklinkKPIs([
          { label: "TOTAL", value: "0", change: "+0%" },
          { label: "REFERENCES", value: "0", change: "+0%" },
          { label: "DR", value: "0", change: "+0" },
          { label: "DOMAINS", value: "0", change: "+0" },
        ]);
        setAnchorData([
          { label: "Brand", value: 0, color: "#FF4D12" },
          { label: "Keyword", value: 0, color: "#111" },
          { label: "Generic", value: 0, color: "#6B6B6B" },
        ]);
        setRecentBacklinks([]);
      } finally {
        setLoading(false);
      }
    }

    fetchBacklinksData();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <h1 className="text-3xl font-bold dot-font">BACKLINKS</h1>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-stone border border-ink p-4">
              <div className="flex items-center justify-center py-8">
                <div className="w-4 h-4 border-2 border-ink border-t-transparent rounded-full animate-spin" />
              </div>
            </div>
          ))}
        </div>

        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Anchor Distribution</div>
          <div className="flex items-center justify-center py-8">
            <div className="w-4 h-4 border-2 border-ink border-t-transparent rounded-full animate-spin" />
          </div>
        </div>

        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Recent Backlinks</div>
          <div className="flex items-center justify-center py-8">
            <div className="w-4 h-4 border-2 border-ink border-t-transparent rounded-full animate-spin" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <h1 className="text-3xl font-bold dot-font">BACKLINKS</h1>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-stone border border-ink p-4">
              <div className="text-[11px] text-ink mono-font text-center">
                {error}
              </div>
            </div>
          ))}
        </div>

        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Anchor Distribution</div>
          <div className="flex items-center justify-center py-8">
            <div className="text-[11px] text-ink mono-font">Backend offline</div>
          </div>
        </div>

        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Recent Backlinks</div>
          <div className="flex items-center justify-center py-8">
            <div className="text-[11px] text-ink mono-font">Backend offline</div>
          </div>
        </div>
      </div>
    );
  }

  if (!backlinkKPIs || backlinkKPIs.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <h1 className="text-3xl font-bold dot-font">BACKLINKS</h1>
        </div>
        <div className="bg-stone border border-ink p-4 text-center">
          <div className="text-[11px] text-ink mono-font">No data available</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <h1 className="text-3xl font-bold dot-font">BACKLINKS</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {backlinkKPIs.map((kpi) => (
          <div key={kpi.label} className="bg-stone border border-ink p-4">
            <div className="text-xs text-muted uppercase mono-font">{kpi.label}</div>
            <div className="text-2xl font-bold dot-font mt-1">
              {kpi.value}
              <span className="text-[10px] text-muted"> {kpi.change}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-stone border border-ink p-4">
        <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Anchor Distribution</div>
        <div className="flex items-center gap-6">
          <StatusPieChart data={anchorData} />
          <div className="space-y-2">
            {anchorData.map((item, i) => (
              <div key={item.label} className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
                <span className="text-[11px] mono-font">{item.label}</span>
                <span className="text-[10px] text-muted mono-font"> {item.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-stone border border-ink p-4">
        <div className="text-xs text-muted uppercase tracking-wider mono-font mb-4">Recent Backlinks</div>
        <div className="space-y-2">
          {recentBacklinks.map((link, i) => (
            <div key={i} className="flex justify-between border-b border-line pb-2 last:border-b-0">
              <span className="mono-font text-sm">{link.site}</span>
              <span className="text-[10px] text-muted mono-font">"{link.anchor}"</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}