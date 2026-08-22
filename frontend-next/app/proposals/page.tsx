"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId, getWebsiteId } from "@/lib/website";

interface Proposal {
  id: string;
  title: string;
  content: string;
  status: string;
  created_at?: string;
}

export default function ProposalsPage() {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [activeTab, setActiveTab] = useState("all");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [websiteId, setWebsiteId] = useState<string>("");

  const fetchProposals = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);
    if (!wid) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = await get(`/api/proposals/${wid}`);
      const list = data?.proposals || (Array.isArray(data) ? data : []);
      setProposals(list);
    } catch (err: any) {
      console.warn("Proposals fetch error:", err);
      setError(err.message || "Failed to load proposals");
      setProposals([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProposals();
    const handleChanged = () => fetchProposals();
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [fetchProposals]);

  const handleApprove = async (proposalId: string) => {
    try {
      const activeWebsiteId = getWebsiteId() || websiteId;
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(
        `${apiUrl}/proposals/${activeWebsiteId}/approve/${proposalId}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-User-Id": "human-approved",
          },
        }
      );

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Approval failed");
      }

      const data = await res.json();
      alert("✅ Approved successfully!");
      fetchProposals();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    }
  };

  const handleReject = async (id: string) => {
    const reason = prompt("Rejection reason:");
    if (!reason) return;
    try {
      await post(`/api/proposals/reject/${id}`, { reason });
      setProposals((prev) => prev.map((p) => (p.id === id ? { ...p, status: "rejected" } : p)));
    } catch (e: any) {
      alert("Reject failed: " + e.message);
    }
  };

  if (loading && proposals.length === 0) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px auto" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Loading agent optimization proposals...
        </p>
      </div>
    );
  }

  if (!websiteId) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">Optimization Proposals</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No data yet — add a website first.</strong> Connect your website to receive autonomous SEO change proposals and approvals.
            <div style={{ marginTop: "10px" }}>
              <Link href="/websites" className="btn btn-accent" style={{ textDecoration: "none", fontSize: "11px", padding: "4px 10px" }}>
                + Add Website
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const filteredProposals = proposals.filter((p) => {
    if (activeTab === "all") return true;
    return p.status === activeTab;
  });

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      <div className="page-heading">Agent Change Proposals</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Human Approval Gate · Critical Action Reviews · Change Verification
        {error && (
          <span className="badge badge-amber" style={{ marginLeft: "12px" }}>
            {error}
          </span>
        )}
      </div>

      <div style={{ display: "flex", gap: "8px", margin: "16px 0" }}>
        {["all", "pending", "approved", "rejected"].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`btn ${activeTab === tab ? "btn-accent" : ""}`}
            style={{ textTransform: "capitalize", padding: "6px 14px", fontSize: "11px" }}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Proposed Actions ({filteredProposals.length})</span>
          <button className="panel-action" onClick={fetchProposals}>
            Refresh
          </button>
        </div>
        <div className="panel-body">
          {filteredProposals.length === 0 ? (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              No {activeTab} proposals found for this website.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {filteredProposals.map((p) => (
                <div key={p.id} style={{ padding: "14px", border: "1px solid var(--line)", background: "var(--surface)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                        <span className={`badge ${p.status === "approved" ? "badge-green" : p.status === "rejected" ? "badge-red" : "badge-accent"}`}>
                          {p.status.toUpperCase()}
                        </span>
                        <span style={{ fontWeight: 600, fontSize: "13px" }}>{p.title}</span>
                      </div>
                      <p style={{ fontSize: "12px", color: "var(--ink)", marginTop: "6px", lineHeight: "1.5" }}>{p.content}</p>
                    </div>
                    {p.status === "pending" && (
                      <div style={{ display: "flex", gap: "8px" }}>
                        <button onClick={() => handleApprove(p.id)} className="btn btn-accent" style={{ padding: "4px 10px", fontSize: "11px" }}>
                          Approve
                        </button>
                        <button onClick={() => handleReject(p.id)} className="btn" style={{ padding: "4px 10px", fontSize: "11px" }}>
                          Reject
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
