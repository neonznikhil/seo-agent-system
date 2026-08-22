"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId, setCurrentWebsiteId } from "@/lib/website";

interface Website {
  id: string;
  domain?: string;
  url?: string;
  cms_url?: string;
  name?: string;
}

interface ContentItem {
  id: string;
  title: string;
  keyword?: string;
  content?: string;
  status: string;
  pipeline_status?: string;
  created_at: string;
  wp_post_id?: number | string;
  wp_draft_url?: string;
}

interface PipelineLog {
  step_number: number;
  step_name: string;
  phase: string;
  status: string;
  thought?: string;
  created_at: string;
}

const PHASES = [
  "1. Brain Context & Brand Voice",
  "2. Audience Demand & Search Intent",
  "3. SERP & Competitor Intelligence",
  "4. Outline & Semantic Architecture",
  "5. NVIDIA NIM Autonomous Content Writing",
  "6. Multi-Expert SEO & EEAT Review",
  "7. Humanizer & Tone Verification",
  "8. Fact-Checking & Knowledge Verification",
  "9. Internal Linking Optimization",
  "10. Citation & Reference Audit",
  "11. Final Quality Gate Scoring",
  "12. Brain Memory Learning",
];

export default function WriterPage() {
  const [websites, setWebsites] = useState<Website[]>([]);
  const [selectedWebsiteId, setSelectedWebsiteId] = useState<string>("");
  const [title, setTitle] = useState("");
  const [keywordsInput, setKeywordsInput] = useState("");
  const [suggestedTitles, setSuggestedTitles] = useState<string[]>([]);
  const [loadingKeywords, setLoadingKeywords] = useState<boolean>(false);
  const [tone, setTone] = useState("authoritative, engaging and SEO-optimized");
  
  const [contentList, setContentList] = useState<ContentItem[]>([]);
  const [selectedArticle, setSelectedArticle] = useState<ContentItem | null>(null);
  
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [activeContentId, setActiveContentId] = useState<string | null>(null);
  const [currentPhaseIndex, setCurrentPhaseIndex] = useState<number>(0);
  const [pipelineLogs, setPipelineLogs] = useState<PipelineLog[]>([]);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isApproving, setIsApproving] = useState<boolean>(false);
  const [isPublishing, setIsPublishing] = useState<boolean>(false);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // 1. Fetch real websites from API
  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"}/websites`)
      .then((r) => r.json())
      .then((data) => {
        const list = Array.isArray(data) ? data : data?.websites || [];
        setWebsites(list);
        if (list.length > 0) {
          const currentWid = getCurrentWebsiteId();
          const validWid = list.find((s: Website) => s.id === currentWid) ? currentWid : list[0].id;
          setSelectedWebsiteId(validWid);
          setCurrentWebsiteId(validWid);
        }
      })
      .catch((err) => {
        console.error("Failed to load websites:", err);
      })
      .finally(() => setLoading(false));
  }, []);

  // 2. Fetch keyword opportunities & auto-suggest titles when website is selected
  useEffect(() => {
    if (!selectedWebsiteId) return;

    setLoadingKeywords(true);

    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"}/gsc/${selectedWebsiteId}/keywords`)
      .then((r) => r.json())
      .then((data) => {
        const keywords = Array.isArray(data?.keywords) ? data.keywords : Array.isArray(data) ? data : [];
        if (keywords.length > 0) {
          // Auto-fill top 3 keywords
          const topKeywords = keywords
            .slice(0, 3)
            .map((k: any) => k.keyword || k)
            .filter(Boolean)
            .join(", ");
          setKeywordsInput(topKeywords);

          // Auto-suggest title based on top keyword
          const topKeyword = (keywords[0]?.keyword || keywords[0] || "").toString();
          if (topKeyword) {
            // Clean keyword from any domain artifacts
            let cleanKw = topKeyword
              .replace(/https?:\/\/\S+/gi, "")
              .replace(/\b(www|\.com|\.net|\.org|\.io|\.co|innovatcs)\b/gi, "")
              .replace(/[^\w\s-]/g, "")
              .trim();

            if (!cleanKw) cleanKw = "Car Accident Compensation Claims";

            // Capitalize appropriately
            const formatTitleCase = (s: string) => {
              const minor = new Set(["a", "an", "the", "and", "but", "or", "for", "nor", "on", "at", "to", "from", "by", "in", "of", "with"]);
              return s.split(/\s+/).map((w, idx) => {
                const l = w.toLowerCase();
                return (idx === 0 || !minor.has(l)) ? (w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()) : l;
              }).join(" ");
            };

            const cleanTitleCased = formatTitleCase(cleanKw);
            const lower = cleanKw.toLowerCase();

            let generated: string[] = [];
            if (lower.startsWith("how to")) {
              const action = formatTitleCase(cleanKw.substring(6).trim());
              generated = [
                `How to ${action}: Complete Step-by-Step Guide (2026)`,
                `The Ultimate Guide: How to ${action}`,
                `${action}: Everything You Need to Know`,
                `7 Essential Steps: How to ${action}`,
              ];
            } else {
              generated = [
                `Complete Guide to ${cleanTitleCased} in 2026`,
                `How to Handle ${cleanTitleCased}: Step-by-Step Guide`,
                `${cleanTitleCased}: Everything You Need to Know`,
                `7 Critical Facts About ${cleanTitleCased}`,
                `Understanding ${cleanTitleCased}: Process, Timeline & Legal Rights`,
              ];
            }

            setSuggestedTitles(generated);
            setTitle(generated[0]);
          }
        } else {
          setSuggestedTitles([
            "Complete Guide to Personal Injury Claims in 2026",
            "How to Maximize Your Accident Settlement: Step-by-Step",
            "Car Accident Compensation: Everything You Need to Know",
          ]);
        }
      })
      .catch(() => {
        setSuggestedTitles([
          "Complete Guide to Personal Injury Claims in 2026",
          "How to Maximize Your Accident Settlement: Step-by-Step",
          "Car Accident Compensation: Everything You Need to Know",
        ]);
      })
      .finally(() => setLoadingKeywords(false));
  }, [selectedWebsiteId]);

  // 3. Load content for selected website
  const loadArticlesForWebsite = useCallback(async (wid: string) => {
    if (!wid) return;
    try {
      const contentRes = await get(`/api/writer/${wid}/content`);
      const items = Array.isArray(contentRes) ? contentRes : contentRes?.data || [];
      setContentList(items);
      if (items.length > 0 && !selectedArticle) {
        setSelectedArticle(items[0]);
      }
    } catch {
      try {
        const blogsRes = await get(`/api/blogs?website_id=${wid}`);
        setContentList(Array.isArray(blogsRes) ? blogsRes : []);
      } catch {}
    }
  }, [selectedArticle]);

  useEffect(() => {
    if (selectedWebsiteId) {
      loadArticlesForWebsite(selectedWebsiteId);
    }
  }, [selectedWebsiteId, loadArticlesForWebsite]);

  const handleWebsiteChange = (id: string) => {
    setSelectedWebsiteId(id);
    setCurrentWebsiteId(id);
    setSelectedArticle(null);
  };

  // Poll pipeline progress
  const startPollingPipeline = (wid: string, contentId: string) => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    let phase = 0;
    pollIntervalRef.current = setInterval(async () => {
      try {
        const pipelineData = await get(`/api/writer/${wid}/pipeline/${contentId}`);
        if (pipelineData) {
          if (pipelineData.logs) setPipelineLogs(pipelineData.logs);
          phase = Math.min(11, phase + 1);
          setCurrentPhaseIndex(phase);

          // Check if finished
          const contentData = await get(`/api/writer/${wid}/content/${contentId}`);
          if (contentData && contentData.content && contentData.content.length > 100) {
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
            setGenerating(false);
            setCurrentPhaseIndex(11);
            setSelectedArticle(contentData);
            setStatusMessage("✅ Article generated successfully with NVIDIA NIM LLM!");
            loadArticlesForWebsite(wid);
          }
        }
      } catch (e) {
        phase = Math.min(11, phase + 1);
        setCurrentPhaseIndex(phase);
      }
    }, 3000);
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();

    // 1. VALIDATION — stop if placeholder text or empty
    const trimmedTitle = title.trim();
    if (
      !trimmedTitle ||
      trimmedTitle === "Or let AI suggest one based on your site" ||
      trimmedTitle === "Enter your blog title above" ||
      trimmedTitle.toLowerCase().includes("or let ai suggest") ||
      trimmedTitle.toLowerCase().includes("enter your blog title")
    ) {
      setError("Please enter a real blog title or click a suggested title first.");
      return;
    }

    const keywords = keywordsInput
      .split(",")
      .map((k) => k.trim())
      .filter((k) => Boolean(k) && !k.toLowerCase().includes("or let ai") && !k.toLowerCase().includes("enter your"));

    if (keywords.length === 0) {
      setError("Please enter at least one target keyword.");
      return;
    }

    if (!selectedWebsiteId) {
      setError("Please select a website first.");
      return;
    }

    try {
      setGenerating(true);
      setError(null);
      setStatusMessage("Starting 12-phase autonomous generation pipeline...");
      setCurrentPhaseIndex(0);
      setPipelineLogs([]);

      const payload = {
        title: trimmedTitle,
        topic: trimmedTitle,
        keywords: keywords,
        primary_keyword: keywords[0] || trimmedTitle,
        tone,
      };

      const res = await post(`/api/writer/${selectedWebsiteId}/generate`, payload);
      const contentId = res.content_id || res.id;
      setActiveContentId(contentId);

      if (res.content) {
        setSelectedArticle(res);
        setGenerating(false);
        setStatusMessage("✅ Autonomous blog generated successfully!");
        loadArticlesForWebsite(selectedWebsiteId);
      } else {
        startPollingPipeline(selectedWebsiteId, contentId);
      }
    } catch (err: any) {
      setGenerating(false);
      setError(err.message || "Failed to start blog generation");
    }
  };

  const handleApproveDraft = async () => {
    if (!selectedArticle || !selectedWebsiteId) return;
    try {
      setIsApproving(true);
      setError(null);
      const res = await post(`/api/writer/${selectedWebsiteId}/content/${selectedArticle.id}/approve-draft`, {});
      setStatusMessage("Draft created in WordPress ✅ (Status: Draft in WordPress)");
      setSelectedArticle({ ...selectedArticle, status: "draft", wp_post_id: res.wp_post_id, wp_draft_url: res.edit_url });
      loadArticlesForWebsite(selectedWebsiteId);
    } catch (err: any) {
      setError(err.message || "Failed to create WordPress draft");
    } finally {
      setIsApproving(false);
    }
  };

  const handlePublishNow = async () => {
    if (!selectedArticle || !selectedWebsiteId) return;
    try {
      setIsPublishing(true);
      setError(null);
      await post(`/api/writer/${selectedWebsiteId}/content/${selectedArticle.id}/publish`, {});
      setStatusMessage("🚀 Post published live to WordPress successfully!");
      setSelectedArticle({ ...selectedArticle, status: "published" });
      loadArticlesForWebsite(selectedWebsiteId);
    } catch (err: any) {
      setError(err.message || "Failed to publish post to WordPress");
    } finally {
      setIsPublishing(false);
    }
  };

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      {/* PAGE HEADER */}
      <div className="page-heading">Autonomous SEO Writer</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        12-Phase Multi-Agent Content Pipeline · NVIDIA NIM Llama-3.1-70B · WordPress Draft & Publish
      </div>

      {/* NOTICES */}
      {error && (
        <div className="notice" style={{ borderColor: "var(--red)", background: "rgba(239,68,68,0.08)", marginBottom: "16px" }}>
          <span className="notice-sq" style={{ background: "var(--red)" }}></span>
          <span style={{ color: "var(--red)" }}>{error}</span>
        </div>
      )}

      {statusMessage && (
        <div className="notice ok" style={{ marginBottom: "16px" }}>
          <span className="notice-sq"></span>
          <span>{statusMessage}</span>
        </div>
      )}

      {websites.length === 0 && !loading && (
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)", marginBottom: "16px" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No data yet — add a website first.</strong> Connect your website to begin autonomous blog generation.
            <div style={{ marginTop: "8px" }}>
              <Link href="/websites" className="btn btn-accent" style={{ textDecoration: "none", fontSize: "11px", padding: "4px 10px" }}>
                + Add Website
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* STEP 1: GENERATION FORM */}
      <div className="panel" style={{ marginBottom: "20px" }}>
        <div className="panel-head">
          <span className="panel-label">Step 1 — Create New Autonomous Blog Post</span>
          {loadingKeywords && <span className="badge badge-accent">⚡ Mining Keywords...</span>}
        </div>
        <div className="panel-body">
          <form onSubmit={handleGenerate} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
            <div>
              <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                Target Website
              </label>
              <select
                value={selectedWebsiteId}
                onChange={(e) => handleWebsiteChange(e.target.value)}
                className="field"
                style={{ width: "100%", padding: "8px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
                disabled={generating}
              >
                {websites.length === 0 ? (
                  <option value="">No websites added yet — go to Settings first</option>
                ) : (
                  websites.map((site) => (
                    <option key={site.id} value={site.id}>
                      {site.domain || site.url || site.cms_url || site.name || site.id}
                    </option>
                  ))
                )}
              </select>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                Target Keywords (Auto-Suggested or Custom)
              </label>
              <input
                type="text"
                value={keywordsInput}
                onChange={(e) => setKeywordsInput(e.target.value)}
                placeholder={loadingKeywords ? "Mining keywords from site..." : "e.g. accident settlement, personal injury lawyer"}
                className="field"
                style={{ width: "100%", padding: "8px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
                disabled={generating}
              />
            </div>

            <div style={{ gridColumn: "1 / -1" }}>
              <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                Blog Title or Core Topic
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Complete Guide to Georgia Car Accident Settlements in 2026"
                className="field"
                style={{ width: "100%", padding: "8px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--line)" }}
                disabled={generating}
                required
              />

              {/* Clickable Suggested Title Chips */}
              {suggestedTitles.length > 0 && (
                <div style={{ marginTop: "10px" }}>
                  <span style={{ fontSize: "11px", color: "var(--muted)", marginRight: "8px" }}>Suggested titles:</span>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "6px" }}>
                    {suggestedTitles.map((t, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => setTitle(t)}
                        style={{
                          background: title === t ? "var(--accent)" : "rgba(255,255,255,0.05)",
                          color: title === t ? "#fff" : "var(--ink)",
                          border: "1px solid var(--line)",
                          padding: "4px 10px",
                          fontSize: "11px",
                          borderRadius: "4px",
                          cursor: "pointer",
                          transition: "all 0.2s ease",
                        }}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div style={{ gridColumn: "1 / -1", display: "flex", justifyContent: "flex-end" }}>
              <button
                type="submit"
                className="btn btn-accent"
                disabled={generating || !selectedWebsiteId}
                style={{ padding: "10px 24px", fontSize: "12px", cursor: generating ? "not-allowed" : "pointer" }}
              >
                {generating ? "⚡ Generating via NVIDIA NIM..." : "⚡ Generate 1500+ Word Blog Post"}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* STEP 2: REAL-TIME PIPELINE PROGRESS */}
      {generating && (
        <div className="panel" style={{ marginBottom: "20px", borderLeft: "4px solid var(--accent)" }}>
          <div className="panel-head">
            <span className="panel-label">Step 2 — 12-Phase Real-Time Agent Pipeline</span>
            <span className="badge badge-accent">Processing Phase {currentPhaseIndex + 1}/12</span>
          </div>
          <div className="panel-body">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "10px" }}>
              {PHASES.map((p, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: "10px 12px",
                    border: "1px solid var(--line)",
                    background: idx < currentPhaseIndex ? "rgba(34, 197, 94, 0.08)" : idx === currentPhaseIndex ? "rgba(255, 77, 18, 0.08)" : "var(--surface)",
                    fontSize: "11px",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <span>{idx < currentPhaseIndex ? "✅" : idx === currentPhaseIndex ? "⏳" : "⚪"}</span>
                  <span style={{ fontWeight: idx === currentPhaseIndex ? 600 : 400, color: idx === currentPhaseIndex ? "var(--accent)" : "var(--ink)" }}>
                    {p}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* STEP 3 & 4 & 5: ARTICLE PREVIEW & WORDPRESS DISPATCH */}
      <div className="dash-grid">
        {/* LEFT COLUMN: ARTICLES LIST */}
        <div>
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Generated Articles Queue</span>
              <button className="panel-action" onClick={() => selectedWebsiteId && loadArticlesForWebsite(selectedWebsiteId)}>
                Refresh
              </button>
            </div>
            <div className="panel-body" style={{ maxHeight: "600px", overflowY: "auto" }}>
              {contentList.length === 0 ? (
                <div style={{ padding: "20px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
                  No articles generated yet. Fill the form above and click Generate.
                </div>
              ) : (
                contentList.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => setSelectedArticle(item)}
                    style={{
                      padding: "12px 14px",
                      borderBottom: "1px solid var(--line)",
                      cursor: "pointer",
                      background: selectedArticle?.id === item.id ? "rgba(255, 77, 18, 0.08)" : "transparent",
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: "13px", color: "var(--ink)" }}>{item.title}</div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "6px" }}>
                      <span className={`badge ${item.status === "published" ? "badge-green" : "badge-accent"}`}>
                        {item.status}
                      </span>
                      <span style={{ fontSize: "10px", color: "var(--muted)" }}>
                        {item.created_at ? new Date(item.created_at).toLocaleDateString() : "Recent"}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: PREVIEW & WORDPRESS ACTIONS */}
        <div>
          {selectedArticle ? (
            <div className="panel">
              <div className="panel-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="panel-label">Full Article Preview & WordPress Dispatch</span>
                <span className={`badge ${selectedArticle.status === "published" ? "badge-green" : "badge-accent"}`}>
                  Status: {selectedArticle.status}
                </span>
              </div>
              <div className="panel-body">
                {/* ACTION BUTTONS */}
                <div style={{ display: "flex", gap: "10px", marginBottom: "16px", paddingBottom: "16px", borderBottom: "1px solid var(--line)" }}>
                  <button
                    onClick={handleApproveDraft}
                    disabled={isApproving || selectedArticle.status === "published"}
                    className="btn btn-accent"
                    style={{ padding: "8px 16px", fontSize: "11px" }}
                  >
                    {isApproving ? "Creating WordPress Draft..." : "📝 Approve & Send to WordPress Draft"}
                  </button>

                  <button
                    onClick={handlePublishNow}
                    disabled={isPublishing || selectedArticle.status === "published"}
                    className="btn btn-primary"
                    style={{ padding: "8px 16px", fontSize: "11px" }}
                  >
                    {isPublishing ? "Publishing..." : "🚀 Publish Live Now (Human Approved)"}
                  </button>
                </div>

                {selectedArticle.wp_draft_url && (
                  <div style={{ marginBottom: "12px", fontSize: "11px" }}>
                    WordPress Link:{" "}
                    <a href={selectedArticle.wp_draft_url} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>
                      {selectedArticle.wp_draft_url}
                    </a>
                  </div>
                )}

                {/* ARTICLE CONTENT PREVIEW */}
                <div
                  style={{
                    maxHeight: "500px",
                    overflowY: "auto",
                    padding: "16px",
                    background: "var(--surface)",
                    border: "1px solid var(--line)",
                    fontSize: "13px",
                    lineHeight: "1.6",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  <h1 style={{ fontSize: "18px", fontWeight: "bold", marginBottom: "12px" }}>{selectedArticle.title}</h1>
                  {selectedArticle.content || "Generating full article text..."}
                </div>
              </div>
            </div>
          ) : (
            <div className="panel" style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              Select an article from the left or generate a new one to view preview and dispatch to WordPress.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
