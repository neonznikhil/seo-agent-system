"use client";

import { useState, useEffect } from "react";
import { get, post } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function ConnectWordPress() {
  const [status, setStatus] = useState<{ connected: boolean; site_url?: string; username?: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    checkStatus();
  }, []);

  async function checkStatus() {
    setLoading(true);
    setError(null);
    try {
      const data = await get("/wordpress/status");
      setStatus(data);
    } catch (err: any) {
      setError(err.message || "Failed to check WordPress connection status");
    } finally {
      setLoading(false);
    }
  }

  async function handleConnect() {
    setActionLoading(true);
    setError(null);
    try {
      const data = await get("/wordpress/authorize-url");
      if (data.authorize_url) {
        window.location.href = data.authorize_url;
      }
    } catch (err: any) {
      setError(err.message || "Failed to get authorization URL");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDisconnect() {
    setActionLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/wordpress/disconnect`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          "X-User-Id": typeof window !== "undefined" ? (localStorage.getItem("x-user-id") || "anonymous") : "anonymous",
        },
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Disconnect failed: ${res.status} - ${text}`);
      }
      setStatus({ connected: false });
    } catch (err: any) {
      setError(err.message || "Failed to disconnect WordPress");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="bg-stone border border-ink p-4">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-ink border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-muted mono-font">Checking WordPress connection...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-stone border border-ink p-4">
      <div className="text-[11px] text-muted uppercase tracking-wider mono-font mb-3">WordPress</div>

      {error && (
        <div className="border border-red-800 bg-red-900/20 p-3 mb-3">
          <div className="text-xs text-red-400 mono-font">{error}</div>
        </div>
      )}

      {status?.connected ? (
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-sm text-ink font-bold">Connected</div>
            <div className="text-xs text-muted mono-font">
              {status.username} @ {status.site_url}
            </div>
          </div>
          <button
            onClick={handleDisconnect}
            disabled={actionLoading}
            className={`px-4 py-2 border border-ink text-[11px] uppercase tracking-widest mono-font ${
              actionLoading ? "opacity-50 cursor-not-allowed" : "bg-paper hover:bg-stone"
            }`}
          >
            Disconnect
          </button>
        </div>
      ) : (
        <div className="flex items-center justify-between gap-4">
          <div className="text-sm text-ink">Not connected</div>
          <button
            onClick={handleConnect}
            disabled={actionLoading}
            className={`px-4 py-2 bg-ink text-paper text-[11px] uppercase tracking-widest mono-font ${
              actionLoading ? "opacity-50 cursor-not-allowed" : "hover:bg-stone"
            }`}
          >
            Connect WordPress
          </button>
        </div>
      )}
    </div>
  );
}
