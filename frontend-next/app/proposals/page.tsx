"use client";

import { useEffect, useState } from "react";
import { get, post } from "@/lib/api";
import { ApprovalCard } from "@/components/ApprovalCard";
import { getCurrentWebsiteId } from "@/lib/website";

interface Proposal {
  id: string;
  title: string;
  content: string;
  status: string;
}

export default function ProposalsPage() {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [activeTab, setActiveTab] = useState("all");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchProposals() {
      try {
        setLoading(true);
        const websiteId = getCurrentWebsiteId();
        const data = await get(`/proposals/${websiteId}`);
        const proposalsList = data?.proposals || data || [];
        setProposals(Array.isArray(proposalsList) ? proposalsList : []);
        setError(null);
      } catch (err) {
        setError("Backend not running");
        setProposals([]);
      } finally {
        setLoading(false);
      }
    }

    fetchProposals();
  }, []);

  const handleApprove = async (id: string, confirmHomepage: boolean = false) => {
    try {
      const body: any = {};
      if (confirmHomepage) {
        body.confirm_homepage = true;
      }
      await post(`/proposals/approve/${id}`, body);
      setProposals((prev) => prev.map((p) => (p.id === id ? { ...p, status: "approved" } : p)));
    } catch (e) {
      alert("Approve failed: " + (e as any).message);
    }
  };

  const handleReject = async (id: string) => {
    const reason = prompt("Rejection reason:");
    if (!reason) return;
    try {
      await post(`/proposals/reject/${id}`, { reason });
      setProposals((prev) => prev.map((p) => (p.id === id ? { ...p, status: "rejected" } : p)));
    } catch (e) {
      alert("Reject failed: " + (e as any).message);
    }
  };

  const tabs = [
    { id: "all", label: "ALL" },
    { id: "pending", label: "PENDING" },
    { id: "approved", label: "APPROVED" },
    { id: "rejected", label: "REJECTED" },
  ];

  const filteredProposals = proposals.filter((p) => {
    if (activeTab === "all") return true;
    return p.status === activeTab;
  });

  return (
    <div className="space-y-6">
      <div className="border-b border-ink">
        <div className="flex gap-0">
          {tabs.map((tab, i) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-[11px] uppercase tracking-widest mono-font border border-transparent ${
                activeTab === tab.id ? "bg-ink text-paper border-ink" : "border-ink hover:bg-stone"
              } ${i > 0 ? "border-l-0" : ""}`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="space-y-4">
          <div className="bg-stone border border-ink p-8 text-center">
            <div className="flex items-center justify-center py-4">
              <div className="w-4 h-4 border-2 border-ink border-t-transparent rounded-full animate-spin" />
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="space-y-4">
          <div className="bg-stone border border-ink p-8 text-center">
            <div className="text-[11px] text-ink mono-font">{error}</div>
          </div>
        </div>
      )}

      {!loading && !error && (
        <div className="space-y-4">
          {filteredProposals.length > 0 ? (
            filteredProposals.map((p) => (
              <ApprovalCard
                key={p.id}
                id={p.id}
                title={p.title}
                content={p.content}
                status={p.status}
                onApprove={(confirmHomepage) => handleApprove(p.id, confirmHomepage)}
                onReject={() => handleReject(p.id)}
              />
            ))
          ) : (
            <div className="bg-stone border border-[D1CCC4] border-dashed p-8 text-center text-muted mono-font">
              NO {activeTab.toUpperCase()} PROPOSALS
            </div>
          )}
        </div>
      )}
    </div>
  );
}
