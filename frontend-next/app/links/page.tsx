"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import * as d3 from "d3";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId, setCurrentWebsiteId } from "@/lib/website";

interface GraphNode {
  url: string;
  title: string;
  pagerank: number;
  sessions: number;
  in_degree: number;
  is_orphan: boolean;
}

interface GraphEdge {
  from: string;
  to: string;
  anchor: string;
}

interface Prospect {
  id: string;
  prospect_url: string;
  domain_rating: number | null;
  contact_email: string | null;
  strategy: string;
  reason: string;
  broken_link_url: string | null;
  anchor_suggestion: string | null;
  target_page_url: string;
  target_keyword: string;
  relevance_score: number;
  status: string;
  created_at: string;
}

interface MonitorItem {
  id: string;
  source_url: string;
  backlink_url: string;
  anchor_text: string;
  domain_rating: number | null;
  status_code: number | null;
  status: string;
  checked_at: string;
  first_seen_at: string;
}

interface OutreachDraft {
  id: string;
  prospect_id: string;
  subject: string;
  body: string;
  status: string;
  approved_by: string | null;
  sent_at: string | null;
  created_at: string;
}

interface BrainMemory {
  id: string;
  memory_type: string;
  title: string;
  content: string;
  confidence: number;
  times_used: number;
  times_successful: number;
  last_used_at: string;
  created_at: string;
}

type Tab = "graph" | "prospects" | "monitor" | "outreach" | "brain";

export default function LinksPage() {
  const websiteId = getCurrentWebsiteId();
  const [tab, setTab] = useState<Tab>("graph");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [websites, setWebsites] = useState<any[]>([]);
  const [graph, setGraph] = useState<{ nodes: GraphNode[]; edges: GraphEdge[]; orphans: string[] }>({ nodes: [], edges: [], orphans: [] });
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [monitor, setMonitor] = useState<MonitorItem[]>([]);
  const [outreach, setOutreach] = useState<OutreachDraft[]>([]);
  const [brainMemories, setBrainMemories] = useState<BrainMemory[]>([]);
  const [keyword, setKeyword] = useState("");
  const [targetPage, setTargetPage] = useState("");
  const [suggestUrl, setSuggestUrl] = useState("");
  const [suggestKeyword, setSuggestKeyword] = useState("");
  const [suggestions, setSuggestions] = useState<any>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [showApproveModal, setShowApproveModal] = useState<string | null>(null);
  const [userId, setUserId] = useState(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem("x-user-id") || "";
  });

  const graphRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    localStorage.setItem("x-user-id", userId);
  }, [userId]);

  useEffect(() => {
    async function loadWebsites() {
      try {
        const data = await get("/websites");
        setWebsites(data || []);
      } catch (e) {
        console.error(e);
      }
    }
    loadWebsites();
  }, []);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await get(`/backlinks/${websiteId}`);
      setGraph(data.graph || { nodes: [], edges: [], orphans: [] });
      setProspects(data.prospects || []);
      setMonitor(data.monitor || []);
      setOutreach(data.outreach || []);
      setBrainMemories(data.brain_memories || []);
    } catch (e: any) {
      setError(e.message || "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, [websiteId]);

  useEffect(() => {
    if (tab !== "graph" || !graphRef.current || graph.nodes.length === 0) return;
    const svg = d3.select(graphRef.current);
    svg.selectAll("*").remove();
    const width = graphRef.current.clientWidth || 800;
    const height = 500;

    const simulation = d3
      .forceSimulation(graph.nodes as any[])
      .force("link", d3.forceLink(graph.edges.map((e) => ({ ...e, source: e.from, target: e.to })) as any).id((d: any) => d.url).distance(80))
      .force("charge", d3.forceManyBody().strength(-120))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(16));

    const g = svg.append("g");
    const zoom = d3.zoom<SVGSVGElement, unknown>().scaleExtent([0.2, 3]).on("zoom", (event) => {
      g.attr("transform", event.transform);
    });
    svg.call(zoom as any);

    const link = g
      .append("g")
      .selectAll("line")
      .data(graph.edges.map((e) => ({ ...e, source: e.from, target: e.to })))
      .join("line")
      .attr("stroke", "var(--line)")
      .attr("stroke-width", 1);

    const node = g
      .append("g")
      .selectAll<SVGCircleElement, any>("circle")
      .data(graph.nodes)
      .join("circle")
      .attr("r", (d: any) => Math.max(4, (d.pagerank || 0) * 20))
      .attr("fill", (d: any) => (d.is_orphan ? "#FF4D12" : "var(--ink)"))
      .attr("stroke", "var(--border)")
      .attr("stroke-width", 1)
      .style("cursor", "pointer")
      .call(
        d3.drag<SVGCircleElement, any>()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    node.append("title").text((d: any) => `${d.url}\nPR: ${(d.pagerank || 0).toFixed(3)}\nSessions: ${d.sessions}`);

    node.on("click", (_event, d: any) => {
      window.open(d.url, "_blank");
    });

    simulation.on("tick", () => {
      link
        .attr("x1", (d: any) => d.source.x)
        .attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x)
        .attr("y2", (d: any) => d.target.y);

      node.attr("cx", (d: any) => d.x).attr("cy", (d: any) => d.y);
    });

    return () => {
      simulation.stop();
    };
  }, [graph, tab]);

  const runProspect = async () => {
    if (!keyword.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await post(`/backlinks/${websiteId}/prospect`, {
        primary_keyword: keyword,
        target_page_url: targetPage || undefined,
      });
      setProspects(data.prospects || []);
      setToast(`Found ${(data.prospects || []).length} prospects`);
    } catch (e: any) {
      setError(e.message || "Prospect search failed");
    } finally {
      setLoading(false);
    }
  };

  const rebuildGraph = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await post(`/backlinks/${websiteId}/graph/rebuild`, {});
      setGraph(data || { nodes: [], edges: [], orphans: [] });
      setToast("Graph rebuilt");
    } catch (e: any) {
      setError(e.message || "Rebuild failed");
    } finally {
      setLoading(false);
    }
  };

  const checkBacklinks = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await post(`/backlinks/${websiteId}/check`, {});
      setMonitor(data.monitor || []);
      setToast(`Checked ${data.checked} backlinks`);
    } catch (e: any) {
      setError(e.message || "Check failed");
    } finally {
      setLoading(false);
    }
  };

  const runSuggest = async () => {
    if (!suggestUrl || !suggestKeyword) return;
    setLoading(true);
    setError(null);
    try {
      const data = await post(`/links/${websiteId}/suggest`, {
        url: suggestUrl,
        keyword: suggestKeyword,
      });
      setSuggestions(data);
    } catch (e: any) {
      setError(e.message || "Suggest failed");
    } finally {
      setLoading(false);
    }
  };

  const approveProspect = async (prospectId: string) => {
    if (!userId) {
      setShowApproveModal(prospectId);
      return;
    }
    setLoading(true);
    try {
      await post(`/backlinks/${websiteId}/prospects/${prospectId}/approve`, {}, { "X-User-Id": userId });
      setToast("Draft created - human must send");
      refresh();
    } catch (e: any) {
      setError(e.message || "Approve failed");
    } finally {
      setLoading(false);
    }
  };

  const markSent = async (draftId: string) => {
    if (!userId) {
      setError("X-User-Id required");
      return;
    }
    setLoading(true);
    try {
      await post(`/backlinks/${websiteId}/outreach/${draftId}/sent`, {}, { "X-User-Id": userId });
      setToast("Marked as sent");
      refresh();
    } catch (e: any) {
      setError(e.message || "Mark sent failed");
    } finally {
      setLoading(false);
    }
  };

  const copyBody = (body: string) => {
    navigator.clipboard.writeText(body);
    setToast("Copied to clipboard");
  };

  const stats = useMemo(() => {
    const active = monitor.filter((m) => m.status === "active").length;
    const lost = monitor.filter((m) => m.status === "lost").length;
    const broken = monitor.filter((m) => m.status === "broken").length;
    const redirected = monitor.filter((m) => m.status === "redirected").length;
    return { active, lost, broken, redirected };
  }, [monitor]);

  const renderGraph = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-stone border border-ink p-3">
          <div className="text-[9px] text-muted uppercase tracking-wider mono-font mb-1">Total Nodes</div>
          <div className="text-2xl font-bold dot-font">{graph.nodes.length}</div>
        </div>
        <div className="bg-stone border border-ink p-3">
          <div className="text-[9px] text-muted uppercase tracking-wider mono-font mb-1">Total Edges</div>
          <div className="text-2xl font-bold dot-font">{graph.edges.length}</div>
        </div>
        <div className="bg-stone border border-ink p-3">
          <div className="text-[9px] text-muted uppercase tracking-wider mono-font mb-1">Orphans</div>
          <div className="text-2xl font-bold dot-font text-red-500">{graph.orphans.length}</div>
        </div>
        <div className="bg-stone border border-ink p-3">
          <div className="text-[9px] text-muted uppercase tracking-wider mono-font mb-1">Avg PageRank</div>
          <div className="text-2xl font-bold dot-font">
            {graph.nodes.length ? (graph.nodes.reduce((s, n) => s + (n.pagerank || 0), 0) / graph.nodes.length).toFixed(3) : "0"}
          </div>
        </div>
      </div>

      <div className="bg-stone border border-ink p-3">
        <div className="text-[10px] text-muted uppercase tracking-wider mono-font mb-2">PageRank Force Graph</div>
        <svg ref={graphRef} className="w-full bg-paper border border-line" style={{ height: 500 }} />
      </div>

      <div className="bg-stone border border-ink p-3">
        <div className="text-[10px] text-muted uppercase tracking-wider mono-font mb-2">Orphan Pages (0 incoming, high sessions)</div>
        {graph.orphans.length === 0 ? (
          <div className="text-[11px] text-muted mono-font py-4">No orphans detected</div>
        ) : (
          <div className="space-y-2">
            {graph.orphans.map((url, i) => {
              const node = graph.nodes.find((n) => n.url === url);
              return (
                <div key={i} className="flex items-center justify-between p-2 border border-line hover:border-ink transition-colors">
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] mono-font truncate">{url}</div>
                    <div className="text-[9px] text-muted">0 incoming but {node?.sessions || 0} sessions - fix now</div>
                  </div>
                  <button
                    className="btn btn-primary ml-2"
                    onClick={() => {
                      setSuggestUrl(url);
                      setSuggestKeyword(url.split("/").pop() || "");
                    }}
                  >
                    Fix
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="bg-stone border border-ink p-3">
        <div className="text-[10px] text-muted uppercase tracking-wider mono-font mb-2">Suggest Internal Links</div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-2">
          <input className="field" placeholder="New article URL" value={suggestUrl} onChange={(e) => setSuggestUrl(e.target.value)} />
          <input className="field" placeholder="Primary keyword" value={suggestKeyword} onChange={(e) => setSuggestKeyword(e.target.value)} />
          <button className="btn btn-accent" onClick={runSuggest} disabled={!suggestUrl || !suggestKeyword}>Suggest</button>
        </div>
        {suggestions && (
          <div className="space-y-3 mt-3">
            {suggestions.suggestions?.map((s: any, i: number) => (
              <div key={i} className="p-2 border border-line">
                <div className="text-[11px] mono-font font-semibold">{s.url}</div>
                <div className="text-[10px] text-muted">Anchor: {s.anchor}</div>
                <div className="text-[10px] text-muted">{s.reason}</div>
                {s.position_h2 && <div className="text-[10px] text-muted">Position: {s.position_h2}</div>}
              </div>
            ))}
            {suggestions.reverse_link && (
              <div className="p-2 border border-line border-accent">
                <div className="text-[11px] mono-font font-semibold">Reverse: {suggestions.reverse_link.pillar_url}</div>
                <div className="text-[10px] text-muted">{suggestions.reverse_link.reason}</div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex gap-2">
        <button className="btn btn-accent" onClick={rebuildGraph} disabled={loading}>Rebuild Graph</button>
      </div>
    </div>
  );

  const renderProspects = () => (
    <div className="space-y-4">
      <div className="bg-stone border border-ink p-3">
        <div className="text-[10px] text-muted uppercase tracking-wider mono-font mb-2">Find Prospects</div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <input className="field" placeholder="Primary keyword" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
          <input className="field" placeholder="Competitor page (optional)" value={targetPage} onChange={(e) => setTargetPage(e.target.value)} />
          <button className="btn btn-accent" onClick={runProspect} disabled={loading}>Prospect Now</button>
        </div>
      </div>

      {prospects.length === 0 ? (
        <div className="bg-stone border border-ink p-6 text-center">
          <div className="text-[11px] text-muted mono-font">No prospects - Enter keyword and click Prospect Now - Real Crawlee search no mock</div>
        </div>
      ) : (
        <div className="bg-stone border border-ink overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>URL</th>
                <th>DR</th>
                <th>Strategy</th>
                <th>Reason</th>
                <th>Broken Link</th>
                <th>Anchor</th>
                <th>Relevance</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {prospects.map((p) => (
                <tr key={p.id}>
                  <td>
                    <a href={p.prospect_url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                      {p.prospect_url}
                    </a>
                  </td>
                  <td>
                    <span className={`badge ${(p.domain_rating || 0) > 60 ? "badge-green" : (p.domain_rating || 0) > 40 ? "badge-amber" : "badge-red"}`}>
                      DR {p.domain_rating?.toFixed(0) || "?"}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${p.strategy === "broken_link" ? "badge-red" : p.strategy === "resource_page" ? "badge-accent" : p.strategy === "competitor_gap" ? "badge-amber" : "badge-muted"}`}>
                      {p.strategy}
                    </span>
                  </td>
                  <td className="max-w-xs truncate" title={p.reason}>{p.reason}</td>
                  <td>
                    {p.broken_link_url ? (
                      <a href={p.broken_link_url} target="_blank" rel="noreferrer" className="text-red-500 hover:underline text-[10px]">
                        404
                      </a>
                    ) : (
                      <span className="text-muted">-</span>
                    )}
                  </td>
                  <td className="text-[10px]">{p.anchor_suggestion}</td>
                  <td>{(p.relevance_score * 100).toFixed(0)}</td>
                  <td>
                    <span className={`badge ${p.status === "opportunity" ? "badge-muted" : p.status === "approved" ? "badge-amber" : p.status === "acquired" ? "badge-green" : "badge-red"}`}>
                      {p.status}
                    </span>
                  </td>
                  <td>
                    <button className="btn btn-primary mr-1" onClick={() => approveProspect(p.id)}>Approve</button>
                    <button className="btn btn-danger" onClick={() => { /* reject */ }}>Reject</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );

  const renderMonitor = () => {
    const anchorExact = monitor.length > 0
      ? Math.round(
          (monitor.filter((m) => m.anchor_text === (monitor[0] as any)?.target_keyword).length /
            monitor.length) *
            100
        )
      : 0;
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-stone border border-ink p-3">
            <div className="text-[9px] text-muted uppercase tracking-wider mono-font mb-1">Active</div>
            <div className="text-2xl font-bold dot-font text-green-500">{stats.active}</div>
          </div>
          <div className="bg-stone border border-ink p-3">
            <div className="text-[9px] text-muted uppercase tracking-wider mono-font mb-1">Lost</div>
            <div className="text-2xl font-bold dot-font text-red-500">{stats.lost}</div>
          </div>
          <div className="bg-stone border border-ink p-3">
            <div className="text-[9px] text-muted uppercase tracking-wider mono-font mb-1">Broken</div>
            <div className="text-2xl font-bold dot-font text-amber-500">{stats.broken}</div>
          </div>
          <div className="bg-stone border border-ink p-3">
            <div className="text-[9px] text-muted uppercase tracking-wider mono-font mb-1">Redirected</div>
            <div className="text-2xl font-bold dot-font">{stats.redirected}</div>
          </div>
        </div>

        {anchorExact > 60 && (
          <div className="bg-stone border border-red-500 p-3">
            <div className="text-[11px] mono-font text-red-500">{anchorExact}% anchors exact match - risk penalty - diversify</div>
          </div>
        )}

        <div className="bg-stone border border-ink p-3">
          <div className="text-[10px] text-muted uppercase tracking-wider mono-font mb-2">Backlinks Monitor</div>
          {monitor.length === 0 ? (
            <div className="text-[11px] text-muted mono-font py-4">No backlink data - Run Check Now</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Our URL</th>
                    <th>Anchor</th>
                    <th>DR</th>
                    <th>Status</th>
                    <th>Code</th>
                    <th>Checked</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {monitor.map((m) => (
                    <tr key={m.id}>
                      <td>
                        <a href={m.source_url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                          {m.source_url}
                        </a>
                      </td>
                      <td className="text-[10px]">{m.backlink_url}</td>
                      <td className="text-[10px]">{m.anchor_text}</td>
                      <td>
                        <span className={`badge ${(m.domain_rating || 0) > 60 ? "badge-green" : (m.domain_rating || 0) > 40 ? "badge-amber" : "badge-red"}`}>
                          DR {m.domain_rating?.toFixed(0) || "?"}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${m.status === "active" ? "badge-green" : m.status === "lost" ? "badge-red" : m.status === "broken" ? "badge-amber" : "badge-muted"}`}>
                          {m.status}
                        </span>
                      </td>
                      <td className="text-[10px]">{m.status_code || "-"}</td>
                      <td className="text-[10px]">{new Date(m.checked_at).toLocaleString()}</td>
                      <td>
                        <button className="btn btn-primary" onClick={checkBacklinks} disabled={loading}>Check Now</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderOutreach = () => (
    <div className="space-y-4">
      <div className="bg-stone border border-ink p-3">
        <div className="text-[10px] text-muted uppercase tracking-wider mono-font mb-2">Outreach Drafts</div>
        {outreach.length === 0 ? (
          <div className="text-[11px] text-muted mono-font py-4">No drafts - Approve a prospect to create one</div>
        ) : (
          <div className="space-y-3">
            {outreach.map((d) => (
              <div key={d.id} className="p-3 border border-line">
                <div className="flex items-center justify-between mb-1">
                  <div className="text-[11px] mono-font font-semibold">{d.subject}</div>
                  <span className={`badge ${d.status === "draft_ready" ? "badge-muted" : d.status === "sent" ? "badge-green" : "badge-amber"}`}>
                    {d.status}
                  </span>
                </div>
                <div className="text-[10px] text-muted mb-2">{d.body.slice(0, 120)}...</div>
                <div className="flex gap-2">
                  <button className="btn btn-primary" onClick={() => copyBody(d.body)}>Copy Body</button>
                  {d.status !== "sent" && (
                    <button className="btn btn-accent" onClick={() => markSent(d.id)} disabled={loading}>Mark Sent</button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  const renderBrain = () => (
    <div className="space-y-4">
      <div className="bg-stone border border-ink p-3">
        <div className="text-[10px] text-muted uppercase tracking-wider mono-font mb-2">Backlink Memories</div>
        {brainMemories.length === 0 ? (
          <div className="text-[11px] text-muted mono-font py-4">No backlink memories yet</div>
        ) : (
          <div className="space-y-2">
            {brainMemories.map((m) => (
              <div key={m.id} className="p-2 border border-line">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`badge ${m.memory_type === "outcome" ? "badge-green" : m.memory_type === "failure" ? "badge-red" : "badge-muted"}`}>
                    {m.memory_type}
                  </span>
                  <span className="text-[11px] mono-font font-semibold">{m.title}</span>
                </div>
                <div className="text-[10px] text-muted mb-1">{m.content.slice(0, 200)}</div>
                <div className="text-[9px] text-muted">
                  Confidence: {(m.confidence * 100).toFixed(0)}% | Used: {m.times_used} | Success: {m.times_successful} | Last: {new Date(m.last_used_at).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[11px] text-muted">
          <span className="w-2 h-2 bg-accent" />
          <span>Links</span>
        </div>
        <div className="flex items-center gap-2">
          <select className="field" value={websiteId} onChange={(e) => setCurrentWebsiteId(e.target.value)}>
            {websites.map((w) => (
              <option key={w.id} value={w.id}>{w.domain}</option>
            ))}
          </select>
          <button className="btn btn-primary" onClick={refresh} disabled={loading}>Refresh</button>
        </div>
      </div>

      <div>
        <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">Links</h1>
        <p className="text-[11px] text-muted uppercase tracking-widest mono-font mt-1">
          Internal graph + external prospects + monitor + outreach + brain
        </p>
      </div>

      {error && (
        <div className="bg-stone border border-red-500 p-3">
          <div className="text-[11px] mono-font text-red-500">{error}</div>
        </div>
      )}

      <div className="flex border border-ink">
        {([
          { key: "graph", label: "Internal Graph" },
          { key: "prospects", label: "Prospects" },
          { key: "monitor", label: "Monitor" },
          { key: "outreach", label: "Outreach" },
          { key: "brain", label: "Brain" },
        ] as { key: Tab; label: string }[]).map((t) => (
          <button
            key={t.key}
            className={`flex-1 py-2 text-[10px] uppercase tracking-wider mono-font border-r border-ink last:border-r-0 ${tab === t.key ? "bg-ink text-paper" : "bg-stone text-muted hover:text-ink"}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading && (
        <div className="space-y-3">
          <div className="h-8 w-full bg-line animate-pulse" />
          <div className="h-48 w-full bg-line animate-pulse" />
        </div>
      )}

      {!loading && tab === "graph" && renderGraph()}
      {!loading && tab === "prospects" && renderProspects()}
      {!loading && tab === "monitor" && renderMonitor()}
      {!loading && tab === "outreach" && renderOutreach()}
      {!loading && tab === "brain" && renderBrain()}

      {toast && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-ink text-paper px-4 py-2 text-[10px] uppercase tracking-widest mono-font z-50">
          {toast}
        </div>
      )}

      {showApproveModal && (
        <div className="modal-overlay open" onClick={() => setShowApproveModal(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <div className="modal-title">Human Approval Required</div>
              <button className="modal-close" onClick={() => setShowApproveModal(null)}>×</button>
            </div>
            <div className="modal-body">
              <div className="text-[11px] mono-font mb-2">Enter your User ID to approve outreach draft:</div>
              <input className="field" value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="User ID" />
            </div>
            <div className="modal-footer">
              <button className="btn" onClick={() => setShowApproveModal(null)}>Cancel</button>
              <button
                className="btn btn-primary"
                onClick={() => {
                  approveProspect(showApproveModal);
                  setShowApproveModal(null);
                }}
                disabled={!userId}
              >
                Approve
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
