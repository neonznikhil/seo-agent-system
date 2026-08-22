"use client";

import { useState } from "react";
import Link from "next/link";
import { post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

export default function GeneratePage() {
  const [topic, setTopic] = useState("");
  const [keyword, setKeyword] = useState("");
  const [tone, setTone] = useState("authoritative, engaging and SEO-optimized");
  const [targetWords, setTargetWords] = useState("1200");
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationPhase, setGenerationPhase] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  
  // Generated result
  const [generatedArticle, setGeneratedArticle] = useState<{
    id: string;
    title: string;
    keyword: string;
    content: string;
    status: string;
    created_at?: string;
  } | null>(null);

  // WordPress publishing state
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishedUrl, setPublishedUrl] = useState<string | null>(null);

  const websiteId = getCurrentWebsiteId();

  const handleStartGeneration = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic.trim()) {
      setError("Please provide an article topic or title.");
      return;
    }

    setIsGenerating(true);
    setError(null);
    setSuccessMsg(null);
    setGeneratedArticle(null);
    setPublishedUrl(null);
    setGenerationPhase(1);

    // Simulate animated phase progression while awaiting LLM response
    const phaseTimer = setInterval(() => {
      setGenerationPhase((prev) => (prev < 5 ? prev + 1 : prev));
    }, 1800);

    try {
      const payload = {
        topic: topic.trim(),
        primary_keyword: keyword.trim() || topic.trim(),
        tone: tone,
        website_id: websiteId,
      };

      const result = await post("/api/generate", payload);

      clearInterval(phaseTimer);
      setGenerationPhase(7); // Completed

      setGeneratedArticle({
        id: result.id,
        title: result.title || topic,
        keyword: result.keyword || keyword || topic,
        content: result.content || "",
        status: result.status || "pending_approval",
        created_at: result.created_at,
      });

      setSuccessMsg("✓ Autonomous generation complete! Llama-3.1-70B generated the article and saved to Supabase.");
    } catch (err: any) {
      clearInterval(phaseTimer);
      setError(err.message || "Failed to generate blog. Ensure FastAPI backend is running with NVIDIA_API_KEY.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handlePublishToWordPress = async () => {
    if (!generatedArticle) return;
    try {
      setIsPublishing(true);
      setError(null);

      // Call backend WordPress publish endpoint
      const res = await post("/api/wordpress/publish", {
        title: generatedArticle.title,
        content: generatedArticle.content,
        status: "publish",
      });

      const wpUrl = res.wp_url || res.link || (res.id ? `Published (ID #${res.id})` : "Published successfully!");
      setPublishedUrl(wpUrl);
      setSuccessMsg(`✓ Successfully published to WordPress live site!`);
      
      setGeneratedArticle((prev) => prev ? { ...prev, status: "published" } : null);
    } catch (err: any) {
      setError(`WordPress publish error: ${err.message}. Make sure WordPress credentials are saved in /wordpress.`);
    } finally {
      setIsPublishing(false);
    }
  };

  const calculateWordCount = (text: string) => {
    if (!text) return 0;
    return text.trim().split(/\s+/).filter(Boolean).length;
  };

  return (
    <div className="page-container active" style={{ position: "relative", display: "block" }}>
      {/* PAGE HEADER */}
      <div className="page-heading">Generate Article</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        10-Phase Autonomous Writing Pipeline · Powered by NVIDIA NIM Llama-3.1-70B · Supabase Synced
      </div>

      {/* NOTICES */}
      {error && (
        <div className="notice" style={{ borderColor: "var(--red)", background: "rgba(239,68,68,0.08)" }}>
          <span className="notice-sq" style={{ background: "var(--red)" }}></span>
          <span style={{ color: "var(--red)" }}>{error}</span>
        </div>
      )}

      {successMsg && (
        <div className="notice ok">
          <span className="notice-sq"></span>
          <span>{successMsg}</span>
        </div>
      )}

      {/* 10-PHASE PIPELINE STATUS BAR */}
      <div className="panel" style={{ marginBottom: "16px" }}>
        <div className="panel-head">
          <span className="panel-label">Autonomous 10-Phase Pipeline</span>
          <span className={`badge ${isGenerating ? "badge-accent" : generationPhase === 7 ? "badge-green" : "badge-muted"}`}>
            {isGenerating ? "Executing Phase " + generationPhase : generationPhase === 7 ? "Complete" : "Ready"}
          </span>
        </div>
        <div className="panel-body">
          <div className="pipeline-phases">
            <div className={`phase ${generationPhase >= 1 ? (generationPhase === 1 ? "running" : "done") : ""}`}>
              1. Brain Recall
            </div>
            <div className={`phase ${generationPhase >= 2 ? (generationPhase === 2 ? "running" : "done") : ""}`}>
              2. Demand Intel
            </div>
            <div className={`phase ${generationPhase >= 3 ? (generationPhase === 3 ? "running" : "done") : ""}`}>
              3. SERP Gap
            </div>
            <div className={`phase ${generationPhase >= 4 ? (generationPhase === 4 ? "running" : "done") : ""}`}>
              4. Outline
            </div>
            <div className={`phase ${generationPhase >= 5 ? (generationPhase === 5 ? "running" : "done") : ""}`}>
              5. NIM 70B Drafting
            </div>
            <div className={`phase ${generationPhase >= 6 ? (generationPhase === 6 ? "running" : "done") : ""}`}>
              6. Quality Gate
            </div>
            <div className={`phase ${generationPhase >= 7 ? "done" : ""}`}>
              7. Approval / Publish
            </div>
          </div>
          <div className="prog-row" style={{ marginBottom: 0 }}>
            <div className="prog-label">
              <span>Execution Pipeline Status</span>
              <span>
                {isGenerating
                  ? "Phase " + generationPhase + " of 7 — Analyzing intent and generating comprehensive content..."
                  : generationPhase === 7
                  ? "Article generated and ready for review/publish"
                  : "Idle — ready to start"}
              </span>
            </div>
            <div className="prog-track">
              <div
                className={`prog-fill ${generationPhase === 7 ? "green" : ""}`}
                style={{ width: `${(generationPhase / 7) * 100}%` }}
              ></div>
            </div>
          </div>
        </div>
      </div>

      {/* GENERATION INPUT FORM & SETTINGS */}
      <div className="grid-2" style={{ marginBottom: "16px" }}>
        {/* INPUT FORM */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">⚡ Article Parameters</span>
            <span className="badge badge-green">NVIDIA NIM Live</span>
          </div>
          <form onSubmit={handleStartGeneration} className="panel-body">
            <div className="field-group">
              <div className="field-label">
                <span>Article Topic / Title</span>
                <span className="field-hint">Required</span>
              </div>
              <input
                className="field"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g. Modern Technical SEO Checklist 2026: Schema, CWV & AEO"
                disabled={isGenerating}
              />
            </div>

            <div className="field-group">
              <div className="field-label">
                <span>Primary Target Keyword</span>
                <span className="field-hint">Optional (defaults to topic)</span>
              </div>
              <input
                className="field"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder="e.g. technical seo checklist"
                disabled={isGenerating}
              />
            </div>

            <div className="grid-2">
              <div className="field-group">
                <div className="field-label">Brand Voice Tone</div>
                <select
                  className="field"
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  disabled={isGenerating}
                >
                  <option value="authoritative, engaging and SEO-optimized">Authoritative & Insightful</option>
                  <option value="technical, step-by-step developer guide">Technical & Practical</option>
                  <option value="conversational, accessible and persuasive">Conversational & Engaging</option>
                  <option value="data-driven, analytical and executive">Data-Driven Executive</option>
                </select>
              </div>

              <div className="field-group">
                <div className="field-label">Target Word Count</div>
                <select
                  className="field"
                  value={targetWords}
                  onChange={(e) => setTargetWords(e.target.value)}
                  disabled={isGenerating}
                >
                  <option value="1000">~1,000 words (Standard)</option>
                  <option value="1500">~1,500 words (In-depth)</option>
                  <option value="2000">~2,000 words (Ultimate Guide)</option>
                </select>
              </div>
            </div>

            <div style={{ display: "flex", gap: "10px", marginTop: "14px" }}>
              <button
                type="submit"
                className="btn btn-accent"
                style={{ flex: 1, padding: "10px 14px", fontWeight: 600 }}
                disabled={isGenerating}
              >
                {isGenerating ? "⚡ Generating with NVIDIA NIM..." : "⚡ Start 10-Phase Pipeline →"}
              </button>
              <button
                type="button"
                className="btn"
                onClick={() => {
                  setTopic("Enterprise Technical SEO Audit: Complete Framework for High-Traffic Sites");
                  setKeyword("enterprise technical seo audit");
                }}
                disabled={isGenerating}
              >
                Sample
              </button>
            </div>
          </form>
        </div>

        {/* GUIDELINES & SPECIFICATIONS */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">Autonomous Quality Gates</span>
            <span className="badge badge-ink">Active Rules</span>
          </div>
          <div className="panel-body">
            <div className="notice info" style={{ marginBottom: "12px" }}>
              <span className="notice-sq"></span>
              The writer recalls brand memory from Supabase, checks SERP gap algorithms, formats markdown tables, and generates structured FAQ schema.
            </div>

            <div className="check-row">
              <span className="ci pass">✓</span>
              <span className="ck-label">AI Search & AEO Direct Answer in first 100 words</span>
              <span className="badge badge-green">Enforced</span>
            </div>
            <div className="check-row">
              <span className="ci pass">✓</span>
              <span className="ck-label">Banned AI words filter (delve, elevate, revolutionize)</span>
              <span className="badge badge-green">Zero-tolerance</span>
            </div>
            <div className="check-row">
              <span className="ci pass">✓</span>
              <span className="ck-label">Structured Comparison / Implementation Table</span>
              <span className="badge badge-green">Auto-included</span>
            </div>
            <div className="check-row">
              <span className="ci pass">✓</span>
              <span className="ck-label">Schema FAQ section with actionable query answers</span>
              <span className="badge badge-green">Included</span>
            </div>
          </div>
        </div>
      </div>

      {/* GENERATED ARTICLE OUTPUT PREVIEW */}
      {generatedArticle && (
        <div className="panel" style={{ marginBottom: "20px" }}>
          <div className="panel-head">
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span className="panel-label">📄 Generated Article Preview</span>
              <span className="badge badge-green">{generatedArticle.status}</span>
              <span className="badge badge-ink">{calculateWordCount(generatedArticle.content)} words</span>
            </div>
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                className="btn btn-accent"
                onClick={handlePublishToWordPress}
                disabled={isPublishing}
                style={{ fontWeight: 600 }}
              >
                {isPublishing ? "Publishing to WordPress..." : "🔷 1-Click Publish to WordPress"}
              </button>
              <button
                className="btn"
                onClick={() => {
                  navigator.clipboard.writeText(generatedArticle.content);
                  setSuccessMsg("Copied full Markdown to clipboard!");
                }}
              >
                📋 Copy Markdown
              </button>
              <Link href="/content" className="btn btn-primary" style={{ textDecoration: "none" }}>
                View in Content Studio →
              </Link>
            </div>
          </div>

          <div className="panel-body">
            <div style={{ marginBottom: "14px", padding: "10px", background: "var(--bg2)", border: "1px solid var(--line)" }}>
              <div style={{ fontSize: "14px", fontWeight: 700, color: "var(--ink)", marginBottom: "4px" }}>
                {generatedArticle.title}
              </div>
              <div style={{ fontSize: "10px", color: "var(--muted)", display: "flex", gap: "16px" }}>
                <span><strong>Keyword:</strong> {generatedArticle.keyword}</span>
                <span><strong>Model:</strong> Llama-3.1-70B-Instruct</span>
                <span><strong>Database ID:</strong> {generatedArticle.id}</span>
                {publishedUrl && (
                  <span>
                    <strong>WordPress URL:</strong>{" "}
                    <a href={publishedUrl} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>
                      {publishedUrl} ↗
                    </a>
                  </span>
                )}
              </div>
            </div>

            {/* RAW CONTENT VIEWER */}
            <textarea
              className="field"
              rows={18}
              value={generatedArticle.content}
              onChange={(e) => setGeneratedArticle({ ...generatedArticle, content: e.target.value })}
              style={{
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: "11px",
                lineHeight: "1.7",
                background: "var(--panel-inner)",
              }}
            />
          </div>
        </div>
      )}

      {/* BOTTOM TICKER */}
      <div className="bticker">
        <span className="bticker-inner">
          <span className="bt-sq"></span>AUTONOMOUS WRITER <span className="bt-sep">/</span>
          <span className="bt-sq"></span>NVIDIA NIM LLAMA-3.1-70B <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SAVED DIRECTLY TO SUPABASE CONTENT_LOG <span className="bt-sep">/</span>
          <span className="bt-sq"></span>1-CLICK WORDPRESS PUBLISHING ACTIVE &nbsp;&nbsp;&nbsp;&nbsp;
          <span className="bt-sq"></span>AUTONOMOUS WRITER <span className="bt-sep">/</span>
          <span className="bt-sq"></span>NVIDIA NIM LLAMA-3.1-70B <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SAVED DIRECTLY TO SUPABASE CONTENT_LOG <span className="bt-sep">/</span>
          <span className="bt-sq"></span>1-CLICK WORDPRESS PUBLISHING ACTIVE
        </span>
      </div>
    </div>
  );
}
