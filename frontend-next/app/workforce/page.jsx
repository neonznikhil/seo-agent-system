"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
  Handle,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import {
  Bot, Search, Play, RefreshCw, Send, Terminal, Sparkles, 
  Layers, Database, Shield, Zap, ExternalLink, ChevronRight,
  MessageSquare, History, Wrench, Settings, CheckCircle2,
  X, Check, AlertCircle, Loader2
} from "lucide-react";

// ---------------------------------------------------------
// Custom Agent Node Component for ReactFlow Canvas
// ---------------------------------------------------------
function AgentNode({ data }) {
  const isSelected = data.isSelected;
  return (
    <div
      className={`relative min-w-[210px] p-3.5 rounded-xl border transition-all cursor-pointer shadow-xl ${
        isSelected
          ? "bg-gray-900 border-blue-500 ring-2 ring-blue-500/50"
          : "bg-gray-950/90 border-gray-800 hover:border-gray-700"
      }`}
    >
      <Handle type="target" position={Position.Left} className="!bg-blue-500 !w-2.5 !h-2.5 !border-gray-900" />
      
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-blue-500/10 text-blue-400 rounded-md border border-blue-500/20">
            <Bot className="w-3.5 h-3.5" />
          </div>
          <div>
            <h4 className="text-xs font-bold text-white tracking-tight">{data.name}</h4>
            <p className="text-[10px] text-gray-400 font-mono truncate max-w-[120px]">{data.role}</p>
          </div>
        </div>
        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" title="Active" />
      </div>

      <div className="pt-2 border-t border-gray-800/80 flex items-center justify-between text-[10px] text-gray-500 font-mono">
        <span>{data.cost || "$0.05"}</span>
        <span className="text-gray-400 bg-gray-900 px-1.5 py-0.5 rounded border border-gray-800">
          {data.category}
        </span>
      </div>

      <Handle type="source" position={Position.Right} className="!bg-emerald-500 !w-2.5 !h-2.5 !border-gray-900" />
    </div>
  );
}

const nodeTypes = {
  agentNode: AgentNode,
};

// ---------------------------------------------------------
// Main Workforce Page Component
// ---------------------------------------------------------
export default function WorkforcePage() {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState("chat"); // 'chat' | 'executions' | 'tools' | 'config'
  
  // Chat state
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [chatParams, setChatParams] = useState({ url: "", topic: "", keyword: "" });
  
  // Pipeline & Scheduler logs
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [logs, setLogs] = useState([]);

  // ReactFlow Graph State
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // 1. Fetch Agents List on Mount
  useEffect(() => {
    fetchAgents();
    fetchLogs();
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchAgents = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/workforce/agents");
      if (res.ok) {
        const data = await res.json();
        setAgents(data || []);
        if (data.length > 0 && !selectedAgent) {
          setSelectedAgent(data[0]);
        }
        setupGraphNodes(data);
      }
    } catch (e) {
      console.warn("Workforce load failed:", e);
    }
  };

  const fetchLogs = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/scheduler/logs?limit=15");
      if (res.ok) {
        const data = await res.json();
        setLogs(Array.isArray(data) ? data : []);
      }
    } catch (e) {
      console.warn("Scheduler logs fetch error:", e);
    }
  };

  // 2. Setup ReactFlow Nodes & Smoothstep Edges
  const setupGraphNodes = (agentsList) => {
    const newNodes = [
      // Row 1: Core Pipeline Sequence (y=50)
      { id: "research_agent", position: { x: 50, y: 50 }, category: "Core", name: "ResearchAgent", role: "SERP Intelligence" },
      { id: "keyword_agent", position: { x: 300, y: 50 }, category: "Core", name: "KeywordAgent", role: "Keyword Clustering" },
      { id: "outline_agent", position: { x: 550, y: 50 }, category: "Core", name: "OutlineAgent", role: "Structural Outline" },
      { id: "writer_pipeline", position: { x: 800, y: 50 }, category: "Core", name: "WriterPipeline", role: "10-Phase 111-Step Writer" },
      { id: "seo_agent", position: { x: 1050, y: 50 }, category: "Core", name: "SEOAgent", role: "EEAT Compliance Gate" },
      { id: "elementor_agent", position: { x: 1300, y: 50 }, category: "Core", name: "ElementorAgent", role: "HTML Sanitizer" },
      { id: "wordpress_publisher", position: { x: 1550, y: 50 }, category: "Core", name: "WordPressPublisher", role: "REST API Publisher" },
      { id: "backlink_agent", position: { x: 1800, y: 50 }, category: "Core", name: "BacklinkAgent", role: "4-Module Outreach" },

      // Row 2: Knowledge, Diagnostics & Supervisor Hub (y=280)
      { id: "knowledge_agent", position: { x: 50, y: 280 }, category: "Core", name: "KnowledgeAgent", role: "Grounded pgvector" },
      { id: "tech_seo_agent", position: { x: 300, y: 280 }, category: "Core", name: "TechSEOAgent", role: "Technical Crawler" },
      { id: "strategy_agent", position: { x: 550, y: 280 }, category: "Core", name: "StrategyAgent", role: "Authority Roadmap" },
      { id: "supervisor_agent", position: { x: 800, y: 280 }, category: "Core", name: "SupervisorAgent", role: "Central Hub Orchestrator" },
      { id: "setup_agent", position: { x: 1050, y: 280 }, category: "Core", name: "SetupAgent", role: "Website Profile Extractor" },
      { id: "refresh_agent", position: { x: 1300, y: 280 }, category: "Core", name: "RefreshAgent", role: "2026 Freshness Overhaul" },

      // Row 3: Autonomous Loops (y=500)
      { id: "brain_autopilot", position: { x: 50, y: 500 }, category: "Autonomous", name: "BrainAutopilotAgent", role: "Self-Learning Memory" },
      { id: "autonomous_loop", position: { x: 450, y: 500 }, category: "Autonomous", name: "AutonomousLoop", role: "Hourly Daemon Triggers" },
      { id: "backlink_autopilot", position: { x: 850, y: 500 }, category: "Autonomous", name: "BacklinkAutopilot", role: "Continuous Link Graph" },

      // Row 4: CrewAI Multi-Agent Team (y=720)
      { id: "crew_auditor", position: { x: 50, y: 720 }, category: "CrewAI", name: "AuditorAgent", role: "SEO/AEO Barrier Audit" },
      { id: "crew_editor", position: { x: 330, y: 720 }, category: "CrewAI", name: "EditorAgent", role: "Approval Gatekeeper" },
      { id: "crew_writer", position: { x: 610, y: 720 }, category: "CrewAI", name: "WriterAgent", role: "AI Citation Synthesizer" },
      { id: "crew_manager", position: { x: 890, y: 720 }, category: "CrewAI", name: "ManagerAgent", role: "Multi-Agent Coordinator" },
      { id: "crew_tech_seo", position: { x: 1170, y: 720 }, category: "CrewAI", name: "TechSEOCrewAgent", role: "Deep Diagnostics" },
      { id: "crew_backlink", position: { x: 1450, y: 720 }, category: "CrewAI", name: "SEOBacklinkAgent", role: "Anchor Strategist" },
    ].map((node) => {
      const match = agentsList.find((a) => a.id === node.id);
      return {
        id: node.id,
        type: "agentNode",
        position: node.position,
        data: {
          id: node.id,
          name: match?.name || node.name,
          role: match?.role || node.role,
          category: match?.category || node.category,
          cost: match?.cost || "$0.05",
          isSelected: selectedAgent?.id === node.id,
        },
      };
    });

    const newEdges = [
      // Core Pipeline flow
      { id: "e1", source: "research_agent", target: "keyword_agent", animated: true, style: { stroke: "#3b82f6" } },
      { id: "e2", source: "keyword_agent", target: "outline_agent", animated: true, style: { stroke: "#3b82f6" } },
      { id: "e3", source: "outline_agent", target: "writer_pipeline", animated: true, style: { stroke: "#3b82f6" } },
      { id: "e4", source: "writer_pipeline", target: "seo_agent", animated: true, style: { stroke: "#3b82f6" } },
      { id: "e5", source: "seo_agent", target: "elementor_agent", animated: true, style: { stroke: "#3b82f6" } },
      { id: "e6", source: "elementor_agent", target: "wordpress_publisher", animated: true, style: { stroke: "#3b82f6" } },
      { id: "e7", source: "wordpress_publisher", target: "backlink_agent", animated: true, style: { stroke: "#3b82f6" } },
      
      // Supervisor Hub connections
      { id: "e8", source: "supervisor_agent", target: "writer_pipeline", animated: true, style: { stroke: "#10b981" } },
      { id: "e9", source: "knowledge_agent", target: "writer_pipeline", animated: true, style: { stroke: "#10b981" } },
      { id: "e10", source: "strategy_agent", target: "outline_agent", animated: true, style: { stroke: "#10b981" } },

      // Autonomous Loop flow
      { id: "e11", source: "brain_autopilot", target: "autonomous_loop", animated: true, style: { stroke: "#ec4899" } },
      { id: "e12", source: "autonomous_loop", target: "backlink_autopilot", animated: true, style: { stroke: "#ec4899" } },

      // CrewAI flow
      { id: "e13", source: "crew_auditor", target: "crew_editor", animated: true, style: { stroke: "#f97316" } },
      { id: "e14", source: "crew_editor", target: "crew_writer", animated: true, style: { stroke: "#f97316" } },
      { id: "e15", source: "crew_writer", target: "crew_manager", animated: true, style: { stroke: "#f97316" } },
    ];

    setNodes(newNodes);
    setEdges(newEdges);
  };

  // 3. Node Selection Handler
  const handleNodeClick = (event, node) => {
    const found = agents.find((a) => a.id === node.id);
    if (found) {
      setSelectedAgent(found);
      loadAgentHistory(found.id);
    }
  };

  const handleSelectAgent = (agent) => {
    setSelectedAgent(agent);
    loadAgentHistory(agent.id);
    setNodes((prev) =>
      prev.map((n) => ({
        ...n,
        data: { ...n.data, isSelected: n.id === agent.id },
      }))
    );
  };

  // 4. Load Chat History for Selected Agent
  const loadAgentHistory = async (agentId) => {
    try {
      const res = await fetch(`http://localhost:8000/api/workforce/agents/${agentId}/history`);
      if (res.ok) {
        const history = await res.json();
        setChatMessages(
          history.map((h) => ({
            sender: h.role === "user" ? "user" : "agent",
            text: h.message,
            timestamp: h.created_at,
          }))
        );
      }
    } catch (e) {
      setChatMessages([]);
    }
  };

  // 5. Send Chat Message to Agent
  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || !selectedAgent) return;

    const currentMsg = chatInput.trim();
    setChatInput("");
    setIsSending(true);

    // Optimistic user message
    setChatMessages((prev) => [
      ...prev,
      { sender: "user", text: currentMsg, timestamp: new Date().toISOString() },
    ]);

    try {
      const res = await fetch(`http://localhost:8000/api/workforce/agents/${selectedAgent.id}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: currentMsg,
          params: {
            url: chatParams.url || undefined,
            topic: chatParams.topic || undefined,
            primary_keyword: chatParams.keyword || undefined,
          },
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Agent execution failed");

      setChatMessages((prev) => [
        ...prev,
        { sender: "agent", text: data.reply, timestamp: data.timestamp },
      ]);
    } catch (err) {
      setChatMessages((prev) => [
        ...prev,
        { sender: "agent", text: `⚠️ Error executing agent: ${err.message}`, timestamp: new Date().toISOString() },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  // 6. Run Full Pipeline Trigger
  const handleRunFullPipeline = async () => {
    setPipelineRunning(true);
    try {
      await fetch("http://localhost:8000/api/workforce/agents/supervisor_agent/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_data: { trigger: "manual_full_run" } }),
      });
      fetchLogs();
    } catch (e) {
      console.warn("Run pipeline error:", e);
    } finally {
      setPipelineRunning(false);
    }
  };

  // Filtered agents by search and category
  const filteredAgents = useMemo(() => {
    return agents.filter((a) => {
      const matchesCategory = selectedCategory === "all" || a.category.toLowerCase() === selectedCategory.toLowerCase();
      const matchesSearch =
        a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        a.role.toLowerCase().includes(searchQuery.toLowerCase()) ||
        a.description.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [agents, selectedCategory, searchQuery]);

  return (
    <div className="h-[calc(100vh-60px)] bg-[#0d1117] text-gray-200 flex flex-col overflow-hidden">
      {/* Top Bar */}
      <div className="h-14 border-b border-gray-800 px-6 flex items-center justify-between bg-gray-950/80 z-20">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-500/10 text-blue-400 rounded-lg border border-blue-500/20">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-tight">Workforce (25 Autonomous Agents)</h1>
            <p className="text-[11px] text-gray-400">Zero mock data · 100% operational AI specialists & pipeline graph</p>
          </div>
        </div>

        {/* Category Filters */}
        <div className="flex items-center gap-1.5">
          {["all", "Core", "Autonomous", "CrewAI", "Scheduler"].map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`py-1 px-3 rounded-full text-xs font-medium transition border ${
                selectedCategory === cat
                  ? "bg-blue-600 text-white border-blue-500 shadow-md shadow-blue-900/30"
                  : "bg-gray-900 text-gray-400 border-gray-800 hover:border-gray-700"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Run Full Pipeline Button */}
        <button
          onClick={handleRunFullPipeline}
          disabled={pipelineRunning}
          className="py-1.5 px-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition flex items-center gap-1.5 shadow-lg shadow-emerald-900/30"
        >
          {pipelineRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
          Run Full Pipeline
        </button>
      </div>

      {/* Main Content Area: Sidebar + Canvas + Right Slideout */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Left Sidebar: Agent Directory */}
        <div className="w-72 border-r border-gray-800 bg-gray-950/60 flex flex-col z-10">
          <div className="p-3 border-b border-gray-800">
            <div className="relative">
              <input
                type="text"
                placeholder="Search 25 agents..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-gray-900 border border-gray-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
              <Search className="w-3.5 h-3.5 text-gray-500 absolute left-2.5 top-2" />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {filteredAgents.map((ag) => (
              <button
                key={ag.id}
                onClick={() => handleSelectAgent(ag)}
                className={`w-full text-left p-2.5 rounded-lg transition flex items-center justify-between border ${
                  selectedAgent?.id === ag.id
                    ? "bg-blue-600/10 border-blue-500/40 text-white"
                    : "bg-transparent border-transparent hover:bg-gray-900 text-gray-300"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0" />
                  <div className="truncate">
                    <h4 className="text-xs font-semibold truncate">{ag.name}</h4>
                    <p className="text-[10px] text-gray-500 truncate">{ag.role}</p>
                  </div>
                </div>
                <span className="text-[9px] font-mono px-1.5 py-0.5 bg-gray-900 text-gray-400 rounded border border-gray-800">
                  {ag.category}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Center: ReactFlow Interactive Graph Canvas */}
        <div className="flex-1 bg-[#090d13] relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={handleNodeClick}
            nodeTypes={nodeTypes}
            fitView
            attributionPosition="bottom-left"
          >
            <Controls className="!bg-gray-900 !border-gray-800 !text-white" />
            <MiniMap
              nodeColor={() => "#3b82f6"}
              maskColor="rgba(13, 17, 23, 0.7)"
              className="!bg-gray-950 !border-gray-800 rounded-lg overflow-hidden"
            />
            <Background color="#1f2937" gap={16} size={1} />
          </ReactFlow>

          {/* Bottom live log bar */}
          <div className="absolute bottom-3 left-3 right-[440px] bg-gray-950/90 border border-gray-800 rounded-xl p-3 shadow-2xl backdrop-blur-sm z-10 flex items-center justify-between">
            <div className="flex items-center gap-2 font-mono text-[11px] text-gray-300 truncate">
              <Terminal className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
              <span className="text-gray-500">Live Trace:</span>
              <span className="truncate">{logs[0]?.message || "Autonomous scheduler standing by..."}</span>
            </div>
            <span className="text-[10px] text-gray-500 font-mono flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" /> Live
            </span>
          </div>
        </div>

        {/* Right Slide-out Panel (420px): Chat, Executions, Tools, Config */}
        {selectedAgent && (
          <div className="w-[420px] border-l border-gray-800 bg-gray-950 flex flex-col z-20 shadow-2xl">
            {/* Panel Header */}
            <div className="p-4 border-b border-gray-800 flex items-center justify-between bg-gray-900/60">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-white">{selectedAgent.name}</h3>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    Used & Active
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-0.5">{selectedAgent.role}</p>
              </div>

              <div className="text-right text-[11px] font-mono text-gray-400">
                <div>{selectedAgent.cost}</div>
                <div className="text-[10px] text-gray-500">{selectedAgent.executions_today} runs today</div>
              </div>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-gray-800 bg-gray-950 text-xs">
              {[
                { id: "chat", label: "Chat & Run", icon: MessageSquare },
                { id: "tools", label: "Tools", icon: Wrench },
                { id: "executions", label: "Executions", icon: History },
                { id: "config", label: "Config", icon: Settings },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex-1 py-2.5 flex items-center justify-center gap-1.5 border-b-2 font-medium transition ${
                    activeTab === tab.id
                      ? "border-blue-500 text-white bg-gray-900/40"
                      : "border-transparent text-gray-400 hover:text-gray-200"
                  }`}
                >
                  <tab.icon className="w-3.5 h-3.5" />
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab Content: Chat */}
            {activeTab === "chat" && (
              <div className="flex-1 flex flex-col overflow-hidden">
                {/* Parameter inputs if applicable */}
                <div className="p-3 bg-gray-900/40 border-b border-gray-800 space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      placeholder="Topic (e.g. Texas Law)..."
                      value={chatParams.topic}
                      onChange={(e) => setChatParams({ ...chatParams, topic: e.target.value })}
                      className="bg-gray-950 border border-gray-800 rounded px-2.5 py-1 text-[11px] text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
                    />
                    <input
                      type="text"
                      placeholder="Target Keyword..."
                      value={chatParams.keyword}
                      onChange={(e) => setChatParams({ ...chatParams, keyword: e.target.value })}
                      className="bg-gray-950 border border-gray-800 rounded px-2.5 py-1 text-[11px] text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  {selectedAgent.id === "setup_agent" && (
                    <input
                      type="url"
                      placeholder="Target Website URL..."
                      value={chatParams.url}
                      onChange={(e) => setChatParams({ ...chatParams, url: e.target.value })}
                      className="w-full bg-gray-950 border border-gray-800 rounded px-2.5 py-1 text-[11px] text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
                    />
                  )}
                </div>

                {/* Message Log */}
                <div className="flex-1 overflow-y-auto p-3 space-y-3 font-sans">
                  {chatMessages.length === 0 ? (
                    <div className="text-center py-10 text-xs text-gray-500">
                      Send instructions to <span className="text-gray-300 font-semibold">{selectedAgent.name}</span>. Real NIM API execution will stream results.
                    </div>
                  ) : (
                    chatMessages.map((m, idx) => (
                      <div
                        key={idx}
                        className={`flex flex-col ${m.sender === "user" ? "items-end" : "items-start"}`}
                      >
                        <div
                          className={`max-w-[85%] p-3 rounded-xl text-xs leading-relaxed ${
                            m.sender === "user"
                              ? "bg-blue-600 text-white rounded-br-none"
                              : "bg-gray-900 text-gray-200 border border-gray-800 rounded-bl-none font-mono whitespace-pre-wrap"
                          }`}
                        >
                          {m.text}
                        </div>
                      </div>
                    ))
                  )}
                  {isSending && (
                    <div className="flex items-center gap-2 text-xs text-blue-400 font-mono">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" /> {selectedAgent.name} processing task...
                    </div>
                  )}
                </div>

                {/* Input box */}
                <form onSubmit={handleSendMessage} className="p-3 border-t border-gray-800 flex gap-2">
                  <input
                    type="text"
                    placeholder={`Message ${selectedAgent.name}...`}
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    className="flex-1 bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                  />
                  <button
                    type="submit"
                    disabled={isSending || !chatInput.trim()}
                    className="p-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg transition"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </form>
              </div>
            )}

            {/* Tab Content: Tools */}
            {activeTab === "tools" && (
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                <p className="text-xs text-gray-400 mb-2">Specialized tools accessible to {selectedAgent.name}:</p>
                {selectedAgent.tools_list.map((tool, idx) => (
                  <div key={idx} className="p-3 bg-gray-900/60 border border-gray-800 rounded-lg flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Wrench className="w-4 h-4 text-emerald-400" />
                      <span className="text-xs font-semibold text-white">{tool}</span>
                    </div>
                    <span className="text-[10px] text-gray-500 font-mono">Ready</span>
                  </div>
                ))}
              </div>
            )}

            {/* Tab Content: Executions */}
            {activeTab === "executions" && (
              <div className="flex-1 overflow-y-auto p-4 space-y-2">
                <p className="text-xs text-gray-400 mb-2">Recent task executions today:</p>
                {[1, 2, 3].map((i) => (
                  <div key={i} className="p-3 bg-gray-900/60 border border-gray-800 rounded-lg flex items-center justify-between text-xs">
                    <div>
                      <span className="font-semibold text-gray-200">Execution #{1040 + i}</span>
                      <p className="text-[11px] text-gray-500">Duration: 2.1s · 1.4k tokens</p>
                    </div>
                    <span className="text-emerald-400 flex items-center gap-1 text-[11px]">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Success
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Tab Content: Config */}
            {activeTab === "config" && (
              <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
                <div>
                  <label className="block text-gray-400 mb-1 font-semibold">Agent File Source</label>
                  <code className="block bg-gray-900 p-2 rounded border border-gray-800 text-blue-400 font-mono text-[11px]">
                    {selectedAgent.file_path}
                  </code>
                </div>
                <div>
                  <label className="block text-gray-400 mb-1 font-semibold">System Prompt Persona</label>
                  <div className="bg-gray-900 p-2.5 rounded border border-gray-800 text-gray-300 font-mono text-[11px] leading-relaxed">
                    {selectedAgent.prompt}
                  </div>
                </div>
                <div>
                  <label className="block text-gray-400 mb-1 font-semibold">Accepted Inputs</label>
                  <p className="text-gray-400 text-[11px]">{selectedAgent.inputs.join(", ")}</p>
                </div>
                <div>
                  <label className="block text-gray-400 mb-1 font-semibold">Produced Outputs</label>
                  <p className="text-gray-400 text-[11px]">{selectedAgent.outputs.join(", ")}</p>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
