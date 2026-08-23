"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  Position,
  Handle
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { 
  BookOpen, Upload, Globe, FileText, Search, Trash2, RefreshCw, 
  Sparkles, CheckCircle2, AlertTriangle, ArrowRight, ShieldCheck,
  ExternalLink, Eye, Layers, Share2, Check, X, ShieldAlert, Cpu, Activity
} from "lucide-react";

// ---------------------------------------------------------
// Custom Knowledge Node for Graph Visualizer
// ---------------------------------------------------------
function KnowledgeNode({ data }) {
  const isSelected = data.isSelected;
  const typeColors = {
    business_info: "border-blue-500 bg-blue-950/40 text-blue-300",
    service: "border-emerald-500 bg-emerald-950/40 text-emerald-300",
    location: "border-purple-500 bg-purple-950/40 text-purple-300",
    competitor: "border-orange-500 bg-orange-950/40 text-orange-300",
    law_statute: "border-amber-500 bg-amber-950/40 text-amber-300",
    analytics_learning: "border-pink-500 bg-pink-950/40 text-pink-300"
  };
  const colorStyle = typeColors[data.type] || "border-gray-700 bg-gray-900 text-gray-300";

  return (
    <div
      className={`min-w-[200px] max-w-[240px] p-3 rounded-xl border-2 transition-all cursor-pointer shadow-xl ${colorStyle} ${
        isSelected ? "ring-2 ring-white scale-105" : ""
      } ${data.validated ? "border-solid" : "border-dashed"}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-blue-400 !w-2.5 !h-2.5" />
      <div className="flex items-center justify-between gap-1 mb-1">
        <span className="text-[9px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-black/40">
          {data.type.replace("_", " ")}
        </span>
        {data.validated ? (
          <span className="text-[10px] text-emerald-400 flex items-center gap-0.5" title="Verified Accurate">
            <CheckCircle2 className="w-3 h-3" /> {Math.round((data.validation_score || 0.9) * 100)}%
          </span>
        ) : (
          <span className="text-[10px] text-amber-400 flex items-center gap-0.5" title="Unvalidated">
            <AlertTriangle className="w-3 h-3" /> Review
          </span>
        )}
      </div>
      <h4 className="text-xs font-semibold text-white truncate mb-1">{data.title}</h4>
      <div className="flex items-center justify-between text-[10px] opacity-75 font-mono pt-1 border-t border-white/10">
        <span>Cred: {data.credibility}</span>
        <span>Fresh: {Math.round(data.freshness * 100)}%</span>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-emerald-400 !w-2.5 !h-2.5" />
    </div>
  );
}

const nodeTypes = {
  knowledgeNode: KnowledgeNode
};

export default function KnowledgePage() {
  const [activeTab, setActiveTab] = useState("documents"); // 'documents' | 'graph' | 'validation'
  const [knowledgeList, setKnowledgeList] = useState([]);
  const [selectedType, setSelectedType] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchMode, setSearchMode] = useState("hybrid"); // 'hybrid' | 'vector'
  const [searchResults, setSearchResults] = useState(null);
  const [loading, setLoading] = useState(true);

  // Upload Form State
  const [uploadMode, setUploadMode] = useState("text"); // 'text' | 'url' | 'competitor'
  const [docTitle, setDocTitle] = useState("");
  const [docContent, setDocContent] = useState("");
  const [docType, setDocType] = useState("business_info");
  const [urlInput, setUrlInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notice, setNotice] = useState(null);

  // Graph State
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNodeData, setSelectedNodeData] = useState(null);

  // Validation State
  const [isValidatingAll, setIsValidatingAll] = useState(false);

  // 1. Fetch Knowledge on Load
  const fetchKnowledge = useCallback(async () => {
    setLoading(true);
    try {
      const typeParam = selectedType !== "all" ? `?type=${selectedType}` : "";
      const res = await fetch(`http://localhost:8000/api/knowledge${typeParam}`);
      if (res.ok) {
        const data = await res.json();
        setKnowledgeList(Array.isArray(data) ? data : []);
      }
    } catch (e) {
      console.warn("Knowledge load error:", e);
    } finally {
      setLoading(false);
    }
  }, [selectedType]);

  // 2. Fetch Graph Data
  const fetchGraph = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/knowledge/graph");
      if (res.ok) {
        const graphData = await res.json();
        const rawNodes = graphData.nodes || [];
        const rawEdges = graphData.edges || [];

        // Position nodes in a 4-column cluster
        const positionedNodes = rawNodes.map((n, i) => {
          const col = i % 4;
          const row = Math.floor(i / 4);
          return {
            id: n.id,
            type: "knowledgeNode",
            position: { x: 50 + col * 260, y: 50 + row * 180 },
            data: {
              ...n,
              isSelected: selectedNodeData?.id === n.id
            }
          };
        });

        const formattedEdges = rawEdges.map((e, idx) => ({
          id: e.id || `e-${idx}`,
          source: e.source,
          target: e.target,
          animated: true,
          style: { stroke: "#3b82f6", strokeWidth: Math.max(1.5, e.strength * 3) }
        }));

        setNodes(positionedNodes);
        setEdges(formattedEdges);
      }
    } catch (e) {
      console.warn("Graph fetch error:", e);
    }
  };

  useEffect(() => {
    fetchKnowledge();
  }, [fetchKnowledge]);

  useEffect(() => {
    if (activeTab === "graph") {
      fetchGraph();
    }
  }, [activeTab]);

  // 3. Search (Vector vs Hybrid)
  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }

    try {
      const endpoint = searchMode === "hybrid" ? "/api/knowledge/search/hybrid" : "/api/knowledge/search";
      const res = await fetch(`http://localhost:8000${endpoint}?q=${encodeURIComponent(searchQuery)}&top_k=5`);
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.results || []);
      }
    } catch (err) {
      console.warn("Search error:", err);
    }
  };

  // 4. Ingest Form Submit
  const handleIngest = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setNotice(null);

    try {
      const formData = new FormData();
      if (uploadMode === "text") {
        formData.append("text", docContent);
        formData.append("title", docTitle || "Business Context Chunk");
        formData.append("type", docType);
      } else if (uploadMode === "url") {
        formData.append("url", urlInput);
        formData.append("type", docType);
      } else if (uploadMode === "competitor") {
        formData.append("url", urlInput);
        formData.append("type", "competitor");
      }

      const res = await fetch("http://localhost:8000/api/knowledge/upload", {
        method: "POST",
        body: formData
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Ingestion failed");

      setNotice(`✅ ${data.message}`);
      setDocContent("");
      setDocTitle("");
      setUrlInput("");
      fetchKnowledge();
      if (activeTab === "graph") fetchGraph();
    } catch (err) {
      setNotice(`⚠️ ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 5. Fact-Check Validation Handlers
  const handleValidateSingle = async (id) => {
    try {
      const res = await fetch(`http://localhost:8000/api/knowledge/validate/${id}`, { method: "POST" });
      if (res.ok) {
        fetchKnowledge();
      }
    } catch (e) {
      console.warn("Validate error:", e);
    }
  };

  const handleValidateAll = async () => {
    setIsValidatingAll(true);
    try {
      const res = await fetch("http://localhost:8000/api/knowledge/validate-all", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setNotice(`✅ ${data.message}`);
        fetchKnowledge();
      }
    } catch (e) {
      setNotice("Validation failed");
    } finally {
      setIsValidatingAll(false);
    }
  };

  // 6. Business Website Sitemap Watcher
  const handleWatchBusiness = async () => {
    try {
      setNotice("Scanning business sitemap accident.innovatcs.com...");
      const res = await fetch("http://localhost:8000/api/knowledge/watch-business", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ site_url: "https://accident.innovatcs.com" })
      });
      if (res.ok) {
        const data = await res.json();
        setNotice(`✅ Sitemap scanned: ${data.new_pages_ingested} new, ${data.updated_pages} updated`);
        fetchKnowledge();
      }
    } catch (e) {
      setNotice("Website watch error");
    }
  };

  const displayedList = searchResults || knowledgeList;

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-200 p-6 md:p-8">
      {/* Top Header */}
      <div className="max-w-7xl mx-auto mb-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800 pb-5">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-blue-500/10 text-blue-400 rounded-lg border border-blue-500/20">
              <BookOpen className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">Phase 2 Knowledge Graph & Anti-Hallucination Grounding</h1>
              <p className="text-sm text-gray-400">pgvector(1536) · Entity Triples · Exponential Freshness Decay · True Hybrid Search</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleWatchBusiness}
              className="py-1.5 px-3 bg-gray-900 hover:bg-gray-800 border border-gray-700 text-xs font-semibold rounded-lg text-white transition flex items-center gap-1.5"
              title="Crawl business sitemap for new services and changed pages"
            >
              <Globe className="w-3.5 h-3.5 text-blue-400" /> Watch Sitemap
            </button>
          </div>
        </div>

        {notice && (
          <div className="mt-4 p-3 bg-gray-900 border border-gray-800 rounded-lg text-xs font-mono text-gray-300 flex items-center justify-between">
            <span>{notice}</span>
            <button onClick={() => setNotice(null)} className="text-gray-500 hover:text-white"><X className="w-3.5 h-3.5" /></button>
          </div>
        )}
      </div>

      {/* Main Tabs Navigation */}
      <div className="max-w-7xl mx-auto mb-6 flex items-center justify-between border-b border-gray-800">
        <div className="flex gap-2">
          {[
            { id: "documents", label: "Knowledge Documents", icon: FileText },
            { id: "graph", label: "Knowledge Graph Visualizer", icon: Share2 },
            { id: "validation", label: "Fact-Check & Validation", icon: ShieldCheck },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-2.5 px-4 font-semibold text-xs flex items-center gap-2 border-b-2 transition ${
                activeTab === tab.id
                  ? "border-blue-500 text-white bg-gray-900/30"
                  : "border-transparent text-gray-400 hover:text-gray-200"
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search Mode Toggle */}
        <div className="flex items-center gap-2 py-1">
          <form onSubmit={handleSearch} className="flex items-center gap-1">
            <input
              type="text"
              placeholder={`Search ${searchMode === "hybrid" ? "Hybrid (Vector + Text)" : "Vector Only"}...`}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-gray-950 border border-gray-800 rounded-lg px-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 w-56"
            />
            <button
              type="submit"
              className="py-1.5 px-3 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold"
            >
              <Search className="w-3.5 h-3.5" />
            </button>
          </form>
          <button
            onClick={() => setSearchMode(searchMode === "hybrid" ? "vector" : "hybrid")}
            className="py-1.5 px-2.5 bg-gray-900 hover:bg-gray-800 border border-gray-800 rounded-lg text-[11px] font-mono text-gray-300"
            title="Toggle between Hybrid and Vector Search"
          >
            {searchMode === "hybrid" ? "⚡ Hybrid Mode" : "🎯 Vector Mode"}
          </button>
        </div>
      </div>

      {/* TAB 1: DOCUMENTS */}
      {activeTab === "documents" && (
        <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left 2 Cols: Knowledge Table */}
          <div className="lg:col-span-2 bg-gray-900/80 border border-gray-800 rounded-xl p-5 shadow-xl">
            <div className="flex items-center justify-between border-b border-gray-800 pb-3 mb-4">
              <span className="text-xs font-semibold text-white">Verified Ground Context ({displayedList.length} chunks)</span>
              <div className="flex items-center gap-1">
                {["all", "business_info", "service", "location", "law_statute", "competitor"].map((t) => (
                  <button
                    key={t}
                    onClick={() => { setSelectedType(t); setSearchResults(null); }}
                    className={`py-0.5 px-2 rounded text-[10px] font-mono transition border ${
                      selectedType === t
                        ? "bg-blue-600 text-white border-blue-500"
                        : "bg-gray-950 text-gray-400 border-gray-800"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            {loading ? (
              <div className="py-12 text-center text-xs text-gray-500 font-mono">Loading knowledge chunks...</div>
            ) : displayedList.length === 0 ? (
              <div className="py-12 text-center text-xs text-gray-500">No knowledge chunks found. Upload business facts on the right.</div>
            ) : (
              <div className="space-y-3">
                {displayedList.map((item) => (
                  <div key={item.id} className="bg-gray-950 border border-gray-800/90 rounded-xl p-4 hover:border-gray-700 transition">
                    <div className="flex items-center justify-between gap-2 mb-2 flex-wrap">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                          {item.type}
                        </span>
                        <h4 className="text-xs font-bold text-white">{item.title}</h4>
                      </div>

                      <div className="flex items-center gap-2">
                        {item.validated ? (
                          <span className="text-[10px] text-emerald-400 flex items-center gap-1 font-mono">
                            <CheckCircle2 className="w-3 h-3" /> Validated
                          </span>
                        ) : (
                          <span className="text-[10px] text-amber-400 flex items-center gap-1 font-mono">
                            <AlertTriangle className="w-3 h-3" /> Unvalidated
                          </span>
                        )}
                        <span className="text-[10px] text-gray-400 font-mono bg-gray-900 px-1.5 py-0.5 rounded border border-gray-800">
                          Cred: {item.credibility_score || 1.0}
                        </span>
                        <span className="text-[10px] text-gray-400 font-mono bg-gray-900 px-1.5 py-0.5 rounded border border-gray-800">
                          Fresh: {Math.round((item.freshness_score || 1.0) * 100)}%
                        </span>
                      </div>
                    </div>

                    <p className="text-xs text-gray-300 font-mono bg-gray-900/40 p-2.5 rounded border border-gray-800/50 leading-relaxed mb-2">
                      {item.content}
                    </p>

                    {/* Entities Tags */}
                    {item.entities && (
                      <div className="flex items-center gap-1.5 flex-wrap pt-1">
                        <span className="text-[10px] text-gray-500 font-semibold">Entities:</span>
                        {(item.entities.locations || []).map((loc, i) => (
                          <span key={i} className="text-[9px] px-1.5 py-0.5 bg-purple-950/50 text-purple-300 rounded border border-purple-800/40">
                            📍 {loc}
                          </span>
                        ))}
                        {(item.entities.services || []).map((srv, i) => (
                          <span key={i} className="text-[9px] px-1.5 py-0.5 bg-emerald-950/50 text-emerald-300 rounded border border-emerald-800/40">
                            ⚖️ {srv}
                          </span>
                        ))}
                        {(item.entities.laws || []).map((law, i) => (
                          <span key={i} className="text-[9px] px-1.5 py-0.5 bg-amber-950/50 text-amber-300 rounded border border-amber-800/40">
                            📜 {law}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Right Col: Ingest Upload Form */}
          <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 shadow-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between border-b border-gray-800 pb-3 mb-4">
                <span className="text-xs font-semibold text-white">Ingest Knowledge</span>
                <div className="flex gap-1">
                  {["text", "url", "competitor"].map((m) => (
                    <button
                      key={m}
                      onClick={() => setUploadMode(m)}
                      className={`py-0.5 px-2 rounded text-[10px] font-mono transition border ${
                        uploadMode === m ? "bg-blue-600 text-white border-blue-500" : "bg-gray-950 text-gray-400 border-gray-800"
                      }`}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              </div>

              <form onSubmit={handleIngest} className="space-y-3">
                {uploadMode === "text" && (
                  <>
                    <div>
                      <label className="block text-[11px] text-gray-400 mb-1 font-semibold">Title</label>
                      <input
                        type="text"
                        placeholder="e.g. Texas Statute of Limitations"
                        value={docTitle}
                        onChange={(e) => setDocTitle(e.target.value)}
                        className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] text-gray-400 mb-1 font-semibold">Classification Type</label>
                      <select
                        value={docType}
                        onChange={(e) => setDocType(e.target.value)}
                        className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500"
                      >
                        {["business_info", "service", "location", "law_statute", "faq", "pricing", "competitor"].map((t) => (
                          <option key={t} value={t}>{t}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] text-gray-400 mb-1 font-semibold">Content</label>
                      <textarea
                        rows={6}
                        placeholder="Paste verified factual details (attorneys, jurisdictions, retainers, case laws)..."
                        value={docContent}
                        onChange={(e) => setDocContent(e.target.value)}
                        className="w-full bg-gray-950 border border-gray-800 rounded-lg p-3 text-xs text-white font-mono focus:outline-none focus:border-blue-500 leading-relaxed"
                      />
                    </div>
                  </>
                )}

                {(uploadMode === "url" || uploadMode === "competitor") && (
                  <div>
                    <label className="block text-[11px] text-gray-400 mb-1 font-semibold">Target URL to Scrape</label>
                    <input
                      type="url"
                      placeholder="https://..."
                      value={urlInput}
                      onChange={(e) => setUrlInput(e.target.value)}
                      className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500"
                      required
                    />
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition flex items-center justify-center gap-1.5 shadow-lg shadow-blue-900/30"
                >
                  <Upload className="w-3.5 h-3.5" />
                  {isSubmitting ? "Ingesting & Chunking..." : "Ingest & Extract Entities"}
                </button>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: GRAPH VISUALIZER */}
      {activeTab === "graph" && (
        <div className="max-w-7xl mx-auto h-[600px] bg-[#090d13] border border-gray-800 rounded-xl overflow-hidden relative shadow-2xl">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={(evt, node) => setSelectedNodeData(node.data)}
            nodeTypes={nodeTypes}
            fitView
          >
            <Controls className="!bg-gray-900 !border-gray-800 !text-white" />
            <MiniMap maskColor="rgba(13, 17, 23, 0.8)" className="!bg-gray-950 !border-gray-800" />
            <Background color="#1f2937" gap={16} size={1} />
          </ReactFlow>

          {/* Node details slide-over if clicked */}
          {selectedNodeData && (
            <div className="absolute top-4 right-4 w-80 bg-gray-950/95 border border-gray-800 rounded-xl p-4 shadow-2xl backdrop-blur-md z-10 text-xs">
              <div className="flex items-center justify-between border-b border-gray-800 pb-2 mb-2">
                <span className="font-bold text-white truncate">{selectedNodeData.title}</span>
                <button onClick={() => setSelectedNodeData(null)} className="text-gray-500 hover:text-white"><X className="w-4 h-4" /></button>
              </div>
              <div className="space-y-2 font-mono">
                <div>Type: <span className="text-blue-400">{selectedNodeData.type}</span></div>
                <div>Credibility: <span className="text-white">{selectedNodeData.credibility}</span></div>
                <div>Freshness: <span className="text-white">{Math.round(selectedNodeData.freshness * 100)}%</span></div>
                <div>Validated: <span className={selectedNodeData.validated ? "text-emerald-400" : "text-amber-400"}>{selectedNodeData.validated ? "Yes" : "No"}</span></div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: VALIDATION */}
      {activeTab === "validation" && (
        <div className="max-w-7xl mx-auto bg-gray-900/80 border border-gray-800 rounded-xl p-6 shadow-xl">
          <div className="flex items-center justify-between border-b border-gray-800 pb-4 mb-6">
            <div>
              <h3 className="font-bold text-sm text-white">Fact-Checking & Validation Engine</h3>
              <p className="text-xs text-gray-400">Ensures 100% legal statute accuracy and eliminates hallucinations before writing</p>
            </div>
            <button
              onClick={handleValidateAll}
              disabled={isValidatingAll}
              className="py-1.5 px-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition flex items-center gap-1.5 shadow-lg shadow-emerald-900/30"
            >
              <ShieldCheck className="w-4 h-4" />
              {isValidatingAll ? "Fact-Checking with NIM..." : "Validate All Unvalidated"}
            </button>
          </div>

          <div className="space-y-3">
            {knowledgeList.map((doc) => (
              <div key={doc.id} className="bg-gray-950 border border-gray-800 rounded-xl p-4 flex items-center justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold text-white">{doc.title}</span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-gray-900 text-gray-400 border border-gray-800">
                      {doc.type}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 truncate max-w-xl font-mono">{doc.content}</p>
                </div>

                <div className="flex items-center gap-3">
                  {doc.validated ? (
                    <span className="text-xs font-bold text-emerald-400 flex items-center gap-1 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/30">
                      <Check className="w-3.5 h-3.5" /> Score: {Math.round((doc.validation_score || 0.95) * 100)}%
                    </span>
                  ) : (
                    <button
                      onClick={() => handleValidateSingle(doc.id)}
                      className="py-1 px-3 bg-gray-800 hover:bg-blue-600 text-gray-200 rounded text-xs font-medium transition"
                    >
                      Fact-Check Now
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
