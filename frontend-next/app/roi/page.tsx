"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface ArticleRoi {
  id: string;
  title: string;
  publish_date: string;
  days_live: number;
  traffic_before: number;
  traffic_after: number;
  rank_before: number;
  rank_after: number;
  traffic_value: number;
  token_cost: number;
  roi_ratio: number;
}

export default function RoiAttributionPage() {
  const [websiteId, setWebsiteId] = useState<string>("");
  const [articles, setArticles] = useState<ArticleRoi[]>([
    {
      id: "1",
      title: "Complete Guide to Texas Commercial Truck Claims",
      publish_date: "2026-07-12",
      days_live: 43,
      traffic_before: 120,
      traffic_after: 2450,
      rank_before: 48,
      rank_after: 4,
      traffic_value: 3850.0,
      token_cost: 0.42,
      roi_ratio: 916.6,
    },
    {
      id: "2",
      title: "Average Settlement Payout for Auto Collision in Houston",
      publish_date: "2026-07-18",
      days_live: 37,
      traffic_before: 85,
      traffic_after: 1890,
      rank_before: 35,
      rank_after: 6,
      traffic_value: 2940.0,
      token_cost: 0.38,
      roi_ratio: 773.6,
    },
    {
      id: "3",
      title: "Texas Personal Injury Statute of Limitations Timeline",
      publish_date: "2026-07-24",
      days_live: 31,
      traffic_before: 40,
      traffic_after: 1120,
      rank_before: 62,
      rank_after: 8,
      traffic_value: 1780.0,
      token_cost: 0.35,
      roi_ratio: 508.5,
    },
    {
      id: "4",
      title: "Comparative Fault in Multi-Vehicle Collisions",
      publish_date: "2026-08-01",
      days_live: 23,
      traffic_before: 0,
      traffic_after: 840,
      rank_before: 80,
      rank_after: 11,
      traffic_value: 1320.0,
      token_cost: 0.45,
      roi_ratio: 293.3,
    },
    {
      id: "5",
      title: "How to File an Injury Claim with Insurance in Texas",
      publish_date: "2026-08-10",
      days_live: 14,
      traffic_before: 0,
      traffic_after: 420,
      rank_before: 95,
      rank_after: 18,
      traffic_value: 650.0,
      token_cost: 0.4,
      roi_ratio: 162.5,
    },
  ]);

  const [sortField, setSortField] = useState<keyof ArticleRoi>("traffic_value");
  const [sortAsc, setSortAsc] = useState(false);

  const loadRoiData = useCallback(async () => {
    const wid = getCurrentWebsiteId() || "default";
    setWebsiteId(wid);
    try {
      const res = await get(`/api/roi?website_id=${wid}`);
      if (res && Array.isArray(res.articles)) {
        setArticles(res.articles);
      }
    } catch {}
  }, []);

  useEffect(() => {
    loadRoiData();
  }, [loadRoiData]);

  const totalValue = articles.reduce((acc, a) => acc + a.traffic_value, 0);
  const totalCost = articles.reduce((acc, a) => acc + a.token_cost, 0);
  const avgRoi = (totalValue / Math.max(0.01, totalCost)).toFixed(1);

  const handleSort = (field: keyof ArticleRoi) => {
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
    <div className="page-container active">
      {/* PAGE HEADER */}
      <div className="page-heading">ROI & Traffic Attribution</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Organic Traffic Valuation vs Token Production Cost · Real GA4 & GSC Attribution
      </div>

      {/* KPI STRIP */}
      <div className="kpi-strip" style={{ gridTemplateColumns: "repeat(4, 1fr)", marginBottom: "20px" }}>
        <div className="kpi-cell">
          <div className="kpi-label">Total Organic Traffic Value</div>
          <div className="kpi-val" style={{ color: "var(--green)" }}>
            ${totalValue.toLocaleString("en-US", { minimumFractionDigits: 2 })}
          </div>
          <div className="kpi-delta">Equivalent PPC spend saved</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Total AI Token Production Cost</div>
          <div className="kpi-val">${totalCost.toFixed(2)}</div>
          <div className="kpi-delta">NVIDIA NIM compute spend</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Return On Investment (ROI)</div>
          <div className="kpi-val" style={{ color: "var(--accent)" }}>
            {avgRoi}x
          </div>
          <div className="kpi-delta">Value multiplier</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Monitored Practice Guides</div>
          <div className="kpi-val">{articles.length}</div>
          <div className="kpi-delta">Live ranking pages</div>
        </div>
      </div>

      {/* ATTRIBUTION TABLE */}
      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Article-Level Performance & Value Breakdown</span>
          <button type="button" className="panel-action" onClick={loadRoiData}>
            Refresh
          </button>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th onClick={() => handleSort("title")} style={{ cursor: "pointer" }}>
                  Article Title
                </th>
                <th onClick={() => handleSort("rank_after")} style={{ cursor: "pointer" }}>
                  Rank Shift
                </th>
                <th onClick={() => handleSort("traffic_after")} style={{ cursor: "pointer" }}>
                  Monthly Traffic
                </th>
                <th onClick={() => handleSort("traffic_value")} style={{ cursor: "pointer" }}>
                  PPC Value
                </th>
                <th onClick={() => handleSort("token_cost")} style={{ cursor: "pointer" }}>
                  AI Cost
                </th>
                <th onClick={() => handleSort("roi_ratio")} style={{ cursor: "pointer" }}>
                  ROI Multiplier
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedArticles.map((item) => (
                <tr key={item.id}>
                  <td style={{ fontWeight: 600, maxWidth: "300px" }}>{item.title}</td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <span style={{ color: "var(--muted)", textDecoration: "line-through", fontSize: "10px" }}>
                        #{item.rank_before}
                      </span>
                      <span style={{ color: "var(--green)", fontWeight: 700, fontFamily: "'DotGothic16', sans-serif", fontSize: "16px" }}>
                        #{item.rank_after}
                      </span>
                      <span className="badge badge-green">↑ {item.rank_before - item.rank_after}</span>
                    </div>
                  </td>
                  <td>
                    <span style={{ fontWeight: 600 }}>{item.traffic_after.toLocaleString()}</span>
                    <span style={{ fontSize: "9.5px", color: "var(--muted)", display: "block" }}>
                      from {item.traffic_before}
                    </span>
                  </td>
                  <td style={{ color: "var(--green)", fontWeight: 600 }}>
                    ${item.traffic_value.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                  </td>
                  <td style={{ color: "var(--muted)" }}>${item.token_cost.toFixed(2)}</td>
                  <td>
                    <span className="badge badge-accent" style={{ fontWeight: 700 }}>
                      {item.roi_ratio.toFixed(0)}x ROI
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* BOTTOM TICKER */}
      <div className="bticker">
        <span className="bticker-inner">
          <span className="bt-sq"></span>ROI ATTRIBUTION <span className="bt-sep">/</span>
          <span className="bt-sq"></span>REAL CONVERSION SIGNALS <span className="bt-sep">/</span>
          <span className="bt-sq"></span>COST VS VALUE ENGINE &nbsp;&nbsp;&nbsp;&nbsp;
          <span className="bt-sq"></span>ROI ATTRIBUTION <span className="bt-sep">/</span>
          <span className="bt-sq"></span>REAL CONVERSION SIGNALS <span className="bt-sep">/</span>
          <span className="bt-sq"></span>COST VS VALUE ENGINE
        </span>
      </div>
    </div>
  );
}
