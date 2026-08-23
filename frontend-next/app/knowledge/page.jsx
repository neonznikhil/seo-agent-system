"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { 
  BookOpen, Upload, Globe, FileText, Search, Sparkles, AlertTriangle, 
  Trash2, RefreshCw, Plus, ExternalLink, CheckCircle2, ArrowRight, Eye,
  Shield, Layers, Filter
} from "lucide-react";

export default function KnowledgePage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedType, setSelectedType] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Ingestion form states
  const [activeTab, setActiveTab] = useState("text"); // 'text' | 'url' | 'pdf' | 'competitor'
  const [textTitle, setTextTitle] = useState("");
  const [textContent, setTextContent] = useState("");
  const [textCategory, setTextCategory] = useState("business_info");

  const [inputUrl, setInputUrl] = useState("");
  const [urlTitle, setUrlTitle] = useState("");

  const [competitorUrl, setCompetitorUrl] = useState("");
  const [isScraping, setIsScraping] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);

  // Preview modal for llms.txt
  const [showLlmsModal, setShowLlmsModal] = useState(false);
  const [llmsContent, setLlmsContent] = useState("");
  const [loadingLlms, setLoadingLlms] = useState(false);

  // Load items on mount
  useEffect(() => {
    loadKnowledge();
  }, [selectedType]);

  const loadKnowledge = async () => {
    setLoading(true);
    setError(null);
    try {
      const typeParam = selectedType !== "all" ? `?type=${selectedType}` : "";
      const res = await fetch(`http://localhost:8000/api/knowledge${typeParam}`);
      if (res.ok) {
        const data = await res.json();
        setItems(Array.isArray(data) ? data : []);
      }
    } catch (e) {
      console.warn("Knowledge load error:", e);
      setError("Failed to connect to Knowledge Base backend");
    } finally {
      setLoading(false);
    }
  };

  // Vector Search
  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) {
      loadKnowledge();
      return;
    }
    setIsSearching(true);
    setError(null);
    try {
      const res = await fetch(`http://localhost:8000/api/knowledge/search?q=${encodeURIComponent(searchQuery)}`);
      if (res.ok) {
        const data = await res.json();
        setItems(data.results || []);
      }
    } catch (e) {
      setError("Vector search failed");
    } finally {
      setIsSearching(false);
    }
  };

  // Drag & Drop PDF
  const onDrop = useCallback(async (acceptedFiles) => {
    if (!acceptedFiles || acceptedFiles.length === 0) return;
    const file = acceptedFiles[0];
    setIsIngesting(true);
    setError(null);
    setSuccessMsg(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("title", file.name.replace(/\.[^/.]+$/, ""));
    formData.append("type", "business_info");

    try {
      const res = await fetch("http://localhost:8000/api/knowledge/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "PDF ingestion failed");
      setSuccessMsg(`✅ Successfully ingested ${data.inserted_chunks} chunks from PDF: ${file.name}`);
      loadKnowledge();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsIngesting(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"], "text/plain": [".txt"] },
    maxFiles: 1,
  });

  // Ingest Text
  const handleIngestText = async (e) => {
    e.preventDefault();
    if (!textContent.trim()) {
      setError("Please paste or type content to ingest");
      return;
    }
    setIsIngesting(true);
    setError(null);
    setSuccessMsg(null);

    const formData = new FormData();
    formData.append("text", textContent);
    formData.append("title", textTitle || "Business Context Document");
    formData.append("type", textCategory);

    try {
      const res = await fetch("http://localhost:8000/api/knowledge/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Text ingestion failed");
      setSuccessMsg(`✅ Successfully ingested ${data.inserted_chunks} knowledge chunks as '${textCategory}'!`);
      setTextTitle("");
      setTextContent("");
      loadKnowledge();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsIngesting(false);
    }
  };

  // Ingest URL
  const handleIngestUrl = async (e) => {
    e.preventDefault();
    if (!inputUrl.trim()) {
      setError("Please enter a valid URL");
      return;
    }
    setIsIngesting(true);
    setError(null);
    setSuccessMsg(null);

    const formData = new FormData();
    formData.append("url", inputUrl.trim());
    formData.append("title", urlTitle || inputUrl);
    formData.append("type", "service");

    try {
      const res = await fetch("http://localhost:8000/api/knowledge/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "URL scraping & ingestion failed");
      setSuccessMsg(`✅ Extracted & ingested ${data.inserted_chunks} chunks from URL!`);
      setInputUrl("");
      setUrlTitle("");
      loadKnowledge();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsIngesting(false);
    }
  };

  // Scrape Competitor
  const handleScrapeCompetitor = async (e) => {
    e.preventDefault();
    if (!competitorUrl.trim()) {
      setError("Please enter competitor URL");
      return;
    }
    setIsScraping(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const res = await fetch("http://localhost:8000/api/knowledge/scrape-competitor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: competitorUrl.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Competitor analysis failed");
      setSuccessMsg(`✅ Scraped competitor intelligence (${data.word_count} words analyzed)!`);
      setCompetitorUrl("");
      loadKnowledge();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsScraping(false);
    }
  };

  // Delete item
  const handleDeleteItem = async (id) => {
    if (!confirm("Are you sure you want to delete this knowledge chunk?")) return;
    try {
      const res = await fetch(`http://localhost:8000/api/knowledge/${id}`, { method: "DELETE" });
      if (res.ok) {
        setItems((prev) => prev.filter((it) => it.id !== id));
      }
    } catch (e) {
      console.warn("Delete failed:", e);
    }
  };

  // Regenerate llms.txt
  const handleRegenerateLlms = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/llms/generate", { method: "POST" });
      if (res.ok) {
        setSuccessMsg("✅ Generated fresh llms.txt and llms-full.txt from Knowledge Base!");
      }
    } catch (e) {
      console.warn("Generate llms.txt error:", e);
    }
  };

  // Preview llms.txt
  const handlePreviewLlms = async () => {
    setShowLlmsModal(true);
    setLoadingLlms(true);
    try {
      const res = await fetch("http://localhost:8000/llms.txt");
      if (res.ok) {
        const text = await res.text();
        setLlmsContent(text);
      } else {
        setLlmsContent("# Error loading llms.txt");
      }
    } catch (e) {
      setLlmsContent("# Error: Could not connect to backend");
    } finally {
      setLoadingLlms(false);
    }
  };

  // Helper badge color for knowledge type
  const getTypeBadgeClass = (type) => {
    switch (type) {
      case "business_info":
        return "bg-blue-500/10 text-blue-400 border-blue-500/20";
      case "service":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
      case "location":
        return "bg-purple-500/10 text-purple-400 border-purple-500/20";
      case "competitor":
        return "bg-orange-500/10 text-orange-400 border-orange-500/20";
      case "seo_rule":
        return "bg-yellow-500/10 text-yellow-400 border-yellow-500/20";
      case "faq":
        return "bg-gray-700 text-gray-300 border-gray-600";
      case "analytics_learning":
        return "bg-pink-500/10 text-pink-400 border-pink-500/20";
      case "law_statute":
        return "bg-red-500/10 text-red-400 border-red-500/20";
      default:
        return "bg-gray-800 text-gray-400 border-gray-700";
    }
  };

  // Freshness dot calculation
  const getFreshnessDot = (created_at, freshness_score) => {
    const score = freshness_score ?? 1.0;
    if (score >= 0.8) return { color: "bg-emerald-500", text: "Fresh (<30d)" };
    if (score >= 0.5) return { color: "bg-yellow-500", text: "Moderate (30-90d)" };
    return { color: "bg-red-500", text: "Stale (>90d)" };
  };

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-200 p-6 md:p-8">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800 pb-6">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-blue-500/10 text-blue-400 rounded-lg border border-blue-500/20">
              <BookOpen className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">Deep Knowledge Base & Anti-Hallucination Brain</h1>
              <p className="text-sm text-gray-400">Ground truth business data, services, location facts, and competitor intelligence powering AI writers.</p>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleRegenerateLlms}
              className="py-2 px-3.5 bg-gray-800 hover:bg-gray-700 text-white rounded-lg text-xs font-medium transition flex items-center gap-1.5 border border-gray-700"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Regenerate llms.txt
            </button>
            <button
              onClick={handlePreviewLlms}
              className="py-2 px-3.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium transition flex items-center gap-1.5 shadow-lg shadow-blue-900/30"
            >
              <Eye className="w-3.5 h-3.5" /> Preview /llms.txt
            </button>
          </div>
        </div>
      </div>

      {/* Warning banner if Knowledge Base is empty */}
      {items.length === 0 && !loading && (
        <div className="max-w-7xl mx-auto mb-6 p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-semibold text-amber-300">Knowledge Base Empty: Upload Business Info First</h4>
            <p className="text-xs text-amber-400/80 mt-0.5">
              RankForge's Content Writer strictly enforces zero hallucination. It requires at least 5 business context documents/chunks before writing articles. Upload business facts, legal specializations, or firm background below.
            </p>
          </div>
        </div>
      )}

      {/* Feedback Alerts */}
      {error && (
        <div className="max-w-7xl mx-auto mb-6 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400">
          {error}
        </div>
      )}
      {successMsg && (
        <div className="max-w-7xl mx-auto mb-6 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-xs text-emerald-400">
          {successMsg}
        </div>
      )}

      {/* Top Section: Ingestion Tools */}
      <div className="max-w-7xl mx-auto mb-8 bg-gray-900/80 border border-gray-800 rounded-xl p-6 shadow-xl">
        <div className="flex items-center gap-2 border-b border-gray-800 pb-4 mb-5">
          <button
            onClick={() => setActiveTab("text")}
            className={`py-2 px-4 rounded-lg text-xs font-medium transition ${
              activeTab === "text" ? "bg-blue-600 text-white" : "bg-gray-800/60 text-gray-400 hover:text-white"
            }`}
          >
            <FileText className="w-3.5 h-3.5 inline mr-1.5" /> Paste Business Text
          </button>
          <button
            onClick={() => setActiveTab("pdf")}
            className={`py-2 px-4 rounded-lg text-xs font-medium transition ${
              activeTab === "pdf" ? "bg-blue-600 text-white" : "bg-gray-800/60 text-gray-400 hover:text-white"
            }`}
          >
            <Upload className="w-3.5 h-3.5 inline mr-1.5" /> Upload PDF Document
          </button>
          <button
            onClick={() => setActiveTab("url")}
            className={`py-2 px-4 rounded-lg text-xs font-medium transition ${
              activeTab === "url" ? "bg-blue-600 text-white" : "bg-gray-800/60 text-gray-400 hover:text-white"
            }`}
          >
            <Globe className="w-3.5 h-3.5 inline mr-1.5" /> Scrape Website URL
          </button>
          <button
            onClick={() => setActiveTab("competitor")}
            className={`py-2 px-4 rounded-lg text-xs font-medium transition ${
              activeTab === "competitor" ? "bg-orange-600 text-white" : "bg-gray-800/60 text-gray-400 hover:text-white"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 inline mr-1.5" /> Scrape Competitor Intel
          </button>
        </div>

        {/* Tab 1: Text */}
        {activeTab === "text" && (
          <form onSubmit={handleIngestText} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Document Title</label>
                <input
                  type="text"
                  placeholder="e.g. Houston Injury Law Practice Overview & Retainer Terms"
                  value={textTitle}
                  onChange={(e) => setTextTitle(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3.5 py-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Knowledge Category</label>
                <select
                  value={textCategory}
                  onChange={(e) => setTextCategory(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3.5 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
                >
                  <option value="business_info">Business Info (Firm facts, founders, overview)</option>
                  <option value="service">Service (Practice areas, legal services)</option>
                  <option value="location">Location (Houston, Harris County, Texas)</option>
                  <option value="seo_rule">SEO Rule (Specific brand voice and guidelines)</option>
                  <option value="faq">FAQ (Common client queries & answers)</option>
                  <option value="pricing">Pricing / Contingency fee facts</option>
                  <option value="testimonial">Testimonial & Social Proof</option>
                  <option value="law_statute">Law Statute / Texas Civil Codes</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-300 mb-1">Content / Business Facts</label>
              <textarea
                rows={4}
                placeholder="Paste verified factual details: founding year, practice specializations, Houston court jurisdictions, client case results, contact phone numbers..."
                value={textContent}
                onChange={(e) => setTextContent(e.target.value)}
                className="w-full bg-gray-950 border border-gray-800 rounded-lg p-3 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 leading-relaxed font-mono"
              />
            </div>
            <button
              type="submit"
              disabled={isIngesting}
              className="py-2 px-5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium transition flex items-center gap-1.5 shadow-lg shadow-blue-900/30"
            >
              <Plus className="w-3.5 h-3.5" />
              {isIngesting ? "Chunking & Embedding..." : "Chunk, Embed & Ingest Text"}
            </button>
          </form>
        )}

        {/* Tab 2: PDF Dropzone */}
        {activeTab === "pdf" && (
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition ${
              isDragActive ? "border-blue-500 bg-blue-500/5" : "border-gray-800 hover:border-gray-700 bg-gray-950/50"
            }`}
          >
            <input {...getInputProps()} />
            <Upload className="w-8 h-8 text-blue-400 mx-auto mb-2" />
            <p className="text-sm font-medium text-gray-200">
              {isDragActive ? "Drop PDF file here..." : "Drag & drop PDF business profile or click to browse"}
            </p>
            <p className="text-xs text-gray-500 mt-1">PyMuPDF will extract text, create 3200-char chunks, and generate 1536-dim embeddings automatically.</p>
          </div>
        )}

        {/* Tab 3: URL */}
        {activeTab === "url" && (
          <form onSubmit={handleIngestUrl} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Target Web Page URL</label>
                <input
                  type="url"
                  placeholder="https://accident.innovatcs.com/houston-car-accident-lawyer"
                  value={inputUrl}
                  onChange={(e) => setInputUrl(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3.5 py-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Document Title (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Practice Page Content"
                  value={urlTitle}
                  onChange={(e) => setUrlTitle(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3.5 py-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={isIngesting}
              className="py-2 px-5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium transition flex items-center gap-1.5 shadow-lg shadow-blue-900/30"
            >
              <Globe className="w-3.5 h-3.5" />
              {isIngesting ? "Extracting & Embedding..." : "Scrape & Ingest URL"}
            </button>
          </form>
        )}

        {/* Tab 4: Competitor */}
        {activeTab === "competitor" && (
          <form onSubmit={handleScrapeCompetitor} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-300 mb-1">Competitor Webpage URL</label>
              <input
                type="url"
                placeholder="https://competitorlawfirm.com/houston-truck-accidents"
                value={competitorUrl}
                onChange={(e) => setCompetitorUrl(e.target.value)}
                className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3.5 py-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-orange-500"
              />
            </div>
            <p className="text-xs text-gray-500">
              Scrapes competitor content via Trafilatura, uses NIM LLM to extract keyword density, structure patterns, and saves intelligence as <code>competitor</code> type.
            </p>
            <button
              type="submit"
              disabled={isScraping}
              className="py-2 px-5 bg-orange-600 hover:bg-orange-500 text-white rounded-lg text-xs font-medium transition flex items-center gap-1.5 shadow-lg shadow-orange-900/30"
            >
              <Sparkles className="w-3.5 h-3.5" />
              {isScraping ? "Analyzing Competitor..." : "Scrape Competitor Intelligence"}
            </button>
          </form>
        )}
      </div>

      {/* Main Knowledge Base List & Vector Search */}
      <div className="max-w-7xl mx-auto bg-gray-900/80 border border-gray-800 rounded-xl p-6 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          {/* Vector Search Bar */}
          <form onSubmit={handleSearch} className="flex-1 max-w-md relative">
            <input
              type="text"
              placeholder="Semantic vector search (e.g. Houston truck accident statutes)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-gray-950 border border-gray-800 rounded-lg pl-9 pr-20 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
            <Search className="w-4 h-4 text-gray-500 absolute left-3 top-2.5" />
            <button
              type="submit"
              disabled={isSearching}
              className="absolute right-1.5 top-1.5 px-2.5 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded text-[11px] font-medium transition"
            >
              {isSearching ? "..." : "Search"}
            </button>
          </form>

          {/* Type Filter Badges */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-xs text-gray-400 mr-1 flex items-center gap-1">
              <Filter className="w-3.5 h-3.5" /> Filter:
            </span>
            {["all", "business_info", "service", "location", "competitor", "seo_rule", "faq", "analytics_learning"].map((t) => (
              <button
                key={t}
                onClick={() => setSelectedType(t)}
                className={`py-1 px-2.5 rounded-full text-[11px] font-medium transition border ${
                  selectedType === t
                    ? "bg-blue-600 text-white border-blue-500"
                    : "bg-gray-950 text-gray-400 border-gray-800 hover:border-gray-700"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* List of Documents / Chunks */}
        {loading ? (
          <div className="py-12 text-center text-xs text-gray-500 font-mono">
            Loading Knowledge Base pgvector index...
          </div>
        ) : items.length === 0 ? (
          <div className="py-12 text-center text-xs text-gray-500">
            No knowledge entries found matching the filter or search query.
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((it) => {
              const freshness = getFreshnessDot(it.created_at, it.freshness_score);
              return (
                <div
                  key={it.id}
                  className="bg-gray-950/60 border border-gray-800/80 hover:border-gray-700 rounded-lg p-4 transition flex flex-col md:flex-row md:items-start justify-between gap-4"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                      <span className={`text-[11px] font-semibold px-2 py-0.5 rounded border uppercase tracking-wider ${getTypeBadgeClass(it.type)}`}>
                        {it.type}
                      </span>
                      <span className="text-xs font-semibold text-gray-200">{it.title}</span>
                      <span className="inline-flex items-center gap-1 text-[11px] text-gray-400">
                        <span className={`w-2 h-2 rounded-full ${freshness.color}`} />
                        {freshness.text}
                      </span>
                      {it.total_chunks > 1 && (
                        <span className="text-[10px] bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded">
                          Chunk {it.chunk_index + 1}/{it.total_chunks}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-300 font-mono leading-relaxed line-clamp-3 bg-gray-900/40 p-2.5 rounded border border-gray-800/50">
                      {it.content}
                    </p>
                    <div className="flex items-center gap-4 text-[11px] text-gray-500 mt-2">
                      <span>Source: {it.source || "text"}</span>
                      {it.url && (
                        <a href={it.url} target="_blank" rel="noreferrer" className="text-blue-400 hover:underline truncate max-w-xs flex items-center gap-1">
                          {it.url} <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                      <span>Usage count: {it.usage_count ?? 0}</span>
                      {it.similarity !== undefined && (
                        <span className="text-emerald-400 font-semibold">Similarity: {(it.similarity * 100).toFixed(1)}%</span>
                      )}
                    </div>
                  </div>

                  <button
                    onClick={() => handleDeleteItem(it.id)}
                    className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition"
                    title="Delete knowledge chunk"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* llms.txt Modal Preview */}
      {showLlmsModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-gray-900 border border-gray-800 rounded-xl max-w-3xl w-full max-h-[85vh] flex flex-col shadow-2xl">
            <div className="p-4 border-b border-gray-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-blue-400" />
                <h3 className="font-semibold text-white text-sm">llms.txt Generated Preview</h3>
              </div>
              <button
                onClick={() => setShowLlmsModal(false)}
                className="text-xs text-gray-400 hover:text-white px-2 py-1 bg-gray-800 rounded"
              >
                Close
              </button>
            </div>
            <div className="p-4 flex-1 overflow-y-auto font-mono text-xs text-gray-300 whitespace-pre-wrap bg-gray-950">
              {loadingLlms ? "Generating real llms.txt from knowledge base..." : llmsContent}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
