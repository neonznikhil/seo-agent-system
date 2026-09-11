"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface CannibalIssue {
  keyword: string;
  urls: Array<{ url: string; title: string; position: number | null }>;
  page_count: number;
  unmeasured_count: number;
  best_position: number | null;
  worst_position: number | null;
  action: string;
  recommendation: string;
  severity: "high" | "medium" | "low";
}

const ACTION_LABELS: Record<string, string> = {
  consolidate: "Merge + redirect weaker into stronger",
  differentiate: "Split intent / rewrite overlap",
  rewrite: "Rewrite to a distinct angle",
  merge: "Merge duplicate pages",
  redirect: "Redirect duplicate URL",
  internal_links: "Consolidate internal links to one canonical",
};

export default function CannibalizationPage() {
  const [websiteId, setWebsiteId] = useState<string>("");
  const [issues, setIssues] = useState<CannibalIssue[]>([]);
  const [sources, setSources] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [scanning, setScanning] = useState<boolean>(false);
  const [tasksCreated, setTasksCreated] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);
    if (!wid) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const res = await get(`/api/cannibalization/${wid}`);
      setIssues(res?.issues || []);
      setSources({ tracked: res?.sources?.tracked_rows, content: res?.sources?.content_rows });
    } catch (e: any) {
      setError(e.message || "Failed to load cannibalization data");
      setIssues([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    window.addEventListener("website-changed", load);
    return () => window.removeEventListener("website-changed", load);
  }, [load]);

  const handleScan = async () => {
    if (!websiteId) return;
    setScanning(true);
    setTasksCreated(null);
    try {
      const res = await post(`/api/cannibalization/${websiteId}/scan`, {});
      setIssues(res?.issues || []);
      setTasksCreated(res?.tasks_created ?? 0);
    } catch (e: any) {
      setError(e.message || "Scan failed");
    } finally {
      setScanning(false);
    }
  };

  if (loading) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Detecting competing pages…
        </p>
      </div>
    );
  }

  if (!websiteId) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">Cannibalization</div>
        <div className="page-sub">Select a website first — detection runs per site.</div>
      </div>
    );
  }

  return (
    <div className="page-container active">
      <div className="page-heading">Cannibalization</div>
      <div className="page-sub">
        Keywords targeted by 2+ pages. Each finding becomes a rewrite task — not just an alert.{" "}
        {sources && (
          <span style={{ color: "var(--muted)" }}>
            ({sources.tracked ?? 0} tracked rows · {sources.content ?? 0} content rows)
          </span>
        )}
      </div>

      {error && (
        <div className="panel" style={{ marginBottom: "16px", padding: "10px 14px", fontSize: "11px", borderColor: "var(--red)" }}>
          {error}
        </div>
      )}

      <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
        <button onClick={handleScan} disabled={scanning} className="btn btn-accent" style={{ fontSize: "11px", padding: "6px 14px" }}>
          {scanning ? "Scanning…" : "Scan & create fix tasks"}
        </button>
        <Link href="/decay" className="btn" style={{ fontSize: "11px", padding: "6px 14px", textDecoration: "none" }}>
          Content Decay →
        </Link>
      </div>

      {tasksCreated != null && (
        <div className="panel" style={{ marginBottom: "16px", padding: "10px 14px", fontSize: "11px", borderColor: "var(--green)" }}>
          {tasksCreated} fix task{tasksCreated === 1 ? "" : "s"} created in the approvals queue. Duplicates skipped.
        </div>
      )}

      {issues.length === 0 ? (
        <div className="panel" style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
          No cannibalization detected — no keyword is targeted by 2+ pages in tracked or content data.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {issues.map((issue, i) => (
            <div key={i} className="panel" style={{ borderLeft: `4px solid ${issue.severity === "high" ? "var(--red)" : "var(--amber)"}` }}>
              <div className="panel-head">
                <span className="panel-label">
                  “{issue.keyword}” — {issue.page_count} competing pages
                </span>
                <span className={`badge ${issue.severity === "high" ? "badge-red" : "badge-amber"}`} style={{ fontSize: "10px" }}>
                  {ACTION_LABELS[issue.action] || issue.action}
                </span>
              </div>
              <div className="panel-body" style={{ padding: "12px 16px", fontSize: "11px" }}>
                <div style={{ marginBottom: "8px", color: "var(--ink)", lineHeight: "1.5" }}>{issue.recommendation}</div>
                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  {issue.urls.map((u, j) => (
                    <div key={j} style={{ display: "flex", gap: "8px", color: "var(--muted)" }}>
                      <span style={{ fontWeight: 700, color: "var(--ink)" }}>
                        {u.position != null ? `#${u.position}` : "unmeasured"}
                      </span>
                      <span style={{ fontFamily: "monospace", fontSize: "10.5px" }}>{u.title || u.url || "(no URL)"}</span>
                    </div>
                  ))}
                </div>
                {issue.unmeasured_count > 0 && (
                  <div style={{ marginTop: "6px", fontSize: "10px", color: "var(--amber)" }}>
                    {issue.unmeasured_count} page(s) unmeasured — verify which ranks in GSC before merging.
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
