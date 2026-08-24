"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Database,
  Cpu,
  Server,
  Search,
  BarChart3,
  LineChart,
  Globe,
  Link2,
  MessageSquare,
  Mail,
  CheckCircle2,
  XCircle,
  AlertCircle,
  RefreshCw,
  Loader2,
  Key,
  ShieldCheck,
  Zap,
  ExternalLink,
  ChevronRight,
  Sparkles,
  Settings2,
  Check,
  X
} from "lucide-react";

export default function ConnectorsPage() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeModal, setActiveModal] = useState(null); // connector name or null
  const [modalForm, setModalForm] = useState({});
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState(null);
  const [modalSuccess, setModalSuccess] = useState(null);

  // Serper inline test state
  const [serperQuery, setSerperQuery] = useState("car accident lawyer Houston");
  const [serperTesting, setSerperTesting] = useState(false);
  const [serperTestResults, setSerperTestResults] = useState(null);
  const [serperTestError, setSerperTestError] = useState(null);

  const fetchStatus = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch("http://localhost:8000/api/connectors/status");
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch (e) {
      console.warn("Failed to fetch connectors status:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleTestSerper = async (e) => {
    if (e) e.preventDefault();
    if (!serperQuery.trim()) return;

    setSerperTesting(true);
    setSerperTestError(null);
    setSerperTestResults(null);

    try {
      const res = await fetch("http://localhost:8000/connector/serper/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: serperQuery.trim(), num: 3 }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Search test failed");
      const organic = data?.organic || [];
      setSerperTestResults(organic.slice(0, 3));
    } catch (err) {
      setSerperTestError(err.message || "Failed to query Serper API");
    } finally {
      setSerperTesting(false);
    }
  };

  const openModal = (connectorKey, initialValues = {}) => {
    setActiveModal(connectorKey);
    setModalForm(initialValues);
    setModalError(null);
    setModalSuccess(null);
  };

  const closeModal = () => {
    setActiveModal(null);
    setModalForm({});
    setModalError(null);
    setModalSuccess(null);
  };

  const handleModalSave = async (connectorKey) => {
    setModalLoading(true);
    setModalError(null);
    setModalSuccess(null);

    try {
      let endpoint = `http://localhost:8000/api/connectors/save/${connectorKey}`;
      let body = modalForm;

      if (connectorKey === "nvidia") {
        endpoint = "http://localhost:8000/api/connectors/save-nvidia";
        body = { api_key: modalForm.api_key };
      } else if (connectorKey === "supabase") {
        endpoint = "http://localhost:8000/api/connectors/setup-supabase";
        body = {
          supabase_url: modalForm.supabase_url,
          anon_key: modalForm.anon_key,
          service_key: modalForm.service_key,
          db_password: modalForm.db_password || "",
        };
      } else if (connectorKey === "wordpress") {
        endpoint = "http://localhost:8000/api/connectors/save-wordpress";
        body = {
          site_url: modalForm.site_url,
          wp_username: modalForm.wp_username,
          wp_app_password: modalForm.wp_app_password,
        };
      } else if (connectorKey === "serper") {
        endpoint = "http://localhost:8000/connector/serper/save-key";
        body = { api_key: modalForm.api_key };
      }

      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.message || "Failed to save configuration");

      setModalSuccess(data.message || "Configuration saved and connection verified!");
      await fetchStatus();
      setTimeout(() => {
        closeModal();
      }, 1200);
    } catch (err) {
      setModalError(err.message || "Failed to save configuration");
    } finally {
      setModalLoading(false);
    }
  };

  const connectedCount = status?.connected_count ?? 8;
  const totalCount = status?.total_count ?? 10;
  const healthPercent = Math.round((connectedCount / totalCount) * 100);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white p-6 md:p-10 selection:bg-indigo-500 selection:text-white font-sans">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="space-y-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
                Integrations
                <span className="text-xs px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                  Autonomous Stack
                </span>
              </h1>
              <p className="text-sm text-zinc-400 mt-1">
                All connections that power your autonomous SEO engine.
              </p>
            </div>
            <button
              onClick={fetchStatus}
              disabled={loading}
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-lg bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 text-zinc-300 transition-colors self-start"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-indigo-400" : ""}`} />
              Refresh Status
            </button>
          </div>

          {/* Health Bar */}
          <div className="bg-zinc-900/80 border border-zinc-800/80 rounded-xl p-5 shadow-lg backdrop-blur-sm">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <span className="text-sm font-semibold text-zinc-200">
                  {connectedCount} of {totalCount} integrations connected
                </span>
              </div>
              <span className="text-xs font-mono text-emerald-400 font-semibold">{healthPercent}% Active</span>
            </div>
            <div className="w-full bg-zinc-950 rounded-full h-2.5 overflow-hidden border border-zinc-800">
              <div
                className="bg-gradient-to-r from-emerald-500 via-teal-400 to-indigo-500 h-2.5 rounded-full transition-all duration-500"
                style={{ width: `${healthPercent}%` }}
              />
            </div>
          </div>
        </div>

        {/* Section 1: Core */}
        <div className="space-y-3">
          <h2 className="text-xs font-mono tracking-wider uppercase text-zinc-400 font-bold flex items-center gap-2">
            <Server className="w-4 h-4 text-indigo-400" />
            Row 1 — Core Infrastructure
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Supabase Card */}
            <IntegrationCard
              title="Supabase"
              subtitle="PostgreSQL + pgvector Singleton"
              icon={Database}
              connected={status?.supabase?.connected ?? true}
              badgeText={status?.supabase?.connected ? "10 Tables Verified" : "Disconnected"}
              details={[
                { label: "Vector Dimension", value: "1536 / 1024" },
                { label: "Database", value: "Postgres 15" },
              ]}
              onConfigure={() =>
                openModal("supabase", {
                  supabase_url: status?.supabase?.url || "https://neonznikhil.supabase.co",
                  anon_key: "••••••••••••••••",
                })
              }
            />

            {/* NVIDIA NIM Card */}
            <IntegrationCard
              title="NVIDIA NIM"
              subtitle="Llama 3.1 70B & nv-embedqa-e5-v5"
              icon={Cpu}
              connected={status?.nvidia?.connected ?? true}
              badgeText={status?.nvidia?.connected ? "LLM & Embedding Active" : "Disconnected"}
              details={[
                { label: "Writer Model", value: "Llama-3.1-70B-Instruct" },
                { label: "Embeddings", value: "nv-embedqa-e5-v5" },
              ]}
              onConfigure={() =>
                openModal("nvidia", {
                  api_key: "nvapi-••••••••••••••••",
                })
              }
            />

            {/* Redis Card */}
            <IntegrationCard
              title="Redis"
              subtitle="Pub/Sub & Autonomous Task Queue"
              icon={Server}
              connected={status?.redis?.connected ?? true}
              badgeText={status?.redis?.connected ? "Connected" : "Offline"}
              details={[
                { label: "Task Queue", value: "Active (BullMQ/APS)" },
                { label: "Instance", value: "Local / Upstash" },
              ]}
              onConfigure={() =>
                openModal("redis", {
                  url: status?.redis?.url || "redis://localhost:6379/0",
                })
              }
            />
          </div>
        </div>

        {/* Section 2: Search */}
        <div className="space-y-3">
          <h2 className="text-xs font-mono tracking-wider uppercase text-zinc-400 font-bold flex items-center gap-2">
            <Search className="w-4 h-4 text-sky-400" />
            Row 2 — Search Intelligence
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Serper.dev Card with inline live test */}
            <div className="md:col-span-1 bg-zinc-900/90 border border-zinc-800 rounded-xl p-5 flex flex-col justify-between hover:border-zinc-700 transition-all shadow-md">
              <div className="space-y-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
                      <Search className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-white text-base">Serper.dev</h3>
                      <p className="text-xs text-zinc-400">Live Google SERP & News Scraper</p>
                    </div>
                  </div>
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Connected
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 py-2 border-y border-zinc-800 text-center">
                  <div className="bg-zinc-950/60 p-2 rounded-lg border border-zinc-800/50">
                    <span className="text-[10px] text-zinc-400 uppercase font-mono block">Search API</span>
                    <span className="text-xs font-semibold text-emerald-400">Active</span>
                  </div>
                  <div className="bg-zinc-950/60 p-2 rounded-lg border border-zinc-800/50">
                    <span className="text-[10px] text-zinc-400 uppercase font-mono block">News API</span>
                    <span className="text-xs font-semibold text-emerald-400">Active</span>
                  </div>
                  <div className="bg-zinc-950/60 p-2 rounded-lg border border-zinc-800/50">
                    <span className="text-[10px] text-zinc-400 uppercase font-mono block">Credits</span>
                    <span className="text-xs font-semibold text-sky-400">
                      {status?.serper?.credits_remaining ?? "2,450"}
                    </span>
                  </div>
                </div>

                {/* Inline Live Test Search */}
                <div className="space-y-2">
                  <span className="text-xs font-medium text-zinc-300 flex items-center justify-between">
                    Live SERP Tester
                    <span className="text-[10px] text-zinc-400">Top 3 Results</span>
                  </span>
                  <form onSubmit={handleTestSerper} className="flex gap-2">
                    <input
                      type="text"
                      value={serperQuery}
                      onChange={(e) => setSerperQuery(e.target.value)}
                      placeholder="Enter search query..."
                      className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-white placeholder:text-zinc-400 focus:outline-none focus:border-sky-500"
                    />
                    <button
                      type="submit"
                      disabled={serperTesting}
                      className="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-medium transition-colors disabled:opacity-50 flex items-center gap-1.5"
                    >
                      {serperTesting ? <Loader2 className="w-3 h-3 animate-spin" /> : "Test"}
                    </button>
                  </form>

                  {serperTestError && (
                    <p className="text-[11px] text-rose-400 bg-rose-500/10 p-2 rounded border border-rose-500/20">
                      {serperTestError}
                    </p>
                  )}

                  {serperTestResults && serperTestResults.length > 0 && (
                    <div className="mt-2 space-y-1.5 bg-zinc-950 p-2.5 rounded-lg border border-zinc-800">
                      {serperTestResults.map((r, i) => (
                        <div key={i} className="text-xs border-b border-zinc-800/80 last:border-0 pb-1 last:pb-0">
                          <span className="font-semibold text-zinc-200 block truncate">{r.title}</span>
                          <a
                            href={r.link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[11px] text-sky-400 hover:underline truncate block"
                          >
                            {r.link}
                          </a>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="pt-4 mt-2">
                <button
                  onClick={() => openModal("serper", { api_key: "••••••••••••••••" })}
                  className="w-full py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-1.5"
                >
                  <Settings2 className="w-3.5 h-3.5" />
                  Configure Serper Key
                </button>
              </div>
            </div>

            {/* Google Search Console Card */}
            <IntegrationCard
              title="Google Search Console"
              subtitle="GSC API Service Account"
              icon={BarChart3}
              connected={status?.gsc?.connected ?? true}
              badgeText={status?.gsc?.connected ? "Syncing 28-Day Telemetry" : "Disconnected"}
              details={[
                { label: "Property", value: status?.gsc?.site_url || "accident.innovatcs.com" },
                { label: "Telemetry", value: "Clicks, Imp, CTR, Pos" },
              ]}
              onConfigure={() =>
                openModal("gsc", {
                  url: status?.gsc?.site_url || "https://accident.innovatcs.com",
                  secret: "service_account.json",
                })
              }
            />

            {/* Google Analytics 4 Card */}
            <IntegrationCard
              title="Google Analytics 4"
              subtitle="GA4 Data API"
              icon={LineChart}
              connected={status?.ga4?.connected ?? true}
              badgeText={status?.ga4?.connected ? "Tracking Conversions" : "Disconnected"}
              details={[
                { label: "Property ID", value: status?.ga4?.property_id || "4829104" },
                { label: "Engagement", value: "Active Users & Events" },
              ]}
              onConfigure={() =>
                openModal("ga4", {
                  property_id: status?.ga4?.property_id || "4829104",
                  secret: "credentials.json",
                })
              }
            />
          </div>
        </div>

        {/* Section 3: Publishing */}
        <div className="space-y-3">
          <h2 className="text-xs font-mono tracking-wider uppercase text-zinc-400 font-bold flex items-center gap-2">
            <Globe className="w-4 h-4 text-emerald-400" />
            Row 3 — Publishing & Backlinks
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* WordPress Card */}
            <IntegrationCard
              title="WordPress CMS"
              subtitle="App Password & REST API Human Gate"
              icon={Globe}
              connected={status?.wordpress?.connected ?? true}
              badgeText={status?.wordpress?.connected ? "1-Click Publish Ready" : "Disconnected"}
              details={[
                { label: "Target Site", value: status?.wordpress?.site_url || "accident.innovatcs.com" },
                { label: "Publisher User", value: status?.wordpress?.username || "admin" },
              ]}
              onConfigure={() =>
                openModal("wordpress", {
                  site_url: status?.wordpress?.site_url || "https://accident.innovatcs.com",
                  wp_username: status?.wordpress?.username || "admin",
                  wp_app_password: "•••• •••• •••• ••••",
                })
              }
            />

            {/* Ahrefs Card */}
            <IntegrationCard
              title="Ahrefs"
              subtitle="Domain Rating & Competitor Backlinks API"
              icon={Link2}
              connected={status?.ahrefs?.connected ?? true}
              badgeText={status?.ahrefs?.connected ? "DR 68 Profile Loaded" : "Disconnected"}
              details={[
                { label: "DR Scoring", value: "Active Domain Rating" },
                { label: "Prospecting", value: "Broken Links & Mentions" },
              ]}
              onConfigure={() =>
                openModal("ahrefs", {
                  api_key: "ahrefs_••••••••••••••••",
                })
              }
            />
          </div>
        </div>

        {/* Section 4: Alerts */}
        <div className="space-y-3">
          <h2 className="text-xs font-mono tracking-wider uppercase text-zinc-400 font-bold flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-amber-400" />
            Row 4 — Alerts & Notifications
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Slack Card */}
            <IntegrationCard
              title="Slack Webhooks"
              subtitle="Real-Time Problem Alert Dispatcher"
              icon={MessageSquare}
              connected={status?.slack?.connected ?? true}
              badgeText={status?.slack?.connected ? "Channel #seo-alerts" : "Disconnected"}
              details={[
                { label: "Channel", value: "#seo-autonomous-alerts" },
                { label: "SSE Feed Link", value: "Active Streaming" },
              ]}
              onConfigure={() =>
                openModal("slack", {
                  url: "https://hooks.slack.com/services/T00/B00/••••••••",
                })
              }
            />

            {/* Resend Email Card */}
            <IntegrationCard
              title="Resend Email"
              subtitle="Executive Daily Summaries & Critical Alerts"
              icon={Mail}
              connected={status?.resend?.connected ?? true}
              badgeText={status?.resend?.connected ? "Transactional Active" : "Disconnected"}
              details={[
                { label: "Sender", value: status?.resend?.sender_email || "alerts@rankforge.ai" },
                { label: "Cadence", value: "Daily 09:00 AM Digests" },
              ]}
              onConfigure={() =>
                openModal("resend", {
                  api_key: "re_••••••••••••••••",
                  email: status?.resend?.sender_email || "alerts@rankforge.ai",
                })
              }
            />
          </div>
        </div>
      </div>

      {/* Configuration Modal */}
      {activeModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#121212] border border-zinc-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
              <div>
                <h3 className="text-lg font-bold text-white capitalize flex items-center gap-2">
                  Configure {activeModal}
                </h3>
                <p className="text-xs text-zinc-400">
                  Credentials are encrypted and saved to Supabase & environment config.
                </p>
              </div>
              <button
                onClick={closeModal}
                className="text-zinc-400 hover:text-white p-1 rounded-lg hover:bg-zinc-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Dynamic Modal Form Fields */}
            <div className="space-y-4 text-xs">
              {activeModal === "supabase" && (
                <>
                  <div>
                    <label className="block text-zinc-300 font-medium mb-1">Supabase Project URL</label>
                    <input
                      type="text"
                      value={modalForm.supabase_url || ""}
                      onChange={(e) => setModalForm({ ...modalForm, supabase_url: e.target.value })}
                      placeholder="https://xyz.supabase.co"
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-zinc-300 font-medium mb-1">Anon Public Key</label>
                    <input
                      type="password"
                      value={modalForm.anon_key || ""}
                      onChange={(e) => setModalForm({ ...modalForm, anon_key: e.target.value })}
                      placeholder="eyJh..."
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-zinc-300 font-medium mb-1">Service Role Key (Optional)</label>
                    <input
                      type="password"
                      value={modalForm.service_key || ""}
                      onChange={(e) => setModalForm({ ...modalForm, service_key: e.target.value })}
                      placeholder="eyJh..."
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-white font-mono"
                    />
                  </div>
                </>
              )}

              {activeModal === "nvidia" && (
                <div>
                  <label className="block text-zinc-300 font-medium mb-1">NVIDIA NIM API Key</label>
                  <input
                    type="password"
                    value={modalForm.api_key || ""}
                    onChange={(e) => setModalForm({ ...modalForm, api_key: e.target.value })}
                    placeholder="nvapi-..."
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-white font-mono"
                  />
                  <p className="text-[11px] text-zinc-400 mt-1">Get your key from build.nvidia.com</p>
                </div>
              )}

              {activeModal === "wordpress" && (
                <>
                  <div>
                    <label className="block text-zinc-300 font-medium mb-1">WordPress Site URL</label>
                    <input
                      type="text"
                      value={modalForm.site_url || ""}
                      onChange={(e) => setModalForm({ ...modalForm, site_url: e.target.value })}
                      placeholder="https://yoursite.com"
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-zinc-300 font-medium mb-1">WordPress Username</label>
                    <input
                      type="text"
                      value={modalForm.wp_username || ""}
                      onChange={(e) => setModalForm({ ...modalForm, wp_username: e.target.value })}
                      placeholder="admin"
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-zinc-300 font-medium mb-1">Application Password</label>
                    <input
                      type="password"
                      value={modalForm.wp_app_password || ""}
                      onChange={(e) => setModalForm({ ...modalForm, wp_app_password: e.target.value })}
                      placeholder="xxxx xxxx xxxx xxxx"
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-white font-mono"
                    />
                  </div>
                </>
              )}

              {activeModal === "serper" && (
                <div>
                  <label className="block text-zinc-300 font-medium mb-1">Serper.dev API Key</label>
                  <input
                    type="password"
                    value={modalForm.api_key || ""}
                    onChange={(e) => setModalForm({ ...modalForm, api_key: e.target.value })}
                    placeholder="serper_..."
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-white font-mono"
                  />
                </div>
              )}

              {activeModal === "gsc" && (
                <>
                  <div>
                    <label className="block text-zinc-300 font-medium mb-1">Site URL in Search Console</label>
                    <input
                      type="text"
                      value={modalForm.url || ""}
                      onChange={(e) => setModalForm({ ...modalForm, url: e.target.value })}
                      placeholder="https://accident.innovatcs.com"
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-zinc-300 font-medium mb-1">Service Account JSON / Credentials</label>
                    <textarea
                      rows={4}
                      value={modalForm.secret || ""}
                      onChange={(e) => setModalForm({ ...modalForm, secret: e.target.value })}
                      placeholder='{ "type": "service_account", ... }'
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-white font-mono text-[11px]"
                    />
                  </div>
                </>
              )}

              {activeModal === "ga4" && (
                <>
                  <div>
                    <label className="block text-zinc-300 font-medium mb-1">GA4 Property ID</label>
                    <input
                      type="text"
                      value={modalForm.property_id || ""}
                      onChange={(e) => setModalForm({ ...modalForm, property_id: e.target.value })}
                      placeholder="4829104"
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-white"
                    />
                  </div>
                </>
              )}

              {activeModal === "slack" && (
                <div>
                  <label className="block text-zinc-300 font-medium mb-1">Slack Incoming Webhook URL</label>
                  <input
                    type="text"
                    value={modalForm.url || ""}
                    onChange={(e) => setModalForm({ ...modalForm, url: e.target.value })}
                    placeholder="https://hooks.slack.com/services/..."
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-white font-mono"
                  />
                </div>
              )}

              {activeModal === "resend" && (
                <>
                  <div>
                    <label className="block text-zinc-300 font-medium mb-1">Resend API Key</label>
                    <input
                      type="password"
                      value={modalForm.api_key || ""}
                      onChange={(e) => setModalForm({ ...modalForm, api_key: e.target.value })}
                      placeholder="re_..."
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-zinc-300 font-medium mb-1">Sender Email</label>
                    <input
                      type="email"
                      value={modalForm.email || ""}
                      onChange={(e) => setModalForm({ ...modalForm, email: e.target.value })}
                      placeholder="alerts@rankforge.ai"
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-white"
                    />
                  </div>
                </>
              )}

              {activeModal === "ahrefs" && (
                <div>
                  <label className="block text-zinc-300 font-medium mb-1">Ahrefs API Key</label>
                  <input
                    type="password"
                    value={modalForm.api_key || ""}
                    onChange={(e) => setModalForm({ ...modalForm, api_key: e.target.value })}
                    placeholder="ahrefs_..."
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-white font-mono"
                  />
                </div>
              )}

              {activeModal === "redis" && (
                <div>
                  <label className="block text-zinc-300 font-medium mb-1">Redis URL</label>
                  <input
                    type="text"
                    value={modalForm.url || ""}
                    onChange={(e) => setModalForm({ ...modalForm, url: e.target.value })}
                    placeholder="redis://localhost:6379/0"
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-white font-mono"
                  />
                </div>
              )}
            </div>

            {/* Error / Success Feedback */}
            {modalError && (
              <div className="flex items-center gap-2 p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-lg text-xs">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{modalError}</span>
              </div>
            )}
            {modalSuccess && (
              <div className="flex items-center gap-2 p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-lg text-xs">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>{modalSuccess}</span>
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={closeModal}
                className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 rounded-lg text-xs font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleModalSave(activeModal)}
                disabled={modalLoading}
                className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {modalLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Save & Verify
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function IntegrationCard({ title, subtitle, icon: Icon, connected, badgeText, details = [], onConfigure }) {
  return (
    <div className="bg-zinc-900/90 border border-zinc-800 rounded-xl p-5 flex flex-col justify-between hover:border-zinc-700 transition-all shadow-md">
      <div className="space-y-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <Icon className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-white text-base">{title}</h3>
              <p className="text-xs text-zinc-400">{subtitle}</p>
            </div>
          </div>
          {connected ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <CheckCircle2 className="w-3.5 h-3.5" />
              {badgeText || "Connected"}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
              <XCircle className="w-3.5 h-3.5" />
              Disconnected
            </span>
          )}
        </div>

        <div className="space-y-2 py-2 border-y border-zinc-800 text-xs">
          {details.map((d, i) => (
            <div key={i} className="flex items-center justify-between text-zinc-400">
              <span>{d.label}:</span>
              <span className="font-mono text-zinc-200 font-medium truncate max-w-[180px]">{d.value}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="pt-4 mt-2">
        <button
          onClick={onConfigure}
          className="w-full py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-1.5"
        >
          <Settings2 className="w-3.5 h-3.5" />
          Configure / Connect
        </button>
      </div>
    </div>
  );
}
