"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface AgentDef {
  id: string;
  name: string;
  role: string;
  category: string;
  description: string;
  // Real runtime stats joined from the tasks table
  runtime_state?: "ACTIVE" | "IDLE" | "ERROR";
  last_run?: string | null;
  last_run_status?: string | null;
  last_run_summary?: string | null;
  last_error?: string | null;
  runs_last_7d?: number;
  next_scheduled_run?: string | null;
}

function stateBadgeClass(state?: string) {
  if (state === "ACTIVE") return "badge-green";
  if (state === "ERROR") return "badge-red";
  return "badge-amber";
}

export default function WorkforcePage() {
  const [websiteId, setWebsiteId] = useState<string>("");
  const [agents, setAgents] = useState<AgentDef[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentDef | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [isRunningAgent, setIsRunningAgent] = useState<boolean>(false);
  const [agentPrompt, setAgentPrompt] = useState<string>("");

  // NVIDIA NIM availability banner
  const [nimStatus, setNimStatus] = useState<{ available: boolean; diagnostic?: string } | null>(null);

  // Real thought stream
  const [thoughts, setThoughts] = useState<Array<{ thought: string; created_at?: string }>>([]);
  const sseRef = useRef<EventSource | null>(null);
  const thoughtBottomRef = useRef<HTMLDivElement | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 4000);
  };

  const loadWorkforce = useCallback(async () => {
    const wid = getCurrentWebsiteId() || "";
    setWebsiteId(wid);
    try {
      const res = await get(`/api/workforce?website_id=${wid}`);
      if (res && Array.isArray(res.agents)) {
        setAgents(res.agents);
        setSelectedAgent((prev) => res.agents.find((a: AgentDef) => a.id === prev?.id) || res.agents[0]);
      }
    } catch {}
    try {
      const nim = await get("/api/workforce/nim-status");
      setNimStatus(nim);
    } catch {}
  }, []);

  useEffect(() => {
    loadWorkforce();
  }, [loadWorkforce]);

  // Subscribe to the real agent thought stream when an agent is selected
  useEffect(() => {
    if (!selectedAgent) return;
    if (sseRef.current) sseRef.current.close();
    setThoughts([]);

    try {
      const source = new EventSource(
        `${(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "")}/api/workforce/agents/${selectedAgent.id}/thoughts/stream`,
      );
      source.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event === "thought" && data.thought) {
            setThoughts((prev) => [...prev.slice(-50), { thought: data.thought, created_at: data.created_at }]);
          }
        } catch {}
      };
      source.onerror = () => source.close();
      sseRef.current = source;
      return () => source.close();
    } catch {}
  }, [selectedAgent?.id]);

  useEffect(() => {
    if (thoughts.length && thoughtBottomRef.current) {
      thoughtBottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [thoughts]);

  const handleRunAgent = async () => {
    if (!selectedAgent) return;
    try {
      setIsRunningAgent(true);
      showToast(`Dispatching ${selectedAgent.name}...`);
      setThoughts((prev) => [...prev, { thought: `[${new Date().toLocaleTimeString()}] Triggered by user — executing now...` }]);

      const res = await post(`/api/workforce/${selectedAgent.id}/run`, {
        website_id: getCurrentWebsiteId() || websiteId || "default",
        instruction: agentPrompt.trim() || `Execute standard cadence for ${selectedAgent.name}`,
      });

      const summaryText =
        res?.summary ||
        res?.message ||
        (res?.result ? `Completed — ${JSON.stringify(res.result).slice(0, 200)}` : "Execution finished.");
      showToast(`✓ ${selectedAgent.name}: ${summaryText}`);
      loadWorkforce();
    } catch (err: any) {
      showToast(`${selectedAgent.name} failed: ${err.message}`);
    } finally {
      setIsRunningAgent(false);
    }
  };

  const filteredAgents = agents.filter((a) => {
    if (selectedCategory === "all") return true;
    return a.category.toLowerCase() === selectedCategory;
  });

  const activeCount = agents.filter((a) => a.runtime_state === "ACTIVE").length;

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
            fontSize: "10.5px",
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

      {/* PAGE HEADER */}
      <div className="page-heading">Autonomous SEO Workforce</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Multi-Agent System · Real Execution Telemetry · Continuous Operation
      </div>

      {/* NIM AVAILABILITY BANNER */}
      {nimStatus && !nimStatus.available && (
        <div className="notice" style={{ borderColor: "var(--red)", background: "rgba(239,68,68,.08)", marginBottom: "16px" }}>
          <span className="notice-sq" style={{ background: "var(--red)" }}></span>
          <div>
            <strong>NVIDIA NIM unavailable</strong> — {nimStatus.diagnostic || "check your API key in Connectors."}
            Agent triggering is disabled until this is resolved.
          </div>
        </div>
      )}

      {/* CATEGORY FILTERS */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "16px", flexWrap: "wrap" }}>
        {[
          { id: "all", label: "All Agents" },
          { id: "core", label: "Core Pipeline" },
          { id: "autonomous", label: "Autonomous Loop" },
          { id: "crewai", label: "CrewAI Specialists" },
          { id: "scheduler", label: "Scheduler" },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`btn ${selectedCategory === tab.id ? "btn-primary" : ""}`}
            onClick={() => setSelectedCategory(tab.id)}
            style={{ fontSize: "9.5px", padding: "6px 12px" }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="grid-2">
        {/* AGENTS LIST — REAL STATUS */}
        <div>
          <div className="panel">
            <div className="panel-head">
              <span className="panel-label">Agent Roster</span>
              <span className={`badge ${activeCount > 0 ? "badge-green" : "badge-amber"}`}>{activeCount}/{agents.length} Active (24h)</span>
            </div>
            <div style={{ padding: "8px 12px", maxHeight: "640px", overflowY: "auto" }}>
              {filteredAgents.length === 0 ? (
                <p style={{ fontSize: "11px", color: "var(--muted)" }}>No agents in this category.</p>
              ) : (
                filteredAgents.map((agent) => (
                  <div
                    key={agent.id}
                    className="agent-row"
                    onClick={() => setSelectedAgent(agent)}
                    title={agent.last_error || agent.last_run_summary || undefined}
                    style={{
                      cursor: "pointer",
                      border: selectedAgent?.id === agent.id ? "1px solid var(--accent)" : "1px solid var(--line)",
                      background: selectedAgent?.id === agent.id ? "var(--bg3)" : "var(--panel-inner)",
                      alignItems: "flex-start",
                    }}
                  >
                    <div>
                      <div className="agent-name" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <span
                          className="live-dot"
                          style={{
                            width: "5px",
                            height: "5px",
                            background:
                              agent.runtime_state === "ACTIVE" ? "var(--green)"
                              : agent.runtime_state === "ERROR" ? "var(--red)"
                              : "#f59e0b",
                          }}
                        ></span>
                        {agent.name}
                      </div>
                      <div className="agent-meta">{agent.role}</div>
                      <div style={{ fontSize: "9.5px", color: "var(--muted)", marginTop: "2px" }}>
                        {agent.last_run_summary
                          ? agent.last_run_summary
                          : agent.last_error
                          ? `Last error: ${agent.last_error.slice(0, 60)}`
                          : "No runs recorded yet"}
                        {agent.next_scheduled_run
                          ? ` · next run ${new Date(agent.next_scheduled_run).toLocaleString()}`
                          : ""}
                      </div>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "4px" }}>
                      <span className={`badge ${stateBadgeClass(agent.runtime_state)}`}>
                        {agent.runtime_state}
                      </span>
                      {agent.runs_last_7d !== undefined && (
                        <span style={{ fontSize: "8.5px", color: "var(--muted)" }}>{agent.runs_last_7d} runs / 7d</span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* AGENT CONSOLE */}
        <div>
          {selectedAgent && (
            <div className="panel">
              <div className="panel-head">
                <span className="panel-label">Console: {selectedAgent.name}</span>
                <span className={`badge ${stateBadgeClass(selectedAgent.runtime_state)}`}>
                  {selectedAgent.runtime_state}
                </span>
              </div>
              <div className="panel-body">
                <div style={{ marginBottom: "14px" }}>
                  <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--ink)", marginBottom: "4px" }}>
                    {selectedAgent.role}
                  </div>
                  <p style={{ fontSize: "11px", color: "var(--muted)", lineHeight: "1.5" }}>
                    {selectedAgent.description}
                  </p>
                </div>

                {/* LAST RUN DETAIL */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "14px", fontSize: "10.5px" }}>
                  <div style={{ padding: "8px", border: "1px solid var(--line)" }}>
                    <div style={{ color: "var(--muted)", textTransform: "uppercase", fontSize: "8.5px" }}>Last Run</div>
                    <div>{selectedAgent.last_run ? new Date(selectedAgent.last_run).toLocaleString() : "Never"}</div>
                  </div>
                  <div style={{ padding: "8px", border: "1px solid var(--line)" }}>
                    <div style={{ color: "var(--muted)", textTransform: "uppercase", fontSize: "8.5px" }}>Next Scheduled</div>
                    <div>{selectedAgent.next_scheduled_run ? new Date(selectedAgent.next_scheduled_run).toLocaleString() : "Not scheduled"}</div>
                  </div>
                </div>

                {selectedAgent.last_error && (
                  <div style={{ color: "var(--red)", fontSize: "10.5px", padding: "8px", border: "1px solid var(--red)", marginBottom: "12px" }}>
                    Last failure: {selectedAgent.last_error}
                  </div>
                )}

                <button
                  type="button"
                  className="btn btn-accent"
                  disabled={isRunningAgent || nimStatus?.available === false}
                  onClick={handleRunAgent}
                  style={{ width: "100%", padding: "9px", marginBottom: "14px", fontWeight: 600 }}
                  title={nimStatus?.available === false ? nimStatus.diagnostic : undefined}
                >
                  {isRunningAgent ? "Executing..." : `Trigger ${selectedAgent.name}`}
                </button>

                {/* REAL THOUGHT STREAM */}
                <div>
                  <label style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", display: "block", marginBottom: "4px" }}>
                    Agent Thought Stream (live)
                  </label>
                  <pre
                    style={{
                      fontFamily: "'IBM Plex Mono', monospace",
                      fontSize: "10.5px",
                      background: "var(--panel-inner)",
                      border: "1px solid var(--border)",
                      padding: "10px",
                      minHeight: "160px",
                      maxHeight: "260px",
                      overflowY: "auto",
                      whiteSpace: "pre-wrap",
                      color: "var(--ink)",
                      margin: 0,
                    }}
                  >
                    {thoughts.length === 0
                      ? "No thoughts recorded yet. Thoughts appear here in real time whenever this agent executes."
                      : thoughts.map((t, i) => `${t.created_at ? `[${new Date(t.created_at).toLocaleTimeString()}] ` : ""}${t.thought}`).join("\n")}
                    <div ref={thoughtBottomRef} />
                  </pre>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* BOTTOM TICKER */}
      <div className="bticker">
        <span className="bticker-inner">
          <span className="bt-sq"></span>WORKFORCE ENGINE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>REAL EXECUTION TELEMETRY <span className="bt-sep">/</span>
          <span className="bt-sq"></span>NVIDIA NIM ORCHESTRATION &nbsp;&nbsp;&nbsp;&nbsp;
          <span className="bt-sq"></span>WORKFORCE ENGINE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>REAL EXECUTION TELEMETRY <span className="bt-sep">/</span>
          <span className="bt-sq"></span>NVIDIA NIM ORCHESTRATION
        </span>
      </div>
    </div>
  );
}
