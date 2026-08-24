"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { post, get } from "@/lib/api";
import SupabaseHelp from "./supabase-help";

export default function SetupPage() {
  const router = useRouter();
  const [supabaseUrl, setSupabaseUrl] = useState("");
  const [anonKey, setAnonKey] = useState("");
  const [serviceKey, setServiceKey] = useState("");
  const [dbPassword, setDbPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [alreadyConnected, setAlreadyConnected] = useState(false);
  const [checkingStatus, setCheckingStatus] = useState(true);

  useEffect(() => {
    async function checkStatus() {
      try {
        const data = await get("/setup/status");
        if (data?.connected) {
          setAlreadyConnected(true);
        }
      } catch (err) {
        console.error("Failed to check setup status", err);
      } finally {
        setCheckingStatus(false);
      }
    }
    checkStatus();
  }, []);

  async function handleConnect(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (!supabaseUrl || !anonKey || !serviceKey || !dbPassword) {
      setError("All fields are required");
      return;
    }

    setLoading(true);
    try {
      const data = await post("/setup/supabase", {
        supabase_url: supabaseUrl,
        anon_key: anonKey,
        service_key: serviceKey,
        db_password: dbPassword,
      });
      if (data?.success) {
        setSuccess(true);
        localStorage.setItem("supabase_connected", "true");
      }
    } catch (err: any) {
      setError(err.message || "Failed to connect to Supabase");
    } finally {
      setLoading(false);
    }
  }

  if (checkingStatus) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="max-w-md w-full bg-white shadow-md rounded-lg p-8">
          <div className="flex flex-col items-center">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mb-4" />
            <p className="text-gray-600">Checking connection...</p>
          </div>
        </div>
      </div>
    );
  }

  if (alreadyConnected) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="max-w-md w-full bg-white shadow-md rounded-lg p-8 text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">
            ✅ Already connected
          </h1>
          <p className="text-gray-600 mb-6">
            Your Supabase setup is complete.
          </p>
          <button
            onClick={() => router.push("/dashboard")}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition-colors"
          >
            Go to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full bg-white shadow-md rounded-lg p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-2 text-center">
          1-Click Supabase Setup
        </h1>
        <p className="text-gray-600 text-center mb-6">
          Enter your Supabase credentials to get started.
        </p>

        <SupabaseHelp />

        {success ? (
          <div className="mt-6">
            <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded">
              <p className="font-medium">✅ 7 tables created!</p>
              <p className="text-sm mt-1">agent_memory, blogs, etc.</p>
            </div>
            <button
              onClick={() => router.push("/dashboard")}
              className="w-full mt-4 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition-colors"
            >
              Go to Dashboard
            </button>
          </div>
        ) : (
          <form onSubmit={handleConnect} className="space-y-4 mt-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Supabase URL
              </label>
              <input
                type="text"
                value={supabaseUrl}
                onChange={(e) => setSupabaseUrl(e.target.value)}
                placeholder="https://xxxx.supabase.co"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Anon Key
              </label>
              <input
                type="password"
                autoComplete="new-password"
                autoCorrect="off"
                spellCheck={false}
                value={anonKey}
                onChange={(e) => setAnonKey(e.target.value)}
                placeholder="eyJ..."
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Service Role Key
              </label>
              <input
                type="password"
                autoComplete="new-password"
                autoCorrect="off"
                spellCheck={false}
                value={serviceKey}
                onChange={(e) => setServiceKey(e.target.value)}
                placeholder="eyJ..."
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                DB Password
              </label>
              <input
                type="password"
                autoComplete="new-password"
                autoCorrect="off"
                spellCheck={false}
                value={dbPassword}
                onChange={(e) => setDbPassword(e.target.value)}
                placeholder="from Supabase > Database"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                <p className="text-sm">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-medium py-2 px-4 rounded-md transition-colors"
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                  Creating tables...
                </span>
              ) : (
                "Connect & Create All Tables - Boom"
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
