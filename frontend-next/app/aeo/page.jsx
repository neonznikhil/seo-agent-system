"use client";

import React, { useState, useEffect } from "react";
import { 
  Sparkles, Bot, CheckCircle2, XCircle, Code2, Globe, Search, 
  Send, Layers, BarChart3, ShieldCheck, Zap, ArrowRight, ExternalLink,
  Cpu, Copy, Check
} from "lucide-react";

export default function AEOPage() {
  const [citations, setCitations] = useState([]);
  const [sovData, setSovData] = useState({ share_of_voice_percentage: 68.4, total_queries_audited: 12, brand_citations: 8, ai_readiness_score: 94 });
  const [entityGraph, setEntityGraph] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tracking, setTracking] = useState(false);
  const [customQuery, setCustomQuery] = useState("");
  
  // Schema Injector state
  const [schemaType, setSchemaType] = useState("FAQPage");
  const [injecting, setInjecting] = useState(false);
  const [injectedResult, setInjectedResult] = useState(null);

  // BLUF Formatter state
  const [blufTopic, setBlufTopic] = useState("Houston Car Accident Comparative Negligence");
  const [blufContent, setBlufContent] = useState("In Texas, under the modified comparative negligence rule (proportionate responsibility), a plaintiff can recover damages as long as their fault is 50% or less. If they are 51% or more at fault, they cannot recover any compensation. If they are 20% at fault and damages are $100,000, their recovery is reduced by 20% to $80,000.");
  const [blufOutput, setBlufOutput] = useState("");
  const [formattingBluf, setFormattingBluf] = useState(false);

  useEffect(() => {
    loadAEOData();
  }, []);

  const loadAEOData = async () => {
    setLoading(true);
    try {
      const [citRes, sovRes, entRes] = await Promise.all([
        fetch("http://localhost:8000/api/aeo/citations"),
        fetch("http://localhost:8000/api/aeo/sov"),
        fetch("http://localhost:8000/api/aeo/entity-graph"),
      ]);

      if (citRes.ok) {
        const data = await citRes.json();
        setCitations(Array.isArray(data) ? data : []);
      }
      if (sovRes.ok) {
        const sData = await sovRes.json();
        setSovData(sData);
      }
      if (entRes.ok) {
        const eData = await entRes.json();
        setEntityGraph(eData);
      }
    } catch (e) {
      console.warn("AEO data fetch error:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleRunTracking = async (e) => {
    e.preventDefault();
    const queryToRun = customQuery.trim() || "What is the safest accident lawyer in Houston?";
    setTracking(true);
    try {
      const res = await fetch("http://localhost:8000/api/aeo/track", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: queryToRun }),
      });
      if (res.ok) {
        setCustomQuery("");
        loadAEOData();
      }
    } catch (e) {
      console.warn("Tracking query error:", e);
    } finally {
      setTracking(false);
    }
  };

  const handleInjectSchema = async () => {
    setInjecting(true);
    try {
      const res = await fetch("http://localhost:8000/api/aeo/inject-schema", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ schema_type: schemaType }),
      });
      if (res.ok) {
        const data = await res.json();
        setInjectedResult(data);
      }
    } catch (e) {
      console.warn("Schema injection error:", e);
    } finally {
      setInjecting(false);
    }
  };

  const handleFormatBluf = async () => {
    if (!blufContent.trim()) return;
    setFormattingBluf(true);
    try {
      const res = await fetch("http://localhost:8000/api/aeo/format-bluf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: blufTopic, content: blufContent }),
      });
      if (res.ok) {
        const data = await res.json();
        setBlufOutput(data.bluf_formatted);
      }
    } catch (e) {
      console.warn("BLUF format error:", e);
    } finally {
      setFormattingBluf(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-200 p-6 md:p-8">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800 pb-6">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-purple-500/10 text-purple-400 rounded-lg border border-purple-500/20">
              <Sparkles className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">4-Module Answer Engine Optimization (AEO)</h1>
              <p className="text-sm text-gray-400">LLM Citation Tracking · Entity Knowledge Graph · BLUF Direct Answers · JSON-LD Schema Injection</p>
            </div>
          </div>

          <form onSubmit={handleRunTracking} className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Query LLM buyer intent..."
              value={customQuery}
              onChange={(e) => setCustomQuery(e.target.value)}
              className="bg-gray-900 border border-gray-800 rounded-lg px-3.5 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 w-64"
            />
            <button
              type="submit"
              disabled={tracking}
              className="py-1.5 px-4 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-xs font-semibold transition flex items-center gap-1.5 shadow-lg shadow-purple-900/30"
            >
              <Bot className="w-3.5 h-3.5" />
              {tracking ? "Querying LLMs..." : "Track LLM Citation"}
            </button>
          </form>
        </div>
      </div>

      {/* 4 Stats Cards */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">AI Share of Voice (SoV)</span>
            <BarChart3 className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-2xl font-bold text-purple-300 mb-1">{sovData.share_of_voice_percentage}%</div>
          <p className="text-[11px] text-gray-500">Brand cited in buyer-intent prompts</p>
        </div>

        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">AI Citation Readiness</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-300 mb-1">{sovData.ai_readiness_score}/100</div>
          <p className="text-[11px] text-gray-500">BLUF & structured fact compliance</p>
        </div>

        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Buyer Intent Queries</span>
            <Search className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">{sovData.total_queries_audited}</div>
          <p className="text-[11px] text-gray-500">Perplexity & ChatGPT simulations</p>
        </div>

        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 shadow-lg">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Direct Citations</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 mb-1">{sovData.brand_citations}</div>
          <p className="text-[11px] text-gray-500">Innovatcs cited as verified source</p>
        </div>
      </div>

      {/* Main Grid: Citations Table + Interactive Tools */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Left 2 Cols: LLM Citations Tracker */}
        <div className="lg:col-span-2 bg-gray-900/80 border border-gray-800 rounded-xl p-6 shadow-xl">
          <div className="flex items-center justify-between border-b border-gray-800 pb-4 mb-4">
            <div className="flex items-center gap-2">
              <Bot className="w-4 h-4 text-purple-400" />
              <h3 className="font-semibold text-sm text-white">Live LLM Citation Tracking Matrix</h3>
            </div>
            <span className="text-xs text-gray-500 font-mono">Perplexity · Claude · ChatGPT</span>
          </div>

          {loading ? (
            <div className="py-12 text-center text-xs text-gray-500 font-mono">
              Analyzing AI citations and query responses...
            </div>
          ) : (
            <div className="space-y-3">
              {citations.map((c) => (
                <div
                  key={c.id}
                  className="bg-gray-950 border border-gray-800/80 rounded-xl p-4 hover:border-gray-700 transition"
                >
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div>
                      <h4 className="text-xs font-semibold text-white">{c.query}</h4>
                      <p className="text-[10px] text-gray-500 font-mono mt-0.5">{c.llm_name}</p>
                    </div>

                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      {c.cited ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded-full">
                          <CheckCircle2 className="w-3 h-3" /> Innovatcs Cited
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 bg-amber-500/10 text-amber-400 border border-amber-500/30 rounded-full">
                          <XCircle className="w-3 h-3" /> Missing
                        </span>
                      )}
                    </div>
                  </div>

                  <p className="text-xs text-gray-300 font-mono bg-gray-900/50 p-2.5 rounded border border-gray-800/60 leading-relaxed">
                    "{c.citation_snippet}"
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Col: Entity Knowledge Graph Preview */}
        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-6 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 border-b border-gray-800 pb-4 mb-4">
              <Globe className="w-4 h-4 text-blue-400" />
              <h3 className="font-semibold text-sm text-white">Entity Knowledge Graph</h3>
            </div>

            <div className="bg-gray-950 p-4 rounded-xl border border-gray-800 font-mono text-xs text-gray-300 space-y-2">
              <div className="text-blue-400 font-semibold">@type: LegalService</div>
              <div>Name: Innovatcs Legal Advisors</div>
              <div>Jurisdiction: Houston, Texas (Q16555)</div>
              <div>Entity Status: Verified Entity Node</div>
              <div className="text-[11px] text-gray-500 pt-2 border-t border-gray-800">
                Connected to Wikidata & Google Knowledge Graph
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-gray-800">
            <button
              onClick={handleInjectSchema}
              disabled={injecting}
              className="w-full py-2.5 px-4 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-xs font-semibold transition flex items-center justify-center gap-2 shadow-lg shadow-purple-900/30"
            >
              <Code2 className="w-4 h-4" />
              {injecting ? "Deploying Schema..." : "Deploy Live JSON-LD Schema"}
            </button>
            {injectedResult && (
              <p className="text-center text-[11px] text-emerald-400 mt-2 flex items-center justify-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" /> {injectedResult.message}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Section: Interactive BLUF Formatter Tool */}
      <div className="max-w-7xl mx-auto bg-gray-900/80 border border-gray-800 rounded-xl p-6 shadow-xl">
        <div className="flex items-center gap-2 border-b border-gray-800 pb-4 mb-4">
          <Cpu className="w-4 h-4 text-emerald-400" />
          <h3 className="font-semibold text-sm text-white">Answer Formatting Engine: BLUF Conclusion-First Converter</h3>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1">Target Search Intent Topic</label>
            <input
              type="text"
              value={blufTopic}
              onChange={(e) => setBlufTopic(e.target.value)}
              className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2 text-xs text-white mb-3 focus:outline-none focus:border-emerald-500"
            />
            <label className="block text-xs font-medium text-gray-400 mb-1">Raw Unstructured Text</label>
            <textarea
              rows={5}
              value={blufContent}
              onChange={(e) => setBlufContent(e.target.value)}
              className="w-full bg-gray-950 border border-gray-800 rounded-lg p-3 text-xs text-white font-mono focus:outline-none focus:border-emerald-500 leading-relaxed"
            />
            <button
              onClick={handleFormatBluf}
              disabled={formattingBluf}
              className="mt-3 py-2 px-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition flex items-center gap-1.5 shadow-lg shadow-emerald-900/30"
            >
              <Sparkles className="w-3.5 h-3.5" />
              {formattingBluf ? "Synthesizing BLUF..." : "Convert to BLUF Direct Answer"}
            </button>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1">Generated AEO Answer Block (LLM-Optimized)</label>
            <div className="w-full bg-gray-950 border border-gray-800 rounded-lg p-4 font-mono text-xs text-gray-200 min-h-[175px] whitespace-pre-wrap leading-relaxed">
              {blufOutput || "Click 'Convert to BLUF Direct Answer' to generate conclusion-first structured response for AI search engines."}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
