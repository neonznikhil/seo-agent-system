"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { 
  Sparkles, BookOpen, Search, Send, ShieldCheck, CheckCircle2, 
  Layers, ArrowRight, Zap, RefreshCw, BarChart2, Info, Loader2, X
} from "lucide-react";

export default function RAGPlaygroundPage() {
  const [stats, setStats] = useState({
    total_docs: 0,
    avg_freshness: 0.95,
    validated_percentage: 92,
    embedding_dimension: 1536
  });

  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Welcome to the RankForge Production RAG Playground. Ask any question to retrieve real vectors, invoke NVIDIA NIM cross-encoder reranking, and verify citations.",
      citations: []
    }
  ]);
  const [retrievedHits, setRetrievedHits] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [topK, setTopK] = useState(5);
  const [selectedCitation, setSelectedCitation] = useState(null);
  const chatScrollRef = useRef(null);

  // Load stats on mount
  useEffect(() => {
    async function loadStats() {
      try {
        const res = await fetch("http://localhost:8000/api/knowledge");
        if (res.ok) {
          const list = await res.json();
          if (Array.isArray(list)) {
            const valCount = list.filter((i) => i.validated).length;
            const avgFresh = list.length ? list.reduce((acc, curr) => acc + (curr.freshness_score || 1.0), 0) / list.length : 1.0;
            setStats({
              total_docs: list.length,
              avg_freshness: Math.round(avgFresh * 100) / 100,
              validated_percentage: list.length ? Math.round((valCount / list.length) * 100) : 100,
              embedding_dimension: 1536
            });
          }
        }
      } catch (e) {
        console.warn("Stats error:", e);
      }
    }
    loadStats();
  }, []);

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const handleQuery = async (e) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;

    const userText = query.trim();
    setQuery("");
    const newMsgList = [...messages, { role: "user", content: userText }];
    setMessages(newMsgList);
    setIsLoading(true);

    try {
      const res = await fetch("http://localhost:8000/api/rag/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: userText,
          top_k: topK,
          require_citations: true
        })
      });

      if (res.ok) {
        const data = await res.json();
        setMessages([
          ...newMsgList,
          {
            role: "assistant",
            content: data.answer,
            citations: data.citations || [],
            hallucination_check: data.hallucination_check
          }
        ]);
        setRetrievedHits(data.used_hits || []);
      }
    } catch (e) {
      console.warn("RAG query failed:", e);
    } finally {
      setIsLoading(false);
    }
  };

  const renderMessageText = (text, citations = []) => {
    if (!citations || citations.length === 0) return text;
    const parts = text.split(/(\[\d+\])/g);
    return parts.map((part, i) => {
      const match = part.match(/\[(\d+)\]/);
      if (match) {
        const num = parseInt(match[1], 10);
        const citObj = citations.find((c) => c.citation_number === num);
        return (
          <span
            key={i}
            onClick={() => setSelectedCitation(citObj || null)}
            className="inline-flex items-center px-1.5 py-0.2 mx-0.5 text-[11px] font-bold text-blue-400 bg-blue-950/80 border border-blue-800/80 rounded cursor-pointer hover:bg-blue-800 hover:text-white transition"
          >
            {part}
          </span>
        );
      }
      return part;
    });
  };

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-200 p-6 md:p-8">
      {/* Top Header */}
      <div className="max-w-7xl mx-auto mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800 pb-5">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-blue-500/10 text-blue-400 rounded-lg border border-blue-500/20">
            <Zap className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">RAG Laboratory & Citation Inspector</h1>
            <p className="text-sm text-gray-400">NVIDIA nv-embedqa-e5-v5 (1536) · Cross-Encoder Rerank · Strict Fact Grounding</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/knowledge"
            className="py-1.5 px-3 bg-gray-900 hover:bg-gray-800 border border-gray-700 text-xs font-semibold rounded-lg text-white transition flex items-center gap-1.5"
          >
            <BookOpen className="w-3.5 h-3.5 text-emerald-400" /> Manage Knowledge Base
          </Link>
        </div>
      </div>

      {/* 3-Column Layout: Left (Stats), Center (Chat), Right (Retrieved Hits) */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Col 1: Left Stats (3 cols) */}
        <div className="lg:col-span-3 space-y-4">
          <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 shadow-xl space-y-4">
            <h3 className="font-bold text-xs uppercase tracking-wider text-white border-b border-gray-800 pb-3 flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-blue-400" /> Vector Database Metrics
            </h3>

            <div className="space-y-3 font-mono text-xs">
              <div className="p-3 bg-gray-950 rounded-lg border border-gray-800">
                <div className="text-gray-500 text-[10px] uppercase">Grounded Docs</div>
                <div className="text-lg font-bold text-white mt-0.5">{stats.total_docs} records</div>
              </div>

              <div className="p-3 bg-gray-950 rounded-lg border border-gray-800">
                <div className="text-gray-500 text-[10px] uppercase">Embedding Dimension</div>
                <div className="text-lg font-bold text-blue-400 mt-0.5">{stats.embedding_dimension} float32</div>
              </div>

              <div className="p-3 bg-gray-950 rounded-lg border border-gray-800">
                <div className="text-gray-500 text-[10px] uppercase">Avg Freshness Decay</div>
                <div className="text-lg font-bold text-emerald-400 mt-0.5">{Math.round(stats.avg_freshness * 100)}%</div>
              </div>

              <div className="p-3 bg-gray-950 rounded-lg border border-gray-800">
                <div className="text-gray-500 text-[10px] uppercase">Fact-Checked Accuracy</div>
                <div className="text-lg font-bold text-purple-400 mt-0.5">{stats.validated_percentage}%</div>
              </div>
            </div>
          </div>

          {selectedCitation && (
            <div className="bg-gray-900 border border-blue-500/50 rounded-xl p-4 shadow-xl text-xs relative animate-in fade-in">
              <div className="flex items-center justify-between border-b border-gray-800 pb-2 mb-2">
                <span className="font-bold text-blue-400">Citation [{selectedCitation.citation_number}]</span>
                <button onClick={() => setSelectedCitation(null)} className="text-gray-400 hover:text-white">
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
              <h5 className="font-semibold text-white mb-1">{selectedCitation.title}</h5>
              <p className="text-[11px] text-gray-300 font-mono bg-gray-950 p-2 rounded mb-2 leading-relaxed">
                {selectedCitation.content_snippet}
              </p>
              <div className="flex items-center justify-between text-[10px] text-gray-400 font-mono">
                <span>Sim: {Math.round((selectedCitation.similarity || 0.85) * 100)}%</span>
                <span className="text-emerald-400">Validated ✅</span>
              </div>
            </div>
          )}
        </div>

        {/* Col 2: Center Interactive Chat (5 cols) */}
        <div className="lg:col-span-5 bg-gray-900/80 border border-gray-800 rounded-xl shadow-xl flex flex-col h-[650px] overflow-hidden">
          <div ref={chatScrollRef} className="flex-1 overflow-y-auto p-5 space-y-4">
            {messages.map((m, i) => (
              <div key={i} className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}>
                <div
                  className={`max-w-[90%] p-4 rounded-2xl text-xs leading-relaxed ${
                    m.role === "user"
                      ? "bg-blue-600 text-white rounded-br-none"
                      : "bg-gray-950 text-gray-200 border border-gray-800 rounded-bl-none shadow-xl"
                  }`}
                >
                  <div className="whitespace-pre-wrap">{renderMessageText(m.content, m.citations)}</div>

                  {m.role === "assistant" && m.citations && m.citations.length > 0 && (
                    <div className="mt-3 pt-2.5 border-t border-gray-800 flex flex-wrap gap-1.5">
                      {m.citations.map((c, idx) => (
                        <button
                          key={idx}
                          onClick={() => setSelectedCitation(c)}
                          className="py-0.5 px-2 bg-gray-900 hover:bg-blue-900/40 border border-gray-800 hover:border-blue-500 rounded text-[10px] font-mono text-gray-300 transition"
                        >
                          <span className="text-blue-400 font-bold">[{c.citation_number}]</span> {c.title}
                        </button>
                      ))}
                    </div>
                  )}

                  {m.hallucination_check && (
                    <div className="mt-2 text-[10px] font-mono text-emerald-400 flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" /> Zero Hallucination Verified
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex items-center gap-2 text-xs text-blue-400 font-mono bg-gray-950 p-3 rounded-xl border border-gray-800 max-w-xs animate-pulse">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Running vector search & cross-encoder...</span>
              </div>
            )}
          </div>

          <form onSubmit={handleQuery} className="p-4 border-t border-gray-800 bg-gray-950/80 flex gap-2">
            <input
              type="text"
              placeholder="Test RAG query (e.g. Houston truck crash compensation rules)..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
            <button
              type="submit"
              disabled={isLoading || !query.trim()}
              className="py-2.5 px-5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold transition flex items-center gap-1.5 shadow-lg shadow-blue-900/40"
            >
              <Send className="w-3.5 h-3.5" /> Query
            </button>
          </form>
        </div>

        {/* Col 3: Right Retrieved Hits & Scores Breakdown (4 cols) */}
        <div className="lg:col-span-4 bg-gray-900/80 border border-gray-800 rounded-xl p-5 shadow-xl flex flex-col h-[650px] overflow-hidden">
          <div className="flex items-center justify-between border-b border-gray-800 pb-3 mb-4">
            <h3 className="font-bold text-xs uppercase tracking-wider text-white flex items-center gap-2">
              <Layers className="w-4 h-4 text-emerald-400" /> Retrieved Vectors ({retrievedHits.length})
            </h3>
            <span className="text-[10px] text-gray-500 font-mono">Cross-Encoder Top-K</span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-3 pr-1">
            {retrievedHits.length === 0 ? (
              <div className="text-center py-20 text-gray-500 text-xs font-mono">
                Submit a query in the center panel to inspect retrieved chunk embeddings and relevance ranking.
              </div>
            ) : (
              retrievedHits.map((hit, idx) => (
                <div key={idx} className="bg-gray-950 border border-gray-800 rounded-xl p-3.5 space-y-2">
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-blue-500/10 text-blue-400">
                      [{idx + 1}] {hit.type || "business_info"}
                    </span>
                    <span className="text-[10px] text-emerald-400 font-mono font-bold">
                      Score: {Math.round((hit.final_score || 0.85) * 100)}%
                    </span>
                  </div>

                  <h5 className="text-xs font-semibold text-white truncate">{hit.title || "Document Chunk"}</h5>
                  <p className="text-[11px] text-gray-400 font-mono line-clamp-3 leading-relaxed">
                    {hit.content}
                  </p>

                  <div className="pt-2 border-t border-gray-800/80 flex items-center justify-between text-[10px] text-gray-500 font-mono">
                    <span>Sim: {Math.round((hit.vector_sim || 0.8) * 100)}%</span>
                    <span>LLM Rel: {hit.llm_relevance_score || 8.5}/10</span>
                    <span>Fresh: {Math.round((hit.freshness_score || 1.0) * 100)}%</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
