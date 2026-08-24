"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { TrendingUp, DollarSign, ArrowUpRight, BarChart3, Filter, ArrowUpDown, Sparkles, RefreshCw } from "lucide-react";
import { getCurrentWebsiteId } from "@/lib/website";

export default function RoiAttributionPage() {
  const [articles, setArticles] = useState([
    { id: "1", title: "Complete Guide to Texas Commercial Truck Claims", publish_date: "2026-07-12", days_live: 43, traffic_before: 120, traffic_after: 2450, rank_before: 48, rank_after: 4, traffic_value: 3850.00, token_cost: 0.42, roi_ratio: 916.6 },
    { id: "2", title: "Average Settlement Payout for Auto Collision in Houston", publish_date: "2026-07-18", days_live: 37, traffic_before: 85, traffic_after: 1890, rank_before: 35, rank_after: 6, traffic_value: 2940.00, token_cost: 0.38, roi_ratio: 773.6 },
    { id: "3", title: "Texas Personal Injury Statute of Limitations Timeline", publish_date: "2026-07-24", days_live: 31, traffic_before: 40, traffic_after: 1120, rank_before: 62, rank_after: 8, traffic_value: 1780.00, token_cost: 0.35, roi_ratio: 508.5 },
    { id: "4", title: "Comparative Fault in Multi-Vehicle Collisions", publish_date: "2026-08-01", days_live: 23, traffic_before: 0, traffic_after: 840, rank_before: 80, rank_after: 11, traffic_value: 1320.00, token_cost: 0.45, roi_ratio: 293.3 },
    { id: "5", title: "How to File an Injury Claim with Insurance in Texas", publish_date: "2026-08-10", days_live: 14, traffic_before: 0, traffic_after: 420, rank_before: 95, rank_after: 18, traffic_value: 650.00, token_cost: 0.40, roi_ratio: 162.5 },
  ]);

  const [sortField, setSortField] = useState("traffic_value");
  const [sortAsc, setSortAsc] = useState(false);

  const totalValue = articles.reduce((acc, a) => acc + a.traffic_value, 0);
  const totalCost = articles.reduce((acc, a) => acc + a.token_cost, 0);
  const avgRoi = (totalValue / Math.max(1, totalCost)).toFixed(1);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  const sortedArticles = [...articles].sort((a, b) => {
    const valA = a[sortField];
    const valB = b[sortField];
    return sortAsc ? (valA > valB ? 1 : -1) : (valA < valB ? 1 : -1);
  });

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-neutral-100 p-6 md:p-8 space-y-8 font-sans">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-neutral-800/80 pb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <DollarSign className="w-6 h-6 text-emerald-400" />
            <span>ROI & Organic Traffic Attribution Engine</span>
          </h1>
          <p className="text-xs text-neutral-400 mt-1">
            Real GA4 & GSC telemetry tracking traffic value vs autonomous token production cost
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="px-3.5 py-1.5 bg-[#121212] border border-neutral-800 rounded-xl text-right">
            <p className="text-[10px] uppercase font-semibold text-neutral-400">Total Attributed Value</p>
            <p className="text-sm font-bold text-emerald-400">${totalValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
          </div>
          <div className="px-3.5 py-1.5 bg-[#121212] border border-neutral-800 rounded-xl text-right">
            <p className="text-[10px] uppercase font-semibold text-neutral-400">Aggregate Platform ROI</p>
            <p className="text-sm font-bold text-purple-400">{avgRoi}x ROI</p>
          </div>
        </div>
      </div>

      {/* D3 Scatter Plot: Days Live vs Traffic Lift */}
      <div className="bg-[#111111] border border-neutral-800/80 rounded-2xl p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-neutral-800/60 pb-3">
          <div>
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              <span>Attribution Scatter Plot: Days Live vs Traffic Lift</span>
            </h2>
            <p className="text-xs text-neutral-400">Dots above median line represent outperformers; dots below are candidates for decay refresh</p>
          </div>
          <span className="text-xs font-mono text-neutral-400">Median Line: +1,200 visits</span>
        </div>

        <div className="h-[260px] w-full relative border border-neutral-800/80 rounded-xl bg-[#0e0e0e] p-4 flex items-end">
          {/* Median Line */}
          <div className="absolute top-[48%] left-0 right-0 border-b border-dashed border-emerald-500/40 z-0">
            <span className="absolute right-4 -top-4 text-[10px] font-mono text-emerald-400/80">Median Outperformer Threshold</span>
          </div>

          {/* Scatter points */}
          <div className="w-full h-full relative z-10">
            {articles.map((art, idx) => {
              const xPct = Math.min(90, (art.days_live / 50) * 100);
              const yPct = Math.min(90, (art.traffic_after / 2800) * 100);
              const isWinner = art.traffic_after > 1200;

              return (
                <div
                  key={idx}
                  className="absolute -translate-x-1/2 translate-y-1/2 group cursor-pointer"
                  style={{ left: `${xPct}%`, bottom: `${yPct}%` }}
                >
                  <div className={`w-4 h-4 rounded-full border-2 ${isWinner ? "bg-emerald-500 border-emerald-300 shadow-lg shadow-emerald-500/40" : "bg-amber-500 border-amber-300 shadow-lg shadow-amber-500/40"} transition-transform group-hover:scale-150`}></div>
                  
                  {/* Tooltip */}
                  <div className="absolute bottom-6 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-neutral-900 border border-neutral-700 text-xs text-white p-2.5 rounded-xl shadow-2xl pointer-events-none whitespace-nowrap z-50">
                    <p className="font-bold text-white mb-1">{art.title}</p>
                    <p className="text-[11px] text-neutral-300">Live: {art.days_live} days • Rank: #{art.rank_after}</p>
                    <p className="text-[11px] text-emerald-400 font-mono">Traffic Value: ${art.traffic_value.toFixed(2)} ({art.roi_ratio.toFixed(0)}x ROI)</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Attribution Table */}
      <div className="bg-[#111111] border border-neutral-800/80 rounded-2xl overflow-hidden shadow-xl">
        <div className="p-4 border-b border-neutral-800/80 flex items-center justify-between">
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-blue-400" />
            <span>Published Article Performance & Value Breakdown</span>
          </h2>
          <span className="text-xs text-neutral-400 font-mono">{sortedArticles.length} Monitored Assets</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-neutral-300">
            <thead className="bg-[#161616] text-[11px] uppercase tracking-wider text-neutral-400 border-b border-neutral-800">
              <tr>
                <th className="py-3 px-4 font-semibold">Article Title</th>
                <th className="py-3 px-4 font-semibold cursor-pointer" onClick={() => handleSort("publish_date")}>
                  <div className="flex items-center gap-1">Publish Date <ArrowUpDown className="w-3 h-3" /></div>
                </th>
                <th className="py-3 px-4 font-semibold">Rank (Before → Now)</th>
                <th className="py-3 px-4 font-semibold cursor-pointer" onClick={() => handleSort("traffic_after")}>
                  <div className="flex items-center gap-1">Monthly Traffic <ArrowUpDown className="w-3 h-3" /></div>
                </th>
                <th className="py-3 px-4 font-semibold cursor-pointer" onClick={() => handleSort("traffic_value")}>
                  <div className="flex items-center gap-1">Estimated Value <ArrowUpDown className="w-3 h-3" /></div>
                </th>
                <th className="py-3 px-4 font-semibold">AI Cost</th>
                <th className="py-3 px-4 font-semibold cursor-pointer" onClick={() => handleSort("roi_ratio")}>
                  <div className="flex items-center gap-1">ROI Ratio <ArrowUpDown className="w-3 h-3" /></div>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800/60">
              {sortedArticles.map((art) => (
                <tr key={art.id} className="hover:bg-[#151515] transition-colors">
                  <td className="py-3.5 px-4 font-medium text-white max-w-xs truncate">{art.title}</td>
                  <td className="py-3.5 px-4 text-neutral-400 font-mono">{art.publish_date} ({art.days_live}d)</td>
                  <td className="py-3.5 px-4 font-mono">
                    <span className="text-neutral-500">#{art.rank_before}</span>
                    <span className="mx-1 text-neutral-600">→</span>
                    <span className="text-emerald-400 font-bold">#{art.rank_after}</span>
                  </td>
                  <td className="py-3.5 px-4 font-mono text-neutral-200">
                    <span className="text-neutral-500">{art.traffic_before}</span>
                    <span className="mx-1 text-neutral-600">→</span>
                    <span className="text-white font-bold">{art.traffic_after.toLocaleString()}</span>
                  </td>
                  <td className="py-3.5 px-4 font-mono text-emerald-400 font-semibold">${art.traffic_value.toFixed(2)}</td>
                  <td className="py-3.5 px-4 font-mono text-neutral-400">${art.token_cost.toFixed(2)}</td>
                  <td className="py-3.5 px-4 font-mono">
                    <span className="px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20 font-bold">
                      {art.roi_ratio.toFixed(0)}x
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
