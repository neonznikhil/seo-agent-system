"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import Link from "next/link";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId, setCurrentWebsiteId } from "@/lib/website";
import { createSSE } from "@/lib/api";

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
  error_message?: string | null;
  created_at: string;
  wp_post_id?: number | string;
  wp_draft_url?: string;
}

// Live sections rendered progressively from the SSE stream
interface StreamSection {
  name: string;
  content: string;
}

const SECTION_ORDER = ["h1", "meta_description", "introduction", "faq", "conclusion"];

function sectionSortKey(name: string): number {
  const idx = SECTION_ORDER.indexOf(name);
  if (idx >= 0) return idx;
  if (name.startsWith("h2_")) return 2.5 + parseInt(name.split("_")[1] || "0", 10);
  return 99;
}

export default function WriterPage() {
  const [websites, setWebsites] = useState<Website[]>([]);
  const [selectedWebsiteId, setSelectedWebsiteId] = useState<string>("");
  const [title, setTitle] = useState("");
  const [keywordsInput, setKeywordsInput] = useState("");
  const [suggestedTitles, setSuggestedTitles] = useState<string[]>([]);
  const [loadingKeywords, setLoadingKeywords] = useState<boolean>(false);

  const [contentList, setContentList] = useState<ContentItem[]>([]);
  const [selectedArticle, setSelectedArticle] = useState<ContentItem | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [streamSections, setStreamSections] = useState<StreamSection[]>([]);
  const [streamPhase, setStreamPhase] = useState<string>("");
  const [streamError, setStreamError] = useState<string | null>(null);
  const [streamDone, setStreamDone] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sseRef = useRef<EventSource | null>(null);
  const previewBottomRef = useRef<HTMLDivElement | null>(null);

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      if (sseRef.current) sseRef.current.close();
    };
  }, []);

  // 1. Fetch real websites
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
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // 2. Keyword suggestions from GSC
  useEffect(() => {
    if (!selectedWebsiteId) return;

    setLoadingKeywords(true);
    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"}/gsc/${selectedWebsiteId}/keywords`)
      .then((r) => r.json())
      .then((data) => {
        const keywords = Array.isArray(data?.keywords) ? data.keywords : Array.isArray(data) ? data : [];
        if (keywords.length > 0) {
          const topKeywords = keywords
            .slice(0, 3)
            .map((k: any) => k.keyword || k)
            .filter(Boolean)
            .join(", ");
          setKeywordsInput(topKeywords);

          const topKeyword = (keywords[0]?.keyword || keywords[0] || "").toString();
          if (topKeyword) {
            let cleanKw = topKeyword
              .replace(/https?:\/\/\S+/gi, "")
              .replace(/\b(www|\.com|\.net|\.org|\.io|\.co)\b/gi, "")
              .replace(/[^\w\s-]/g, "")
              .trim();

            if (cleanKw && cleanKw.length > 3) {
              const formatTitleCase = (s: string) => {
                const minor = new Set(["a", "an", "the", "and", "but", "or", "for", "nor", "on", "at", "to", "from", "by", "in", "of", "with"]);
                return s.split(/\s+/).map((w, idx) => {
                  const l = w.toLowerCase();
                  return idx === 0 || !minor.has(l) ? w.charAt(0).toUpperCase() + w.slice(1).toLowerCase() : l;
                }).join(" ");
              };
              const cleanTitleCased = formatTitleCase(cleanKw);
              setSuggestedTitles([
                `Complete Guide to ${cleanTitleCased} in 2026`,
                `${cleanTitleCased}: Everything You Need to Know`,
                `Understanding ${cleanTitleCased}: Process, Timeline & Options`,
              ]);
              setTitle(`Complete Guide to ${cleanTitleCased} in 2026`);
            }
          }
        }
      })
      .catch(() => {})
      .finally(() => setLoadingKeywords(false));
  }, [selectedWebsiteId]);

  // 3. Load articles for website
  const loadArticlesForWebsite = useCallback(async (wid: string) => {
    if (!wid) return;
    try {
      const contentRes = await get(`/api/writer/${wid}/content`);
      const items = Array.isArray(contentRes) ? contentRes : contentRes?.data || [];
      setContentList(items);
      if (items.length > 0) {
        setSelectedArticle((prev) => prev ?? items[0]);
      }
    } catch {
      try {
        const blogsRes = await get(`/api/blogs?website_id=${wid}`);
        setContentList(Array.isArray(blogsRes) ? blogsRes : []);
      } catch {}
    }
  }, []);

  useEffect(() => {
    if (selectedWebsiteId) loadArticlesForWebsite(selectedWebsiteId);
  }, [selectedWebsiteId, loadArticlesForWebsite]);

  const handleWebsiteChange = (id: string) => {
    setSelectedWebsiteId(id);
    setCurrentWebsiteId(id);
    setSelectedArticle(null);
  };

  // 4. SSE streaming for a generation job
  const startStreaming = (jobId: string, wid: string) => {
    if (sseRef.current) sseRef.current.close();
    setActiveJobId(jobId);
    setStreamSections([]);
    setStreamError(null);
    setStreamDone(false);
    setStreamPhase("Connecting to generation stream...");

    const source = createSSE(`/api/writer/job/${jobId}/stream`, () => {});
    if (!source) {
      setStreamError("Could not establish live stream connection.");
      return;
    }
    sseRef.current = source;

    source.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        switch (data.event) {
          case "phase_started":
          case "phase_completed":
            setStreamPhase(data.phase || "");
            break;
          case "section":
            setStreamSections((prev) => {
              const next = [
                ...prev.filter((s) => s.name !== data.section),
                { name: data.section, content: data.content },
              ];
              return next.sort((a, b) => sectionSortKey(a.name) - sectionSortKey(b.name));
            });
            break;
          case "pipeline_completed":
            setStreamDone(true);
            setGenerating(false);
            setStatusMessage(`✅ "${data.title}" generated (${data.word_count} words, SEO ${data.seo_score}) and queued for your approval.`);
            loadArticlesForWebsite(wid);
            source.close();
            break;
          case "pipeline_failed":
          case "pipeline_blocked":
            setStreamError(
              data.error
                ? `Generation failed: ${data.error}`
                : `Pipeline blocked at phase '${data.phase}'${data.reason ? ` — ${data.reason}` : ""}.`
            );
            setGenerating(false);
            source.close();
            break;
          default:
            break;
        }
      } catch {}
    };
    source.onerror = () => {
      // Stream ended; if we never got completion, surface it honestly
      setTimeout(() => {
        if (!streamDone) {
          // Check final state via REST before declaring an error
          fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"}/writer/${wid}/content/${jobId}`)
            .then((r) => (r.ok ? r.json() : null))
            .then((detail) => {
              if (detail && detail.content && detail.content.length > 100) {
                setStreamDone(true);
                setGenerating(false);
                setStatusMessage("✅ Article generated successfully!");
                loadArticlesForWebsite(wid);
              } else if (detail && detail.pipeline_status === "failed") {
                setStreamError(detail.error_message || "Generation failed on the backend.");
                setGenerating(false);
              }
            })
            .catch(() => {});
        }
      }, 2000);
      source.close();
    };
  };

  // Auto-scroll preview while streaming
  useEffect(() => {
    if (generating && previewBottomRef.current) {
      previewBottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [streamSections, generating]);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();

    const trimmedTitle = title.trim();
    const lowerTitle = trimmedTitle.toLowerCase();
    if (
      !trimmedTitle ||
      lowerTitle.includes("or let ai suggest") ||
      lowerTitle.includes("e.g.") ||
      trimmedTitle.length < 8
    ) {
      setError("Please enter a real blog title (click a suggestion or type one).");
      return;
    }

    const keywords = keywordsInput
      .split(",")
      .map((k) => k.trim())
      .filter((k) => Boolean(k));

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
      setStatusMessage("Generation started — article appears below as each section is written...");
      setStreamSections([]);

      const payload = {
        title: trimmedTitle,
        topic: trimmedTitle,
        keywords,
        primary_keyword: keywords[0],
      };

      const res = await post(`/api/writer/${selectedWebsiteId}/generate`, payload);
      const jobId = res.job_id || res.content_id;
      if (res.success === false) {
        throw new Error(res.message || "Failed to start");
      }
      startStreaming(jobId, selectedWebsiteId);
      loadArticlesForWebsite(selectedWebsiteId);
    } catch (err: any) {
      setGenerating(false);
      setError(err.message || "Failed to start blog generation");
    }
  };

  const renderSectionLabel = (name: string) => {
    if (name === "h1") return "H1 Headline";
    if (name === "meta_description") return "Meta Description";
    if (name === "introduction") return "Introduction";
    if (name === "faq") return "FAQ Block";
    if (name === "conclusion") return "Conclusion";
    if (name.startsWith("h2_")) return `Section ${name.split("_")[1]}`;
    return name;
  };

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      {/* PAGE HEADER */}
      <div className="page-heading">Autonomous SEO Writer</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        12-Phase Multi-Agent Pipeline · NVIDIA NIM Llama-3.1-70B · Live Streaming Output
      </div>

      {error && (
        <div className="notice" style={{ borderColor: "var(--red)", background: "rgba(239,68,68,0.08)", marginBottom: "16px" }}>
          <span className="notice-sq" style={{ background: "var(--red)" }}></span>
          <span style={{ color: "var(--red)" }}>{error}</span>
        </div>
      )}

      {statusMessage && !error && (
        <div className="notice ok" style={{ marginBottom: "16px" }}>
          <span className="notice-sq"></span>
          <span>{statusMessage}</span>
        </div>
      )}

      {websites.length === 0 && !loading && (
        <div className="notice" style={{ borderColor: "var(--accent)", background: "rgba(255, 77, 18, 0.08)", marginBottom: "16px" }}>
          <span className="notice-sq"></span>
          <div>
            <strong>No websites connected yet.</strong> Connect your website first — the system will then generate
            its first article automatically within the hour.
            <div style={{ marginTop: "8px" }}>
              <Link href="/websites" className="btn btn-accent" style={{ textDecoration: "none", fontSize: "11px", padding: "4px 10px" }}>
                + Add Website
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* MANUAL OVERRIDE GENERATOR */}
      <div className="panel" style={{ marginBottom: "20px" }}>
        <div className="panel-head">
          <span className="panel-label">Manual Override — Force Generate Now</span>
          {loadingKeywords && <span className="badge badge-accent">Mining Keywords...</span>}
        </div>
        <div className="panel-body">
          <p style={{ fontSize: "10px", color: "var(--muted)", marginBottom: "12px" }}>
            The system generates articles automatically every day at 11:00 IST from your top-priority keyword.
            This form is only for forcing an immediate generation.
          </p>
          <form onSubmit={handleGenerate} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
            <div>
              <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                Target Website
              </label>
              <select
                value={selectedWebsiteId}
                onChange={(e) => handleWebsiteChange(e.target.value)}
                className="field"
                style={{ width: "100%", padding: "8px" }}
                disabled={generating}
              >
                {websites.length === 0 ? (
                  <option value="">No websites added yet</option>
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
                Target Keywords
              </label>
              <input
                type="text"
                value={keywordsInput}
                onChange={(e) => setKeywordsInput(e.target.value)}
                placeholder={loadingKeywords ? "Mining keywords from GSC..." : "keyword one, keyword two"}
                className="field"
                style={{ width: "100%", padding: "8px" }}
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
                placeholder="Type a real article title"
                className="field"
                style={{ width: "100%", padding: "8px" }}
                disabled={generating}
                required
              />

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
                style={{ padding: "10px 24px", fontSize: "12px" }}
              >
                {generating ? "⚡ Generating & Streaming..." : "Manual Override — Force Generate Now"}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* LIVE STREAMING PANEL */}
      {(generating || streamSections.length > 0 || streamError) && (
        <div className="panel" style={{ marginBottom: "20px", borderLeft: generating ? "4px solid var(--accent)" : streamError ? "4px solid var(--red)" : "4px solid var(--green)" }}>
          <div className="panel-head">
            <span className="panel-label">Live Generation Stream</span>
            {generating ? (
              <span className="badge badge-accent">
                Writing{streamPhase ? ` — ${streamPhase.replace(/_/g, " ")}` : "..."}
              </span>
            ) : streamDone ? (
              <span className="badge badge-green">Completed</span>
            ) : streamError ? (
              <span className="badge badge-red">Failed</span>
            ) : null}
          </div>
          <div className="panel-body">
            {streamError && (
              <div style={{ color: "var(--red)", fontSize: "12px", marginBottom: "12px", padding: "10px", border: "1px solid var(--red)", background: "rgba(239,68,68,.06)" }}>
                {streamError}
              </div>
            )}
            <div
              style={{
                maxHeight: "520px",
                overflowY: "auto",
                padding: "16px",
                background: "var(--surface)",
                border: "1px solid var(--line)",
                fontSize: "13px",
                lineHeight: "1.7",
              }}
            >
              {streamSections.length === 0 && generating && !streamError && (
                <div style={{ color: "var(--muted)" }}>
                  Waiting for NVIDIA NIM to produce the first section... This typically takes under a minute.
                  If NIM is unavailable you will see the exact error here instead of a spinner.
                </div>
              )}
              {streamSections.map((section) => (
                <div key={section.name} style={{ marginBottom: "18px" }}>
                  <div style={{ fontSize: "9.5px", textTransform: "uppercase", letterSpacing: ".06em", color: "var(--accent)", marginBottom: "4px" }}>
                    {renderSectionLabel(section.name)} ✓
                  </div>
                  <div style={{ whiteSpace: "pre-wrap" }}>{section.content}</div>
                </div>
              ))}
              {generating && <div ref={previewBottomRef} style={{ height: "2px" }} />}
            </div>
          </div>
        </div>
      )}

      {/* ARTICLES LIST + PREVIEW */}
      <div className="dash-grid">
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
                  No articles yet. Articles appear here automatically after the daily 11:00 IST run — or force one above.
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
                    <div style={{ fontWeight: 600, fontSize: "13px", color: "var(--ink)" }}>
                      {item.title}
                      {item.pipeline_status === "failed" && (
                        <span className="badge badge-red" style={{ marginLeft: "8px" }}>failed</span>
                      )}
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "6px" }}>
                      <span className={`badge ${item.status === "published" ? "badge-green" : item.status === "failed" ? "badge-red" : "badge-accent"}`}>
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

        <div>
          {selectedArticle ? (
            <div className="panel">
              <div className="panel-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="panel-label">Full Article Preview</span>
                <span className={`badge ${selectedArticle.status === "published" ? "badge-green" : selectedArticle.status === "failed" ? "badge-red" : "badge-accent"}`}>
                  Status: {selectedArticle.status}
                </span>
              </div>
              <div className="panel-body">
                {selectedArticle.pipeline_status === "failed" && (
                  <div style={{ color: "var(--red)", fontSize: "12px", marginBottom: "12px", padding: "10px", border: "1px solid var(--red)" }}>
                    This generation failed: {selectedArticle.error_message || "unknown backend error"}
                  </div>
                )}
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
                  {selectedArticle.content || (
                    selectedArticle.pipeline_status === "in_progress" || selectedArticle.status === "in_progress" ? (
                      <span style={{ color: "var(--muted)" }}>
                        Still generating — click this row again in a minute, or watch the live stream panel above.
                      </span>
                    ) : (
                      <span style={{ color: "var(--red)" }}>
                        No article body stored for this row.
                        {selectedArticle.error_message ? ` Error: ${selectedArticle.error_message}` : ""}
                      </span>
                    )
                  )}
                </div>
                <ApproveControls article={selectedArticle} wid={selectedWebsiteId} onRefresh={() => loadArticlesForWebsite(selectedWebsiteId)} />
              </div>
            </div>
          ) : (
            <div className="panel" style={{ padding: "30px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              Select an article from the left to preview it here.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ApproveControls({ article, wid, onRefresh }: { article: ContentItem; wid: string; onRefresh: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  if (article.status === "published") {
    return <p style={{ fontSize: "11px", color: "var(--green)", marginTop: "12px" }}>✓ Published live on WordPress.</p>;
  }
  if (article.status === "failed") return null;

  const approve = async () => {
    setBusy("draft");
    setMsg(null);
    try {
      await post(`/api/writer/${wid}/content/${article.id}/approve-draft`, {});
      setMsg("Draft created in WordPress.");
      onRefresh();
    } catch (e: any) {
      setMsg(e.message || "Draft creation failed");
    } finally {
      setBusy(null);
    }
  };

  const publish = async () => {
    setBusy("publish");
    setMsg(null);
    try {
      await post(`/api/writer/${wid}/content/${article.id}/publish`, {});
      setMsg("Published live to WordPress.");
      onRefresh();
    } catch (e: any) {
      setMsg(e.message || "Publish failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div style={{ marginTop: "14px" }}>
      <div style={{ display: "flex", gap: "10px" }}>
        <button onClick={approve} disabled={!!busy} className="btn btn-accent" style={{ padding: "8px 16px", fontSize: "11px" }}>
          {busy === "draft" ? "Creating WordPress Draft..." : "📝 Send to WordPress Draft"}
        </button>
        <button onClick={publish} disabled={!!busy} className="btn btn-primary" style={{ padding: "8px 16px", fontSize: "11px" }}>
          {busy === "publish" ? "Publishing..." : "🚀 Publish Live Now"}
        </button>
      </div>
      {msg && <p style={{ fontSize: "11px", marginTop: "8px", color: msg.startsWith("Published") ? "var(--green)" : "var(--ink)" }}>{msg}</p>}
    </div>
  );
}
