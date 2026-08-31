"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { get, post, buildUrl } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface KnowledgeChunk {
  id: string;
  website_id?: string;
  source_type?: string;
  title?: string;
  content: string;
  url?: string;
  freshness_score?: number;
  credibility_score?: number;
  created_at?: string;
  similarity?: number;
}

export default function KnowledgePage() {
  const [websiteId, setWebsiteId] = useState<string>("");
  const [chunks, setChunks] = useState<KnowledgeChunk[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  // Filters & Search
  const [filterSource, setFilterSource] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [isCrawling, setIsCrawling] = useState<boolean>(false);
  const [crawlProgress, setCrawlProgress] = useState<string>("");

  // Upload Modal
  const [showUploadModal, setShowUploadModal] = useState<boolean>(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState<string>("");
  const [isUploading, setIsUploading] = useState<boolean>(false);

  // Ingest Text Form
  const [textTitle, setTextTitle] = useState("");
  const [textType, setTextType] = useState("business_info");
  const [textContent, setTextContent] = useState("");
  const [isIngesting, setIsIngesting] = useState(false);

  // Full-site crawl form (NEW: crawl ALL subpages, not just single page)
  const [crawlUrl, setCrawlUrl] = useState("");
  const [crawlMaxPages, setCrawlMaxPages] = useState<number>(50);
  const [crawlResult, setCrawlResult] = useState<any>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  const loadKnowledgeChunks = useCallback(async () => {
    const wid = getCurrentWebsiteId() || "default";
    setWebsiteId(wid);
    try {
      setLoading(true);
      const res = await get(`/api/knowledge?website_id=${wid}&limit=100`);
      const list = Array.isArray(res) ? res : res?.data || res?.chunks || [];
      setChunks(list);
    } catch {
      setChunks([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadKnowledgeChunks();
    const handleWChange = () => loadKnowledgeChunks();
    window.addEventListener("website-changed", handleWChange);
    return () => window.removeEventListener("website-changed", handleWChange);
  }, [loadKnowledgeChunks]);

  const handleReCrawl = async () => {
    const wid = getCurrentWebsiteId() || websiteId;
    if (!wid || wid === "default") {
      showToast("Please connect a website first (via Setup)");
      return;
    }
    try {
      setIsCrawling(true);
      setCrawlProgress("Full-site crawl: recursive sitemap + BFS discovering ALL subpages (up to 50 pages, depth 3) — this may take 60–90s...");
      setCrawlResult(null);
      // Preferred: synchronous full-site crawl that returns detailed stats
      let res: any = null;
      try {
        // Try new full-site crawl endpoint first
        res = await post(`/api/knowledge/crawl`, { website_id: wid, max_pages: crawlMaxPages, max_depth: 3 });
        if (res && res.success !== false) {
          setCrawlResult(res);
          setCrawlProgress(`✓ Crawled ${res.urls_scanned || 0} subpages (${res.new_pages_ingested || 0} new + ${res.updated_pages || 0} updated) → ${res.total_chunks_indexed || 0} chunks indexed (${res.sitemap_urls_found || 0} sitemap URLs, ${res.urls_discovered || 0} discovered)`);
          await loadKnowledgeChunks();
          setTimeout(() => { setIsCrawling(false); setCrawlProgress(""); }, 2500);
          showToast(`✓ Full-site crawl complete — ${res.urls_scanned || 0} subpages, ${res.total_chunks_indexed || 0} chunks!`);
          return;
        }
      } catch (e1: any) {
        console.warn("knowledge/crawl failed, trying watch-business", e1);
      }
      try {
        res = await post(`/api/knowledge/watch-business`, { website_id: wid, max_pages: crawlMaxPages });
        if (res && (res.urls_scanned || res.new_pages_ingested != null)) {
          setCrawlResult(res);
          setCrawlProgress(`Ingested ${res.new_pages_ingested || 0} new + ${res.updated_pages || 0} updated pages → ${res.total_chunks_indexed || 0} chunks (scanned ${res.urls_scanned || res.total_pages_crawled || 0} URLs via BFS + sitemap)`);
          await loadKnowledgeChunks();
          setTimeout(() => { setIsCrawling(false); setCrawlProgress(""); }, 2500);
          showToast(`✓ Deep crawl complete — ${res.urls_scanned || 0} subpages, ${res.total_chunks_indexed || 0} chunks!`);
          return;
        }
      } catch (watchErr: any) {
        console.warn("watch-business failed, falling back to sync websites/crawl", watchErr);
      }
      // Fallback: sync websites crawl (?sync=true) — also full-site BFS
      res = await post(`/api/websites/${wid}/crawl?sync=true&max_pages=${crawlMaxPages}`, { sync: true, max_pages: crawlMaxPages });
      setCrawlResult(res);
      setCrawlProgress(`✓ Crawled ${res.urls_scanned || 0} subpages → ${res.total_chunks_indexed || 0} chunks`);
      await loadKnowledgeChunks();
      setIsCrawling(false);
      setCrawlProgress("");
      showToast(`✓ Full-site crawl complete — ${res.urls_scanned || 0} subpages, ${res.total_chunks_indexed || 0} chunks!`);
    } catch (e: any) {
      setIsCrawling(false);
      setCrawlProgress("");
      showToast(`Crawl notice: ${e.message}`);
    }
  };

  const handleCrawlSite = async (e: React.FormEvent) => {
    e.preventDefault();
    const wid = getCurrentWebsiteId() || websiteId;
    let target = crawlUrl.trim();
    if (!target) {
      // fallback to connected website
      if (!wid || wid === "default") {
        showToast("Enter a website URL (e.g. https://example.com) or connect a site first");
        return;
      }
      // will crawl the connected site
      return handleReCrawl();
    }
    // normalize
    if (!target.startsWith("http")) target = "https://" + target;
    try {
      setIsCrawling(true);
      setCrawlResult(null);
      setCrawlProgress(`Crawling entire site ${target} — sitemap index recursion + BFS across all subpages (up to ${crawlMaxPages} pages)...`);
      const res = await post(`/api/knowledge/crawl`, { site_url: target, url: target, website_id: wid, max_pages: crawlMaxPages, max_depth: 3 });
      setCrawlResult(res);
      if (res.success === false) {
        setCrawlProgress(res.message || "Crawl failed — check URL and try again");
        showToast(res.message || "Crawl failed");
      } else {
        setCrawlProgress(`✓ Crawled ${res.urls_scanned || 0} subpages (${res.new_pages_ingested || 0} new, ${res.updated_pages || 0} updated, ${res.failed_pages || 0} failed) → ${res.total_chunks_indexed || 0} chunks from ${target}`);
        showToast(`✓ Full site crawled: ${res.urls_scanned || 0} pages, ${res.total_chunks_indexed || 0} chunks!`);
      }
      await loadKnowledgeChunks();
      setTimeout(() => { setIsCrawling(false); }, 3000);
    } catch (err: any) {
      setIsCrawling(false);
      setCrawlProgress("");
      showToast(`Crawl error: ${err.message}`);
    }
  };

  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) return;
    const wid = getCurrentWebsiteId() || websiteId;

    try {
      setIsUploading(true);
      const formData = new FormData();
      formData.append("file", uploadFile);
      if (uploadTitle) formData.append("title", uploadTitle);
      if (wid) formData.append("website_id", wid);

      const res = await fetch(buildUrl("/api/knowledge/upload"), {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        showToast("✓ Document parsed and embedded into knowledge base!");
        setShowUploadModal(false);
        setUploadFile(null);
        setUploadTitle("");
        loadKnowledgeChunks();
      } else {
        const errTxt = await res.text();
        showToast(`Upload error: ${errTxt}`);
      }
    } catch (err: any) {
      showToast(`Upload failed: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleIngestText = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!textContent.trim()) return;
    const wid = getCurrentWebsiteId() || websiteId;

    try {
      setIsIngesting(true);
      await post("/api/knowledge/upload", {
        website_id: wid,
        title: textTitle.trim() || "Business Fact",
        type: textType,
        text: textContent.trim(),
      });
      showToast("✓ Fact ingested into Living Knowledge Base!");
      setTextTitle("");
      setTextContent("");
      loadKnowledgeChunks();
    } catch (err: any) {
      showToast(`Ingestion notice: ${err.message}`);
    } finally {
      setIsIngesting(false);
    }
  };

  const sourcesList = useMemo(() => {
    const s = new Set<string>();
    chunks.forEach((c) => {
      if (c.url) s.add(c.url);
      else if (c.source_type) s.add(c.source_type);
    });
    return Array.from(s);
  }, [chunks]);

  const filteredChunks = useMemo(() => {
    return chunks.filter((c) => {
      const matchesSource = filterSource === "all" || c.url === filterSource || c.source_type === filterSource;
      const matchesQuery = !searchQuery.trim() ||
        (c.title || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
        (c.content || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
        (c.url || "").toLowerCase().includes(searchQuery.toLowerCase());
      return matchesSource && matchesQuery;
    });
  }, [chunks, filterSource, searchQuery]);

  const avgFreshness = useMemo(() => {
    if (chunks.length === 0) return 100;
    const sum = chunks.reduce((acc, c) => acc + (c.freshness_score ? Math.round(c.freshness_score * 100) : 95), 0);
    return Math.round(sum / chunks.length);
  }, [chunks]);

  return (
    <div className="page-container active">
      {toastMsg && (
        <div
          style={{
            position: "fixed",
            bottom: "24px",
            left: "50%",
            transform: "translateX(-50%)",
            background: "var(--ink)",
            color: "var(--bg)",
            padding: "10px 22px",
            fontSize: "11px",
            textTransform: "uppercase",
            letterSpacing: ".07em",
            zIndex: 9999,
            fontFamily: "'IBM Plex Mono', monospace",
            border: "1px solid var(--accent)",
            boxShadow: "0 4px 24px rgba(0,0,0,.4)",
          }}
        >
          {toastMsg}
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
        <div>
          <div className="page-heading">Living Knowledge Base</div>
          <div className="page-sub">
            <span className="sub-sq"></span>
            Multi-Source Fact Ingestion · pgvector Semantic Retrieval · Hallucination Defense
          </div>
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          <button
            onClick={handleReCrawl}
            disabled={isCrawling}
            className="btn btn-accent"
            style={{ padding: "8px 16px", fontSize: "11.5px" }}
          >
            {isCrawling ? "⚡ Crawling Sitemap..." : "⚡ RE-CRAWL SITEMAP"}
          </button>
          <button
            onClick={() => setShowUploadModal(true)}
            className="btn"
            style={{ padding: "8px 16px", fontSize: "11.5px", border: "1px solid var(--line)" }}
          >
            📂 UPLOAD DOCUMENT
          </button>
        </div>
      </div>

      {isCrawling && crawlProgress && (
        <div className="notice" style={{ marginBottom: "16px", borderColor: "var(--accent)", background: "rgba(255,77,18,0.08)" }}>
          <span className="notice-sq"></span>
          <span style={{ fontWeight: 600 }}>{crawlProgress}</span>
        </div>
      )}

      <div className="kpi-strip" style={{ marginBottom: "20px" }}>
        <div className="kpi-cell" style={{ borderLeft: "3px solid var(--accent)" }}>
          <div className="kpi-label">Total Knowledge Chunks</div>
          <div className="kpi-val" style={{ color: "var(--accent)" }}>{chunks.length}</div>
          <div className="kpi-delta">Indexed in pgvector (all subpages)</div>
        </div>
        <div className="kpi-cell" style={{ borderLeft: "3px solid var(--green)" }}>
          <div className="kpi-label">Average Freshness Score</div>
          <div className="kpi-val" style={{ color: "var(--green)" }}>{avgFreshness}%</div>
          <div className="kpi-delta">Active temporal weight</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Indexed Sources (subpages)</div>
          <div className="kpi-val">{sourcesList.length || 1}</div>
          <div className="kpi-delta">Unique subpages indexed</div>
        </div>
      </div>

      {/* Full-Site Crawl Panel — crawls ALL subpages via sitemap + BFS, not just single page */}
      <div className="panel" style={{ marginBottom: "20px", borderColor: isCrawling ? "var(--accent)" : "var(--line)" }}>
        <div className="panel-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span className="panel-label">🌐 Crawl Entire Website — Build Knowledge Base From All Subpages</span>
          <span style={{ fontSize: "10px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: ".06em" }}>
            Recursive sitemap + BFS · not single-page scrape
          </span>
        </div>
        <div className="panel-body">
          <p style={{ fontSize: "11px", color: "var(--muted)", marginBottom: "12px", lineHeight: 1.5 }}>
            Enter your business website URL to crawl <b style={{ color: "var(--ink)" }}>all subpages</b> (sitemap.xml, wp-sitemap.xml, robots.txt sitemaps, plus BFS internal-link discovery up to depth 3).
            Each page is chunked into 3200-char sections, embedded (1536-dim NIM), and stored in pgvector — this powers grounded content generation.
            Previous behavior scraped only a single page; now it discovers <b>all</b> URLs via sitemap index recursion.
          </p>
          <form onSubmit={handleCrawlSite} style={{ display: "flex", gap: "10px", alignItems: "flex-end", flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: "240px" }}>
              <label style={{ display: "block", fontSize: "10px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                Website URL to crawl (leave empty to crawl connected site)
              </label>
              <input
                className="field"
                value={crawlUrl}
                onChange={(e) => setCrawlUrl(e.target.value)}
                placeholder="https://example.com  — will crawl all subpages"
                style={{ width: "100%", padding: "8px 12px", fontSize: "12px" }}
              />
            </div>
            <div style={{ minWidth: "120px" }}>
              <label style={{ display: "block", fontSize: "10px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                Max pages
              </label>
              <select
                className="field"
                value={crawlMaxPages}
                onChange={(e) => setCrawlMaxPages(parseInt(e.target.value) || 50)}
                style={{ width: "100%", padding: "8px 12px", fontSize: "12px" }}
              >
                <option value={15}>15 pages</option>
                <option value={25}>25 pages</option>
                <option value={50}>50 pages (default)</option>
                <option value={75}>75 pages</option>
                <option value={100}>100 pages</option>
              </select>
            </div>
            <button
              type="submit"
              className="btn btn-accent"
              disabled={isCrawling}
              style={{ padding: "10px 22px", fontSize: "11.5px", whiteSpace: "nowrap", height: "36px" }}
            >
              {isCrawling ? "⚡ Crawling All Pages..." : "🌐 CRAWL ALL SUBPAGES"}
            </button>
            <button
              type="button"
              onClick={handleReCrawl}
              disabled={isCrawling}
              className="btn"
              style={{ padding: "10px 16px", fontSize: "11.5px", border: "1px solid var(--line)", whiteSpace: "nowrap", height: "36px" }}
            >
              ↻ Re-crawl connected site
            </button>
          </form>
          {crawlResult && (
            <div style={{ marginTop: "14px", padding: "12px", background: "var(--bg)", border: "1px solid var(--line)", borderRadius: "4px", fontSize: "11px", lineHeight: 1.6 }}>
              <div style={{ fontWeight: 700, marginBottom: "6px", color: crawlResult.success === false ? "var(--red)" : "var(--green)" }}>
                {crawlResult.success === false ? "✗ Crawl failed" : `✓ Crawled ${crawlResult.urls_scanned ?? 0} subpages`}
                {crawlResult.site_checked ? ` — ${crawlResult.site_checked}` : ""}
              </div>
              <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", color: "var(--muted)" }}>
                <span>New: <b style={{ color: "var(--ink)" }}>{crawlResult.new_pages_ingested ?? 0}</b></span>
                <span>Updated: <b style={{ color: "var(--ink)" }}>{crawlResult.updated_pages ?? 0}</b></span>
                <span>Chunks: <b style={{ color: "var(--accent)" }}>{crawlResult.total_chunks_indexed ?? 0}</b></span>
                <span>Discovered: <b style={{ color: "var(--ink)" }}>{crawlResult.urls_discovered ?? crawlResult.sitemap_urls_found ?? 0}</b> URLs</span>
                <span>Sitemaps: <b style={{ color: "var(--ink)" }}>{crawlResult.sitemaps_visited ?? 0}</b></span>
                {crawlResult.failed_pages != null && <span>Failed: <b style={{ color: "var(--ink)" }}>{crawlResult.failed_pages}</b></span>}
              </div>
              {crawlResult.message && <div style={{ marginTop: "6px", color: "var(--muted)" }}>{crawlResult.message}</div>}
              {crawlResult.crawled_urls && Array.isArray(crawlResult.crawled_urls) && crawlResult.crawled_urls.length > 0 && (
                <details style={{ marginTop: "8px" }}>
                  <summary style={{ cursor: "pointer", color: "var(--accent)", fontWeight: 600 }}>View crawled URLs ({crawlResult.crawled_urls.length})</summary>
                  <ul style={{ marginTop: "6px", maxHeight: "140px", overflowY: "auto", paddingLeft: "16px" }}>
                    {crawlResult.crawled_urls.slice(0, 30).map((r: any, i: number) => (
                      <li key={i} style={{ fontSize: "10.5px", color: "var(--muted)", wordBreak: "break-all" }}>
                        {r.url} {r.chunks ? `— ${r.chunks} chunks` : r.skipped ? "— skipped" : ""}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}
        </div>
      </div>

      {showUploadModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div style={{ background: "var(--surface)", border: "1px solid var(--line)", padding: "24px", maxWidth: "480px", width: "90%", borderRadius: "4px" }}>
            <h3 style={{ fontSize: "14px", fontWeight: 600, marginBottom: "8px" }}>Upload Document to Knowledge Base</h3>
            <p style={{ fontSize: "11px", color: "var(--muted)", marginBottom: "16px" }}>
              Upload PDF, DOCX, or TXT documents. The system chunks content into 3200-char pieces and indexes 1536-dim NIM embeddings.
            </p>
            <form onSubmit={handleFileUpload}>
              <div style={{ marginBottom: "12px" }}>
                <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                  Document Title (Optional)
                </label>
                <input
                  type="text"
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                  placeholder="e.g. 2026 Practice Guidelines"
                  className="field"
                  style={{ width: "100%", padding: "8px" }}
                />
              </div>
              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "11px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                  Select File (PDF, DOCX, TXT) *
                </label>
                <input
                  type="file"
                  accept=".pdf,.docx,.txt"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  required
                  style={{ fontSize: "12px" }}
                />
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
                <button type="button" className="btn" onClick={() => setShowUploadModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-accent" disabled={!uploadFile || isUploading}>
                  {isUploading ? "Uploading & Embedding..." : "Upload & Ingest"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: "10px", alignItems: "center", marginBottom: "16px", flexWrap: "wrap" }}>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Filter chunks by keyword or text content..."
          className="field"
          style={{ flex: 1, minWidth: "220px", padding: "8px 12px", fontSize: "12px" }}
        />
        {sourcesList.length > 0 && (
          <select
            value={filterSource}
            onChange={(e) => setFilterSource(e.target.value)}
            className="field"
            style={{ padding: "8px 12px", fontSize: "12px", maxWidth: "260px" }}
          >
            <option value="all">All Sources ({chunks.length})</option>
            {sourcesList.map((src, i) => (
              <option key={i} value={src}>
                {src.length > 35 ? src.slice(0, 35) + "..." : src}
              </option>
            ))}
          </select>
        )}
      </div>

      {loading ? (
        <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>Loading knowledge chunks...</div>
      ) : filteredChunks.length === 0 ? (
        <div className="panel">
          <div className="panel-body" style={{ textAlign: "center", padding: "36px 20px" }}>
            <p style={{ fontSize: "12px", color: "var(--muted)", marginBottom: "12px" }}>
              No knowledge chunks found matching your filter.
            </p>
            <button onClick={handleReCrawl} className="btn btn-accent" style={{ fontSize: "11px", padding: "6px 14px" }}>
              ⚡ Run Sitemap Auto-Crawl
            </button>
          </div>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "14px", marginBottom: "24px" }}>
          {filteredChunks.map((chunk) => {
            const freshness = chunk.freshness_score ? Math.round(chunk.freshness_score * 100) : 98;
            return (
              <div
                key={chunk.id}
                style={{
                  background: "var(--surface)",
                  border: "1px solid var(--line)",
                  padding: "16px",
                  borderRadius: "4px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                }}
              >
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                    <span style={{ fontWeight: 600, fontSize: "12.5px", color: "var(--ink)", maxWidth: "200px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {chunk.title || "Foundational Knowledge Fact"}
                    </span>
                    <span className="badge badge-green" style={{ fontSize: "9.5px" }}>
                      {freshness}% Fresh
                    </span>
                  </div>
                  <p style={{ fontSize: "11.5px", lineHeight: "1.5", color: "var(--muted)", marginBottom: "12px" }}>
                    {chunk.content?.slice(0, 200)}...
                  </p>
                </div>

                <div style={{ borderTop: "1px solid var(--line)", paddingTop: "10px", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "10px", color: "var(--muted)" }}>
                  <span style={{ maxWidth: "180px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {chunk.url ? (
                      <a href={chunk.url} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>
                        {chunk.url.replace(/^https?:\/\//, "")}
                      </a>
                    ) : (
                      `Source: ${chunk.source_type || "manual"}`
                    )}
                  </span>
                  <span>{chunk.created_at ? new Date(chunk.created_at).toLocaleDateString() : "Active"}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Add Specific Custom Knowledge Chunk</span>
        </div>
        <div className="panel-body">
          <form onSubmit={handleIngestText} style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "12px" }}>
            <div>
              <label style={{ display: "block", fontSize: "10px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                Fact Title / Concept
              </label>
              <input
                className="field"
                value={textTitle}
                onChange={(e) => setTextTitle(e.target.value)}
                placeholder="e.g. Core Service Offerings & Pricing"
                style={{ width: "100%", padding: "7px 10px" }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "10px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                Category
              </label>
              <select
                className="field"
                value={textType}
                onChange={(e) => setTextType(e.target.value)}
                style={{ width: "100%", padding: "7px 10px" }}
              >
                <option value="business_info">Business Info</option>
                <option value="service">Service / Product</option>
                <option value="faq">FAQ</option>
                <option value="location">Location / Service Area</option>
              </select>
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <label style={{ display: "block", fontSize: "10px", textTransform: "uppercase", color: "var(--muted)", marginBottom: "4px" }}>
                Verified Fact Content *
              </label>
              <textarea
                className="field"
                value={textContent}
                onChange={(e) => setTextContent(e.target.value)}
                placeholder="Paste verified company facts, policy descriptions, or service overviews..."
                style={{ width: "100%", height: "80px", padding: "8px 10px", fontSize: "11.5px" }}
                required
              />
            </div>
            <div style={{ gridColumn: "1 / -1", display: "flex", justifyContent: "flex-end" }}>
              <button
                type="submit"
                className="btn btn-accent"
                disabled={isIngesting || !textContent.trim()}
                style={{ padding: "8px 18px", fontSize: "11.5px" }}
              >
                {isIngesting ? "⚡ Generating Embedding..." : "+ Ingest Knowledge Fact"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
