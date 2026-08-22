"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getCurrentWebsiteId } from "@/lib/website";

export default function LlmsTxtPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [websiteId, setWebsiteId] = useState<string>("");

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

  const fetchLlmsTxt = useCallback(async (wid: string) => {
    if (!wid) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const res = await fetch(`${apiUrl}/llms-txt/${wid}`);
      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}`);
      }
      const json = await res.json();
      setData(json);
    } catch (err: any) {
      setError(err.message || "Failed to load LLMs.txt");
    } finally {
      setLoading(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);
    if (wid) {
      fetchLlmsTxt(wid);
    } else {
      setLoading(false);
    }

    const handleChanged = () => {
      const newWid = getCurrentWebsiteId();
      setWebsiteId(newWid);
      if (newWid) fetchLlmsTxt(newWid);
    };

    window.addEventListener("website-changed", handleChanged);
    return () => window.removeEventListener("website-changed", handleChanged);
  }, [fetchLlmsTxt]);

  const handleGenerate = async () => {
    if (!websiteId) return;
    try {
      setGenerating(true);
      setError(null);
      const res = await fetch(`${apiUrl}/llms-txt/${websiteId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        throw new Error(`Generation failed with HTTP ${res.status}`);
      }
      const json = await res.json();
      setData(json);
    } catch (err: any) {
      setError(err.message || "Failed to generate LLMs.txt");
    } finally {
      setGenerating(false);
    }
  };

  if (!websiteId) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">LLMs.txt Generator</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)", marginTop: "16px" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No website selected.</strong> Please select or add a website in Settings first to generate machine-readable guidelines for AI search models (ChatGPT, Perplexity, Claude).
            <div style={{ marginTop: "12px" }}>
              <Link href="/settings" className="btn btn-accent" style={{ textDecoration: "none", fontSize: "11px", padding: "6px 12px" }}>
                Go to Settings
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (loading && !data) {
    return (
      <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ width: "32px", height: "32px", border: "3px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px auto" }} />
        <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase" }}>
          Loading LLMs.txt manifest...
        </p>
      </div>
    );
  }

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      <div className="page-heading">LLMs.txt Generator</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        AI Crawler Protocols · Machine-Readable Site Architecture · Perplexity & ChatGPT Optimization
      </div>

      <div style={{ marginBottom: "16px" }}>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="btn btn-accent"
          style={{ padding: "8px 18px", fontSize: "12px", cursor: "pointer" }}
        >
          {generating ? "Generating with AI..." : "⚡ Generate LLMs.txt"}
        </button>
      </div>

      {error && (
        <div className="notice" style={{ borderColor: "var(--red)", background: "rgba(239,68,68,0.08)", marginBottom: "16px" }}>
          <span className="notice-sq" style={{ background: "var(--red)" }}></span>
          <span style={{ color: "var(--red)" }}>Error: {error} — Make sure backend is running on port 8000</span>
        </div>
      )}

      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Manifest Content (/llms.txt)</span>
        </div>
        <div className="panel-body">
          {data?.content ? (
            <pre
              style={{
                background: "var(--surface)",
                color: "var(--ink)",
                padding: "16px",
                border: "1px solid var(--line)",
                fontSize: "12px",
                lineHeight: "1.6",
                overflowX: "auto",
                whiteSpace: "pre-wrap",
              }}
            >
              {data.content}
            </pre>
          ) : (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              No llms.txt generated yet. Click the button above to generate.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}