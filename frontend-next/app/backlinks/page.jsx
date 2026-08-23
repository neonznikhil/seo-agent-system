"use client";

import React, { useState, useEffect } from "react";
import { 
  Link2, Mail, CheckCircle2, XCircle, ShieldAlert, Sparkles, 
  ExternalLink, Search, RefreshCw, Send, ThumbsDown, Check,
  TrendingUp, Award, Layers
} from "lucide-react";

export default function BacklinksPage() {
  const [opportunities, setOpportunities] = useState([]);
  const [stats, setStats] = useState({ total_opportunities: 0, pending_approval: 0, contacted_outreach: 0, average_domain_authority: 45 });
  const [loading, setLoading] = useState(true);
  const [prospecting, setProspecting] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchKeyword, setSearchKeyword] = useState("");
  const [expandedDraftId, setExpandedDraftId] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadData();
  }, [statusFilter]);

  const loadData = async () => {
    setLoading(true);
    try {
      const filterParam = statusFilter !== "all" ? `?status=${statusFilter}` : "";
      const [oppRes, statsRes] = await Promise.all([
        fetch(`http://localhost:8000/api/backlinks/opportunities${filterParam}`),
        fetch("http://localhost:8000/api/backlinks/stats"),
      ]);

      if (oppRes.ok) {
        const data = await oppRes.json();
        setOpportunities(Array.isArray(data) ? data : []);
      }
      if (statsRes.ok) {
        const sData = await statsRes.json();
        setStats(sData);
      }
    } catch (e) {
      console.warn("Backlinks load error:", e);
      setError("Failed to connect to backlink engine");
    } finally {
      setLoading(false);
    }
  };

  const handleApproveSend = async (id) => {
    try {
      const res = await fetch(`http://localhost:8000/api/backlinks/${id}/approve-send`, { method: "POST" });
      if (res.ok) {
        setOpportunities((prev) =>
          prev.map((o) => (o.id === id ? { ...o, status: "contacted" } : o))
        );
        loadData();
      }
    } catch (e) {
      console.warn("Approve send error:", e);
    }
  };

  const handleReject = async (id) => {
    try {
      const res = await fetch(`http://localhost:8000/api/backlinks/${id}/reject`, { method: "POST" });
      if (res.ok) {
        setOpportunities((prev) => prev.filter((o) => o.id !== id));
        loadData();
      }
    } catch (e) {
      console.warn("Reject error:", e);
    }
  };

  const handleRunProspecting = async (e) => {
    e.preventDefault();
    setProspecting(true);
    setError(null);
    try {
      const res = await fetch("http://localhost:8000/api/backlinks/prospect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword: searchKeyword || "Houston accident legal resources" }),
      });
      if (res.ok) {
        loadData();
      }
    } catch (e) {
      setError("Prospecting loop failed");
    } finally {
      setProspecting(false);
    }
  };

  const getTypeBadgeClass = (type) => {
    switch (type) {
      case "competitor_replication":
        return "bg-blue-500/10 text-blue-400 border-blue-500/30";
      case "unlinked_mention":
        return "bg-purple-500/10 text-purple-400 border-purple-500/30";
      case "broken_link":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      default:
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
    }
  };

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-200 p-6 md:p-8">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800 pb-6">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-blue-500/10 text-blue-400 rounded-lg border border-blue-500/20">
              <Link2 className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">4-Module Autonomous Backlink Engine</h1>
              <p className="text-sm text-gray-400">Prospecting · Qualification (DA&gt;30) · Personalization · Human-in-the-Loop Review</p>
            </div>
          </div>

          <form onSubmit={handleRunProspecting} className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Prospect keyword niche..."
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              className="bg-gray-900 border border-gray-800 rounded-lg px-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
            <button
              type="submit"
              disabled={prospecting}
              className="py-1.5 px-4 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition flex items-center gap-1.5 shadow-lg shadow-blue-900/30"
            >
              <Sparkles className="w-3.5 h-3.5" />
              {prospecting ? "Prospecting..." : "Run Prospecting Loop"}
            </button>
          </form>
        </div>
      </div>

      {/* 4 Stats Cards */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Total Qualified Leads</span>
            <Layers className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">{stats.total_opportunities}</div>
          <p className="text-[11px] text-gray-500">Filtered DA &gt; 30</p>
        </div>

        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Pending Approval</span>
            <Mail className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-300 mb-1">{stats.pending_approval}</div>
          <p className="text-[11px] text-gray-500">Drafted pitches staged for review</p>
        </div>

        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Contacted Outreach</span>
            <Send className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-300 mb-1">{stats.contacted_outreach}</div>
          <p className="text-[11px] text-gray-500">Approved and sent to editors</p>
        </div>

        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Avg Domain Authority</span>
            <Award className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-2xl font-bold text-purple-300 mb-1">DA {stats.average_domain_authority}</div>
          <p className="text-[11px] text-gray-500">High-trust authority domains</p>
        </div>
      </div>

      {/* Main Opportunities List */}
      <div className="max-w-7xl mx-auto bg-gray-900/80 border border-gray-800 rounded-xl p-6 shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-800 pb-4 mb-6">
          <h3 className="font-semibold text-sm text-white">Qualified Link Building Opportunities</h3>
          <div className="flex items-center gap-1.5">
            {["all", "pending", "contacted"].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`py-1 px-3 rounded-full text-xs font-medium transition border ${
                  statusFilter === st
                    ? "bg-blue-600 text-white border-blue-500"
                    : "bg-gray-950 text-gray-400 border-gray-800 hover:border-gray-700"
                }`}
              >
                {st}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="py-12 text-center text-xs text-gray-500 font-mono">
            Running qualification and personalization algorithms...
          </div>
        ) : opportunities.length === 0 ? (
          <div className="py-12 text-center text-xs text-gray-500">
            No opportunities found. Click "Run Prospecting Loop" above to discover new high-DA link leads.
          </div>
        ) : (
          <div className="space-y-4">
            {opportunities.map((opp) => (
              <div
                key={opp.id}
                className="bg-gray-950 border border-gray-800/90 rounded-xl p-5 hover:border-gray-700 transition"
              >
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2.5 mb-2 flex-wrap">
                      <span className="font-mono text-xs font-bold px-2 py-0.5 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded">
                        DA {opp.domain_authority || 45}
                      </span>
                      <span className={`text-[11px] font-semibold px-2 py-0.5 rounded border uppercase tracking-wider ${getTypeBadgeClass(opp.type)}`}>
                        {(opp.type || "outreach").replace("_", " ")}
                      </span>
                      <span className={`text-[11px] font-semibold px-2 py-0.5 rounded ${opp.status === "contacted" ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-400"}`}>
                        {opp.status}
                      </span>
                    </div>

                    <a
                      href={opp.target_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm font-semibold text-white hover:text-blue-400 transition flex items-center gap-1.5 mb-1"
                    >
                      {opp.target_url} <ExternalLink className="w-3.5 h-3.5 text-gray-500" />
                    </a>

                    {opp.gap_analysis && (
                      <p className="text-xs text-gray-400 mb-2">
                        <span className="text-gray-500 font-semibold">Content Gap:</span> {opp.gap_analysis}
                      </p>
                    )}

                    <div className="text-[11px] text-gray-500">
                      Target Anchor: <span className="text-gray-300 font-mono">"{opp.anchor_text || "Accident Claims Guide"}"</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setExpandedDraftId(expandedDraftId === opp.id ? null : opp.id)}
                      className="py-1.5 px-3 bg-gray-900 hover:bg-gray-800 border border-gray-700 text-xs font-medium rounded-lg text-gray-300 transition"
                    >
                      {expandedDraftId === opp.id ? "Hide Email Draft" : "Preview Email Pitch"}
                    </button>
                    {opp.status !== "contacted" && (
                      <>
                        <button
                          onClick={() => handleApproveSend(opp.id)}
                          className="py-1.5 px-3.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition flex items-center gap-1 shadow-lg shadow-emerald-900/30"
                        >
                          <Check className="w-3.5 h-3.5" /> Approve & Send
                        </button>
                        <button
                          onClick={() => handleReject(opp.id)}
                          className="p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition"
                          title="Reject lead"
                        >
                          <ThumbsDown className="w-4 h-4" />
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* Collapsible Email Draft Preview */}
                {expandedDraftId === opp.id && (
                  <div className="mt-4 pt-4 border-t border-gray-800/80 bg-gray-900/50 p-4 rounded-lg font-mono text-xs text-gray-300 whitespace-pre-wrap leading-relaxed border border-gray-800">
                    <div className="text-[11px] text-blue-400 font-semibold mb-2 flex items-center gap-1.5">
                      <Mail className="w-3.5 h-3.5" /> Personalized AI Outreach Draft:
                    </div>
                    {opp.email_draft || "No draft available."}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
