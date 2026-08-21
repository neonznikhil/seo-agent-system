"use client";

import { useEffect, useState } from "react";
import { get, post, put } from "@/lib/api";

interface Website {
  id: string;
  domain: string;
  cms_url: string | null;
  cms_user: string | null;
  app_password: string | null;
  gsc_property: string | null;
  status: string;
}

interface WebsiteForm {
  domain: string;
  cms_url: string | null;
  cms_user: string | null;
  app_password: string | null;
  gsc_property: string | null;
}

export default function WebsitesPage() {
  const [websites, setWebsites] = useState<Website[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Website | null>(null);
  const [form, setForm] = useState<WebsiteForm>({ domain: "", cms_url: null, cms_user: null, app_password: null, gsc_property: null });

  useEffect(() => {
    async function fetchWebsites() {
      try {
        setLoading(true);
        const res = await get("/websites");
        setWebsites(Array.isArray(res) ? res : []);
        setError(null);
      } catch (err) {
        setError("Failed to load websites");
        setWebsites([]);
      } finally {
        setLoading(false);
      }
    }

    fetchWebsites();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editing) {
        await put(`/websites/${editing.id}`, { status: editing.status });
        setEditing(null);
      } else {
        await post("/websites", { domain: form.domain, status: "active" });
      }
      setForm({ domain: "", cms_url: null, cms_user: null, app_password: null, gsc_property: null });
      fetchWebsites();
    } catch (err) {
      setError("Failed to save website");
    }
  };

  const fetchWebsites = async () => {
    try {
      const res = await get("/websites");
      setWebsites(Array.isArray(res) ? res : []);
    } catch {
      setWebsites([]);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2 text-[11px] text-muted">
          <span className="w-2 h-2 bg-accent" />
          <span>Websites</span>
        </div>
        <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">
          Websites
        </h1>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="bg-stone border border-ink p-4">
              <div className="text-[11px] text-muted uppercase tracking-wider mono-font mb-2">
                Loading...
              </div>
              <div className="h-8 w-24 bg-line animate-pulse" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2 text-[11px] text-muted">
          <span className="w-2 h-2 bg-accent" />
          <span>Websites</span>
        </div>
        <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">
          Websites
        </h1>
        <div className="bg-stone border border-ink p-4 text-center">
          <div className="text-[11px] text-ink mono-font">Error: {error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-[11px] text-muted">
        <span className="w-2 h-2 bg-accent" />
        <span>Websites</span>
      </div>
      <h1 className="text-3xl md:text-5xl font-bold dot-font tracking-tight">
        Websites
      </h1>

      {/* Add Website Form */}
      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Connect New Website</span>
        </div>
        <div className="panel-body">
          <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-[10px] text-muted uppercase tracking-wider mono-font block mb-1">Domain</label>
              <input
                className="field"
                type="text"
                placeholder="Enter website URL"
                value={form.domain}
                onChange={(e) => setForm({ ...form, domain: e.target.value })}
                required
              />
            </div>
            <div>
              <label className="text-[10px] text-muted uppercase tracking-wider mono-font block mb-1">CMS URL (optional)</label>
              <input
                className="field"
                type="text"
                placeholder="https://cms.example.com"
                value={form.cms_url || ""}
                onChange={(e) => setForm({ ...form, cms_url: e.target.value || null })}
              />
            </div>
            <div>
              <label className="text-[10px] text-muted uppercase tracking-wider mono-font block mb-1">CMS User (optional)</label>
              <input
                className="field"
                type="text"
                placeholder="CMS username"
                value={form.cms_user || ""}
                onChange={(e) => setForm({ ...form, cms_user: e.target.value || null })}
              />
            </div>
            <div>
              <label className="text-[10px] text-muted uppercase tracking-wider mono-font block mb-1">App Password (optional)</label>
              <input
                className="field"
                type="password"
                placeholder="Application password"
                value={form.app_password || ""}
                onChange={(e) => setForm({ ...form, app_password: e.target.value || null })}
              />
            </div>
            <div className="col-span-2">
              <label className="text-[10px] text-muted uppercase tracking-wider mono-font block mb-1">GSC Property (optional)</label>
              <input
                className="field"
                type="text"
                placeholder="https://search.google.com/search-console"
                value={form.gsc_property || ""}
                onChange={(e) => setForm({ ...form, gsc_property: e.target.value || null })}
              />
            </div>
            <div className="col-span-2 mt-2">
              <button className="btn btn-accent" type="submit">
                + Connect Site
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Websites List */}
      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Connected Properties</span>
          <span className="badge badge-green">Active</span>
        </div>
        <div className="panel-body">
          {websites.length === 0 ? (
            <div className="text-[11px] text-muted mono-font">No websites connected</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Domain</th>
                    <th>CMS URL</th>
                    <th>GSC Property</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {websites.map((website) => (
                    <tr key={website.id}>
                      <td>
                        <div className="site-card">
                          <div className="site-name">{website.domain}</div>
                        </div>
                      </td>
                      <td className="sm-val">{website.cms_url || "-"}</td>
                      <td className="sm-val">{website.gsc_property || "-"}</td>
                      <td>
                        <span className={`badge ${website.status === 'active' ? 'badge-green' : 'badge-amber'}`}>
                          {website.status}
                        </span>
                      </td>
                      <td>
                        <button className="btn btn-primary btn-sm">Manage</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
