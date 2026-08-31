"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

export default function LlmsTxtPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [deploying, setDeploying] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [websiteId, setWebsiteId] = useState<string>("");

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 4500);
  };

  const fetchLlmsTxt = useCallback(async (wid: string) => {
    if (!wid) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const json = await get(`/api/llms-txt/${wid}/generate`);
      setData(json);
    } catch (err: any) {
      setError(err.message || "Failed to load LLMs.txt");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const init = async () => {
      let wid = getCurrentWebsiteId();
      if (!wid) {
        try {
          const sites = await get("/api/websites");
          const list = Array.isArray(sites) ? sites : sites?.websites || [];
          if (list.length > 0 && list[0]?.id) {
            wid = list[0].id;
            localStorage.setItem("current-website-id", wid);
          }
        } catch {}
      }
      setWebsiteId(wid || "");
      if (wid) {
        fetchLlmsTxt(wid);
      } else {
        setLoading(false);
      }
    };
    init();

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
      const json = await get(`/api/llms-txt/${websiteId}/generate`);
      setData(json);
      showToast("LLMs.txt regenerated from published articles.");
    } catch (err: any) {
      setError(err.message || "Failed to generate LLMs.txt");
    } finally {
      setGenerating(false);
    }
  };

  // One-click deployment straight to WordPress
  const handleDeployToWordPress = async () => {
    if (!websiteId) return;
    try {
      setDeploying(true);
      const res = await post(`/api/llms-txt/${websiteId}/deploy-wordpress`, {});
      showToast(res.message || "Deployed to WordPress.");
    } catch (err: any) {
      showToast(`Deployment failed: ${err.message}`);
    } finally {
      setDeploying(false);
    }
  };

  if (!websiteId) {
    return (
      <div className="page-container active" style={{ padding: "30px" }}>
        <div className="page-heading">LLMs.txt Generator</div>
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)", marginTop: "16px" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No website selected.</strong> Select or add a website first to generate machine-readable
            guidelines for AI search models (ChatGPT, Perplexity, Claude).
            <div style={{ marginTop: "12px" }}>
              <Link href="/websites" className="btn btn-accent" style={{ textDecoration: "none", fontSize: "11px", padding: "6px 12px" }}>
                Go to Websites
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      {toastMsg && (
        <div style={{
          position: "fixed", bottom: "24px", left: "50%", transform: "translateX(-50%)",
          background: "var(--ink)", color: "var(--bg)", padding: "10px 22px", fontSize: "10.5px",
          textTransform: "uppercase", letterSpacing: ".07em", zIndex: 9999,
          fontFamily: "'IBM Plex Mono', monospace", border: "1px solid var(--accent)",
        }}>
          {toastMsg}
        </div>
      )}

      <div className="page-heading">LLMs.txt Generator</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Built exclusively from genuinely published articles · One-click WordPress deployment
      </div>

      <div style={{ marginBottom: "16px", display: "flex", gap: "10px", flexWrap: "wrap" }}>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="btn btn-accent"
          style={{ padding: "8px 18px", fontSize: "12px" }}
        >
          {generating ? "Generating..." : "Regenerate LLMs.txt"}
        </button>
        <button
          onClick={handleDeployToWordPress}
          disabled={deploying || !data?.content}
          className="btn btn-primary"
          style={{ padding: "8px 18px", fontSize: "12px" }}
        >
          {deploying ? "Deploying to WordPress..." : "🚀 Deploy to WordPress (one click)"}
        </button>
        {data?.article_count !== undefined && (
          <span className="badge badge-green" style={{ alignSelf: "center" }}>
            {data.article_count} published article(s) included
          </span>
        )}
      </div>

      {error && (
        <div className="notice" style={{ borderColor: error.includes("website") ? "var(--accent)" : "var(--red)", background: error.includes("website") ? "rgba(255, 77, 18, 0.08)" : "rgba(239,68,68,0.08)", marginBottom: "16px" }}>
          <span className="notice-sq" style={{ background: error.includes("website") ? "var(--accent)" : "var(--red)" }}></span>
          <div>
            <span>{error}</span>
            {error.toLowerCase().includes("website") && (
              <div style={{ marginTop: "8px" }}>
                <Link href="/websites" className="btn btn-accent" style={{ textDecoration: "none", fontSize: "11px", padding: "4px 10px" }}>
                  Go to Websites
                </Link>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Manifest Content (/llms.txt)</span>
          {data?.character_count && (
            <span style={{ fontSize: "9px", color: "var(--muted)" }}>{data.character_count} chars</span>
          )}
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
          ) : loading ? (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)" }}>Loading manifest...</div>
          ) : (
            <div style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              No LLMs.txt yet — only websites with genuinely published articles produce a manifest.
              Approve & publish an article first, then regenerate.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
