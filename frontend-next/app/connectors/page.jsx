"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { 
  Key, Database, Globe, CheckCircle2, XCircle, AlertCircle, 
  Eye, EyeOff, Loader2, RefreshCw, Zap, ShieldCheck, Sparkles 
} from "lucide-react";

export default function ConnectorsPage() {
  // --- NVIDIA State ---
  const [nvidiaKey, setNvidiaKey] = useState("");
  const [showNvidiaKey, setShowNvidiaKey] = useState(false);
  const [nvidiaTesting, setNvidiaTesting] = useState(false);
  const [nvidiaSaving, setNvidiaSaving] = useState(false);
  const [nvidiaStatus, setNvidiaStatus] = useState(null); // { connected, message, models }
  const [nvidiaError, setNvidiaError] = useState(null);

  // --- Supabase State ---
  const [supabaseUrl, setSupabaseUrl] = useState("");
  const [supabaseAnonKey, setSupabaseAnonKey] = useState("");
  const [supabaseServiceKey, setSupabaseServiceKey] = useState("");
  const [supabaseDbPassword, setSupabaseDbPassword] = useState("");
  const [showSupabaseKeys, setShowSupabaseKeys] = useState(false);
  const [supabaseTesting, setSupabaseTesting] = useState(false);
  const [supabaseSaving, setSupabaseSaving] = useState(false);
  const [supabaseStatus, setSupabaseStatus] = useState(null); // { connected, tables_created, message }
  const [supabaseError, setSupabaseError] = useState(null);

  // --- WordPress State ---
  const [wpUrl, setWpUrl] = useState("https://accident.innovatcs.com");
  const [wpUsername, setWpUsername] = useState("");
  const [wpAppPassword, setWpAppPassword] = useState("");
  const [showWpPassword, setShowWpPassword] = useState(false);
  const [wpTesting, setWpTesting] = useState(false);
  const [wpSaving, setWpSaving] = useState(false);
  const [wpStatus, setWpStatus] = useState(null); // { connected, user, recent_posts, message }
  const [wpError, setWpError] = useState(null);

  // --- Autonomous Toggle ---
  const [autonomousOn, setAutonomousOn] = useState(true);
  const [autoUpdating, setAutoUpdating] = useState(false);

  // Load existing status on mount
  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/connectors/status");
      if (res.ok) {
        const data = await res.json();
        if (data.nvidia?.connected) {
          setNvidiaStatus({ connected: true, message: "Connected & Active" });
        }
        if (data.supabase?.connected) {
          setSupabaseStatus({ connected: true, tables_created: data.supabase.tables_count || 10, message: "10 tables verified" });
          if (data.supabase.url) setSupabaseUrl(data.supabase.url);
        }
        if (data.wordpress?.connected) {
          setWpStatus({ connected: true, message: `Connected to ${data.wordpress.site_url || 'WordPress'}` });
          if (data.wordpress.site_url) setWpUrl(data.wordpress.site_url);
          if (data.wordpress.username) setWpUsername(data.wordpress.username);
        }
        if (data.autonomous) {
          setAutonomousOn(data.autonomous.auto_publish ?? true);
        }
      }
    } catch (e) {
      console.warn("Status check failed:", e);
    }
  };

  // --- NVIDIA Handlers ---
  const handleTestNvidia = async () => {
    if (!nvidiaKey) {
      setNvidiaError("Please enter an NVIDIA API Key");
      return;
    }
    setNvidiaTesting(true);
    setNvidiaError(null);
    try {
      const res = await fetch("http://localhost:8000/api/connectors/test-nvidia", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: nvidiaKey }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "NVIDIA connection failed");
      setNvidiaStatus({ connected: true, models: data.models, message: data.message });
    } catch (err) {
      setNvidiaError(err.message);
      setNvidiaStatus({ connected: false });
    } finally {
      setNvidiaTesting(false);
    }
  };

  const handleSaveNvidia = async () => {
    if (!nvidiaKey) {
      setNvidiaError("Please enter an NVIDIA API Key");
      return;
    }
    setNvidiaSaving(true);
    setNvidiaError(null);
    try {
      const res = await fetch("http://localhost:8000/api/connectors/save-nvidia", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: nvidiaKey }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to save NVIDIA key");
      setNvidiaStatus((prev) => ({ ...(prev || {}), connected: true, message: "Key saved successfully ✅" }));
    } catch (err) {
      setNvidiaError(err.message);
    } finally {
      setNvidiaSaving(false);
    }
  };

  // --- Supabase Handlers ---
  const handleTestSupabase = async () => {
    if (!supabaseUrl || !supabaseAnonKey) {
      setSupabaseError("Supabase URL and Anon Key are required");
      return;
    }
    setSupabaseTesting(true);
    setSupabaseError(null);
    try {
      const res = await fetch("http://localhost:8000/api/connectors/test-supabase", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          supabase_url: supabaseUrl,
          anon_key: supabaseAnonKey,
          service_key: supabaseServiceKey,
          db_password: supabaseDbPassword,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Supabase connection failed");
      setSupabaseStatus({ connected: true, message: data.message });
    } catch (err) {
      setSupabaseError(err.message);
      setSupabaseStatus({ connected: false });
    } finally {
      setSupabaseTesting(false);
    }
  };

  const handleSetupSupabase = async () => {
    if (!supabaseUrl || !supabaseAnonKey || !supabaseServiceKey || !supabaseDbPassword) {
      setSupabaseError("All 4 fields are required to create database tables and vector extension");
      return;
    }
    setSupabaseSaving(true);
    setSupabaseError(null);
    try {
      const res = await fetch("http://localhost:8000/api/setup/supabase", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          supabase_url: supabaseUrl,
          anon_key: supabaseAnonKey,
          service_key: supabaseServiceKey,
          db_password: supabaseDbPassword,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Supabase setup failed");
      setSupabaseStatus({
        connected: true,
        tables_created: data.tables_created || 10,
        message: `✅ Boom! ${data.tables_created || 10} tables created with vector(1536) & RPCs!`,
      });
    } catch (err) {
      setSupabaseError(err.message);
    } finally {
      setSupabaseSaving(false);
    }
  };

  // --- WordPress Handlers ---
  const handleTestWordPress = async () => {
    if (!wpUrl || !wpUsername || !wpAppPassword) {
      setWpError("WordPress Site URL, Username, and Application Password are required");
      return;
    }
    setWpTesting(true);
    setWpError(null);
    try {
      const res = await fetch("http://localhost:8000/api/wordpress/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          site_url: wpUrl,
          wp_username: wpUsername,
          wp_app_password: wpAppPassword,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "WordPress connection failed");
      setWpStatus({
        connected: true,
        user: data.user,
        recent_posts: data.recent_posts || [],
        message: `Connected as ${data.user?.name || wpUsername}`,
      });
    } catch (err) {
      setWpError(err.message);
      setWpStatus({ connected: false });
    } finally {
      setWpTesting(false);
    }
  };

  const handleSaveWordPress = async () => {
    if (!wpUrl || !wpUsername || !wpAppPassword) {
      setWpError("WordPress credentials required to save");
      return;
    }
    setWpSaving(true);
    setWpError(null);
    try {
      const res = await fetch("http://localhost:8000/api/wordpress/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          site_url: wpUrl,
          wp_username: wpUsername,
          wp_app_password: wpAppPassword,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to save WordPress credentials");
      setWpStatus((prev) => ({ ...(prev || {}), connected: true, message: "WordPress connection saved! ✅" }));
    } catch (err) {
      setWpError(err.message);
    } finally {
      setWpSaving(false);
    }
  };

  // --- Autonomous Toggle Handler ---
  const handleToggleAutonomous = async () => {
    const nextState = !autonomousOn;
    setAutoUpdating(true);
    try {
      const res = await fetch("http://localhost:8000/api/autonomous/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          auto_publish: nextState,
          auto_generate: nextState,
          auto_refresh: nextState,
        }),
      });
      if (res.ok) {
        setAutonomousOn(nextState);
      }
    } catch (e) {
      console.warn("Autonomous settings error:", e);
      setAutonomousOn(nextState);
    } finally {
      setAutoUpdating(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-200 p-6 md:p-8">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800 pb-6">
          <div>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-orange-500/10 text-orange-400 rounded-lg border border-orange-500/20">
                <Zap className="w-6 h-6" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white tracking-tight">API Connectors & System Integrations</h1>
                <p className="text-sm text-gray-400">Configure NVIDIA NIM inference, Supabase pgvector database, and WordPress REST publishing.</p>
              </div>
            </div>
          </div>

          {/* Autonomous Mode Toggle */}
          <div className="flex items-center gap-4 bg-gray-900/90 border border-gray-800 p-3 rounded-xl">
            <div className="flex flex-col text-right">
              <span className="text-xs font-semibold uppercase tracking-wider text-gray-300">
                🤖 Autonomous Engine Mode
              </span>
              <span className="text-xs text-gray-400">
                {autonomousOn ? "Auto-write & publish enabled" : "Human approval required"}
              </span>
            </div>
            <button
              onClick={handleToggleAutonomous}
              disabled={autoUpdating}
              className={`relative inline-flex h-7 w-14 items-center rounded-full transition-colors focus:outline-none ${
                autonomousOn ? "bg-emerald-600" : "bg-gray-700"
              }`}
            >
              <span
                className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform ${
                  autonomousOn ? "translate-x-8" : "translate-x-1"
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      {/* 3 Cards Grid */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* ================= CARD A: NVIDIA NIM ================= */}
        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-6 flex flex-col justify-between shadow-xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-2xl pointer-events-none" />
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-emerald-500/10 text-emerald-400 rounded-lg border border-emerald-500/20">
                  <Key className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-lg text-white">Card A: NVIDIA NIM</h3>
                  <p className="text-xs text-gray-400">LLM Inference & Embeddings</p>
                </div>
              </div>
              {nvidiaStatus?.connected ? (
                <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded-full">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Connected
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 bg-gray-800 text-gray-400 rounded-full">
                  Not Configured
                </span>
              )}
            </div>

            <div className="space-y-4 my-4">
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1.5">
                  NVIDIA API Key <span className="text-red-400">*</span>
                </label>
                <div className="relative">
                  <input
                    type={showNvidiaKey ? "text" : "password"}
                    placeholder="nvapi-..."
                    value={nvidiaKey}
                    onChange={(e) => setNvidiaKey(e.target.value)}
                    className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3.5 py-2.5 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowNvidiaKey(!showNvidiaKey)}
                    className="absolute right-3 top-3 text-gray-500 hover:text-gray-300"
                  >
                    {showNvidiaKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-1.5">
                  Get your free API key at{" "}
                  <a
                    href="https://build.nvidia.com/account/api-keys"
                    target="_blank"
                    rel="noreferrer"
                    className="text-emerald-400 hover:underline"
                  >
                    build.nvidia.com/account/api-keys
                  </a>
                </p>
              </div>

              {nvidiaError && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <span>{nvidiaError}</span>
                </div>
              )}

              {nvidiaStatus?.models && nvidiaStatus.models.length > 0 && (
                <div className="p-3 bg-emerald-500/5 border border-emerald-500/20 rounded-lg">
                  <p className="text-xs font-semibold text-emerald-400 mb-1.5">
                    Available Models ({nvidiaStatus.models.length}+):
                  </p>
                  <div className="max-h-24 overflow-y-auto text-[11px] font-mono text-gray-400 space-y-0.5">
                    {nvidiaStatus.models.map((m, idx) => (
                      <div key={idx} className="truncate">• {m}</div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="flex gap-2 pt-4 border-t border-gray-800">
            <button
              onClick={handleTestNvidia}
              disabled={nvidiaTesting}
              className="flex-1 py-2.5 px-3 bg-gray-800 hover:bg-gray-700 text-white rounded-lg text-xs font-medium transition flex items-center justify-center gap-1.5 border border-gray-700"
            >
              {nvidiaTesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
              Test Connection
            </button>
            <button
              onClick={handleSaveNvidia}
              disabled={nvidiaSaving}
              className="flex-1 py-2.5 px-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium transition flex items-center justify-center gap-1.5 shadow-lg shadow-emerald-900/30"
            >
              {nvidiaSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
              Save API Key
            </button>
          </div>
        </div>

        {/* ================= CARD B: SUPABASE & PGVECTOR ================= */}
        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-6 flex flex-col justify-between shadow-xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/5 rounded-full blur-2xl pointer-events-none" />
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-blue-500/10 text-blue-400 rounded-lg border border-blue-500/20">
                  <Database className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-lg text-white">Card B: Supabase</h3>
                  <p className="text-xs text-gray-400">PostgreSQL + Vector(1536)</p>
                </div>
              </div>
              {supabaseStatus?.connected ? (
                <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 bg-blue-500/10 text-blue-400 border border-blue-500/30 rounded-full">
                  <CheckCircle2 className="w-3.5 h-3.5" /> {supabaseStatus.tables_created || 10} Tables
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 bg-gray-800 text-gray-400 rounded-full">
                  Not Setup
                </span>
              )}
            </div>

            <div className="space-y-3 my-4">
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Supabase URL</label>
                <input
                  type="text"
                  placeholder="https://xyz.supabase.co"
                  value={supabaseUrl}
                  onChange={(e) => setSupabaseUrl(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-xs text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Anon Public Key</label>
                <input
                  type={showSupabaseKeys ? "text" : "password"}
                  placeholder="eyJhbGciOi..."
                  value={supabaseAnonKey}
                  onChange={(e) => setSupabaseAnonKey(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-xs text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Service Role Key</label>
                <input
                  type={showSupabaseKeys ? "text" : "password"}
                  placeholder="eyJhbGciOi..."
                  value={supabaseServiceKey}
                  onChange={(e) => setSupabaseServiceKey(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-xs text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-gray-300">Database Password</label>
                  <button
                    type="button"
                    onClick={() => setShowSupabaseKeys(!showSupabaseKeys)}
                    className="text-[11px] text-gray-500 hover:text-gray-300 flex items-center gap-1"
                  >
                    {showSupabaseKeys ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                    {showSupabaseKeys ? "Hide" : "Show"}
                  </button>
                </div>
                <input
                  type={showSupabaseKeys ? "text" : "password"}
                  placeholder="Supabase DB Password"
                  value={supabaseDbPassword}
                  onChange={(e) => setSupabaseDbPassword(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-xs text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>

              <p className="text-[11px] text-gray-500">
                Settings at{" "}
                <a
                  href="https://supabase.com/dashboard"
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-400 hover:underline"
                >
                  Supabase Dashboard -&gt; Settings -&gt; API & Database
                </a>
              </p>

              {supabaseError && (
                <div className="p-2.5 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400">
                  {supabaseError}
                </div>
              )}

              {supabaseStatus?.message && (
                <div className="p-2.5 bg-blue-500/10 border border-blue-500/20 rounded-lg text-xs text-blue-400">
                  {supabaseStatus.message}
                </div>
              )}
            </div>
          </div>

          <div className="flex gap-2 pt-4 border-t border-gray-800">
            <button
              onClick={handleTestSupabase}
              disabled={supabaseTesting}
              className="flex-1 py-2.5 px-3 bg-gray-800 hover:bg-gray-700 text-white rounded-lg text-xs font-medium transition flex items-center justify-center gap-1.5 border border-gray-700"
            >
              {supabaseTesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
              Test Connection
            </button>
            <button
              onClick={handleSetupSupabase}
              disabled={supabaseSaving}
              className="flex-1 py-2.5 px-3 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium transition flex items-center justify-center gap-1.5 shadow-lg shadow-blue-900/30"
            >
              {supabaseSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              Save & Create Tables
            </button>
          </div>
        </div>

        {/* ================= CARD C: WORDPRESS ================= */}
        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-6 flex flex-col justify-between shadow-xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/5 rounded-full blur-2xl pointer-events-none" />
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-purple-500/10 text-purple-400 rounded-lg border border-purple-500/20">
                  <Globe className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-lg text-white">Card C: WordPress</h3>
                  <p className="text-xs text-gray-400">REST API Backend Proxy</p>
                </div>
              </div>
              {wpStatus?.connected ? (
                <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 bg-purple-500/10 text-purple-400 border border-purple-500/30 rounded-full">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Connected
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 bg-gray-800 text-gray-400 rounded-full">
                  Not Linked
                </span>
              )}
            </div>

            <div className="space-y-3 my-4">
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">WordPress Site URL</label>
                <input
                  type="text"
                  placeholder="https://accident.innovatcs.com"
                  value={wpUrl}
                  onChange={(e) => setWpUrl(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-xs text-gray-100 placeholder-gray-600 focus:outline-none focus:border-purple-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Username / Email</label>
                <input
                  type="text"
                  placeholder="admin or user"
                  value={wpUsername}
                  onChange={(e) => setWpUsername(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-xs text-gray-100 placeholder-gray-600 focus:outline-none focus:border-purple-500"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-gray-300">Application Password</label>
                  <button
                    type="button"
                    onClick={() => setShowWpPassword(!showWpPassword)}
                    className="text-[11px] text-gray-500 hover:text-gray-300 flex items-center gap-1"
                  >
                    {showWpPassword ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                    {showWpPassword ? "Hide" : "Show"}
                  </button>
                </div>
                <input
                  type={showWpPassword ? "text" : "password"}
                  placeholder="abcd efgh ijkl mnop"
                  value={wpAppPassword}
                  onChange={(e) => setWpAppPassword(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-xs text-gray-100 placeholder-gray-600 focus:outline-none focus:border-purple-500"
                />
              </div>

              <p className="text-[11px] text-gray-500">
                Generate in WP Admin -&gt; Users -&gt; Profile -&gt; Application Passwords.
              </p>

              {wpError && (
                <div className="p-2.5 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400">
                  {wpError}
                </div>
              )}

              {wpStatus?.recent_posts && wpStatus.recent_posts.length > 0 && (
                <div className="p-2.5 bg-purple-500/5 border border-purple-500/20 rounded-lg">
                  <p className="text-xs font-semibold text-purple-400 mb-1">Recent Posts Detected:</p>
                  <div className="max-h-20 overflow-y-auto text-[11px] font-mono text-gray-400 space-y-0.5">
                    {wpStatus.recent_posts.map((p, idx) => (
                      <div key={idx} className="truncate">• {p.title || `Post #${p.id}`}</div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="flex gap-2 pt-4 border-t border-gray-800">
            <button
              onClick={handleTestWordPress}
              disabled={wpTesting}
              className="flex-1 py-2.5 px-3 bg-gray-800 hover:bg-gray-700 text-white rounded-lg text-xs font-medium transition flex items-center justify-center gap-1.5 border border-gray-700"
            >
              {wpTesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
              Test Backend Proxy
            </button>
            <button
              onClick={handleSaveWordPress}
              disabled={wpSaving}
              className="flex-1 py-2.5 px-3 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-xs font-medium transition flex items-center justify-center gap-1.5 shadow-lg shadow-purple-900/30"
            >
              {wpSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />}
              Save & Encrypt
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
