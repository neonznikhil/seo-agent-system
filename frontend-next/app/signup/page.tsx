"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { setAuthSession } from "@/lib/auth";

export default function SignupPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password || !fullName) {
      setError("Please fill all required fields.");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters long.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: fullName.trim(),
          email: email.trim(),
          password,
          role: "owner",
        }),
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || data.message || "Registration failed.");
      }

      setAuthSession(data.token, data.user);
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Failed to create account.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-paper flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background Tech Grid Accents */}
      <div className="absolute inset-0 bg-[radial-gradient(#222_1px,transparent_1px)] [background-size:16px_16px] opacity-30 pointer-events-none" />

      <div className="w-full max-w-md bg-stone border border-ink/40 shadow-2xl relative z-10 p-8">
        {/* Header Branding */}
        <div className="flex items-center justify-between mb-8 pb-4 border-b border-ink/20">
          <div className="flex items-center gap-3">
            <div className="w-4 h-4 bg-accent animate-pulse" />
            <span className="dot-font text-2xl tracking-widest text-ink font-bold">
              RANK<span className="text-accent">FORGE</span>
            </span>
          </div>
          <span className="mono-font text-[10px] text-accent bg-accent/10 px-2 py-0.5 border border-accent/30 tracking-widest uppercase">
            REGISTER
          </span>
        </div>

        <div className="mb-6">
          <h1 className="dot-font text-xl text-ink font-bold tracking-wide">
            CREATE ACCOUNT
          </h1>
          <p className="mono-font text-xs text-muted mt-1">
            Provision dedicated autonomous SEO workspace.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-950/40 border border-red-500/50 text-red-400 mono-font text-xs flex items-center gap-2">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSignup} className="space-y-4">
          <div>
            <label className="block mono-font text-xs text-muted mb-1 uppercase tracking-wider">
              Operator Full Name
            </label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Alex Morgan"
              className="w-full bg-paper border border-ink/30 px-3 py-2 text-ink mono-font text-sm focus:border-accent focus:outline-none transition-colors"
              disabled={loading}
            />
          </div>

          <div>
            <label className="block mono-font text-xs text-muted mb-1 uppercase tracking-wider">
              Account Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="operator@domain.com"
              className="w-full bg-paper border border-ink/30 px-3 py-2 text-ink mono-font text-sm focus:border-accent focus:outline-none transition-colors"
              autoComplete="email"
              disabled={loading}
            />
          </div>

          <div>
            <label className="block mono-font text-xs text-muted mb-1 uppercase tracking-wider">
              Create Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••••••"
              className="w-full bg-paper border border-ink/30 px-3 py-2 text-ink mono-font text-sm focus:border-accent focus:outline-none transition-colors"
              autoComplete="new-password"
              autoCorrect="off"
              spellCheck={false}
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 py-2.5 bg-accent hover:bg-accent/90 text-paper font-bold mono-font text-xs uppercase tracking-widest transition-all shadow-md active:translate-y-0.5 disabled:opacity-50"
          >
            {loading ? "PROVISIONING..." : "CREATE WORKSPACE & ENTER →"}
          </button>
        </form>

        {/* Login Link */}
        <div className="mt-6 pt-6 border-t border-ink/20 text-center mono-font text-xs text-muted">
          Already have an account?{" "}
          <Link href="/login" className="text-accent hover:underline font-bold">
            Log In
          </Link>
        </div>
      </div>
    </div>
  );
}
