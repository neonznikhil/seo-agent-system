"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

export default function LlmsTxtPage() {
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [noticeMsg, setNoticeMsg] = useState<string | null>(null);
  const [websiteId, setWebsiteId] = useState<string>("");

  const fetchLlmsTxtData = useCallback(async () => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);
    if (!wid) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = await get(`/api/llms-txt/${wid}`);
      if (data && data.content) {
        setContent(data.content);
      } else {
        setContent(null);
      }
    } catch (err: any) {
      console.warn("LLMs.txt fetch error:", err);
      setError(err.message || "Failed to load LLMs.txt");
      setContent(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLlmsTxtData();
    const handleChanged = () => fetchLlmsTxtData();
    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [fetchLlmsTxtData]);

  const handleGenerate = async () => {
    if (!websiteId) return;
    try {
      setGenerating(true);
      setError(null);
      const res = await post(`/api/llms-txt/generate?website_id=${websiteId}`, {});
      if (res && res.content) {
        setContent(res.content);
        setNoticeMsg("✓ Generated latest LLMs.txt for AI Search & AEO!");
      }
    } catch (err: any) {
      setError(err.message || "Failed to generate LLMs.txt");
    } finally {
      setGenerating(false);
    }
  };

  if (loading && !content) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px auto" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Loading LLMs.txt & AI Search Optimization manifest...
        </p>
      </div>
    );
  }

  if (!websiteId) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">LLMs.txt Manifest</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No data yet — add a website first.</strong> Connect your website to compile LLMs.txt structured files for Perplexity, ChatGPT, and Gemini Search engines.
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

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      <div className="page-heading">LLMs.txt Manifest</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        AEO & GEO Optimization · AI Search Crawler Protocols · Markdown Knowledge Spec
      </div>

      {error && (
        <div className="notice" style={{ borderColor: "var(--red)", background: "rgba(239,68,68,0.08)", marginBottom: "16px" }}>
          <span className="notice-sq" style={{ background: "var(--red)" }}></span>
          <span style={{ color: "var(--red)" }}>{error}</span>
        </div>
      )}

      {noticeMsg && (
        <div className="notice ok" style={{ marginBottom: "16px" }}>
          <span className="notice-sq"></span>
          <span>{noticeMsg}</span>
        </div>
      )}

      <div className="panel">
        <div className="panel-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span className="panel-label">Live /llms.txt File</span>
          <button onClick={handleGenerate} disabled={generating} className="btn btn-accent" style={{ padding: "6px 14px", fontSize: "11px" }}>
            {generating ? "Compiling..." : "⚡ Generate /llms.txt"}
          </button>
        </div>
        <div className="panel-body">
          {content ? (
            <pre
              style={{
                background: "var(--surface)",
                padding: "16px",
                border: "1px solid var(--line)",
                fontSize: "12px",
                lineHeight: "1.5",
                maxHeight: "500px",
                overflowY: "auto",
                whiteSpace: "pre-wrap",
              }}
            >
              {content}
            </pre>
          ) : (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              No LLMs.txt manifest generated yet for this site. Click "Generate /llms.txt" above to compile it.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}