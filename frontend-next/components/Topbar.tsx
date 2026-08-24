"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { get } from "@/lib/api";
import { getCurrentWebsiteId, setCurrentWebsiteId } from "@/lib/website";
import { getCurrentUser, clearAuthSession, UserProfile } from "@/lib/auth";

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/dashboard": "Dashboard",
  "/generate": "Generate Article",
  "/writer": "Autonomous Writer",
  "/content": "Content Studio",
  "/approvals": "Approval Queue",
  "/brain": "Brand Brain & Memory",
  "/knowledge": "Knowledge Base",
  "/wordpress": "WordPress Manager",
  "/backlinks": "Backlinks & Authority",
  "/tech-seo": "Technical SEO",
  "/monitoring": "24/7 Monitoring",
  "/workforce": "Autonomous Workforce",
  "/calendar": "Publishing Calendar",
  "/llms-txt": "LLMs.txt & GEO",
  "/connectors": "Connectors & Integrations",
  "/settings": "Account & System Settings",
  "/websites": "Websites",
  "/login": "Operator Login",
  "/signup": "Create Account",
};

const sectionMap: Record<string, string> = {
  "/generate": "Core",
  "/writer": "Core",
  "/content": "Core",
  "/approvals": "Core",
  "/backlinks": "SEO Studio",
  "/tech-seo": "SEO Studio",
  "/monitoring": "SEO Studio",
  "/calendar": "SEO Studio",
  "/workforce": "AI Intelligence",
  "/brain": "AI Intelligence",
  "/knowledge": "AI Intelligence",
  "/llms-txt": "AI Intelligence",
  "/wordpress": "Integrations",
  "/connectors": "Integrations",
  "/settings": "Account",
};

function Topbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [websites, setWebsites] = useState<any[]>([]);
  const [selectedWebsiteId, setSelectedWebsiteId] = useState<string>(getCurrentWebsiteId());
  const [user, setUser] = useState<UserProfile>(getCurrentUser());
  const [showUserMenu, setShowUserMenu] = useState(false);

  const pageTitle = pageTitles[pathname] || "Dashboard";
  const section = sectionMap[pathname];

  useEffect(() => {
    setUser(getCurrentUser());
    const handleAuth = (e: any) => {
      setUser(e.detail || getCurrentUser());
    };
    window.addEventListener("rankforge-auth-changed", handleAuth);
    return () => window.removeEventListener("rankforge-auth-changed", handleAuth);
  }, []);

  useEffect(() => {
    async function loadWebsites() {
      try {
        let res = await get("/api/websites");
        if (!Array.isArray(res) || res.length === 0) {
          res = await get("/websites");
        }
        const sites = Array.isArray(res) ? res : [];
        setWebsites(sites);
        
        const current = getCurrentWebsiteId();
        const exists = sites.some((s: any) => s.id === current);
        if (!exists && sites[0]) {
          setSelectedWebsiteId(sites[0].id);
          setCurrentWebsiteId(sites[0].id);
        } else if (current) {
          setSelectedWebsiteId(current);
        }
      } catch {
        setWebsites([]);
      }
    }
    loadWebsites();
    const handleWChange = (e: any) => {
      if (e?.detail) setSelectedWebsiteId(e.detail);
      loadWebsites();
    };
    window.addEventListener("website-changed", handleWChange);
    return () => window.removeEventListener("website-changed", handleWChange);
  }, []);

  const handleWebsiteChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    if (value === "+ Add Website") {
      router.push("/websites");
      return;
    }
    setSelectedWebsiteId(value);
    setCurrentWebsiteId(value);
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("website-changed", { detail: value }));
    }
  };

  const handleSignOut = () => {
    clearAuthSession();
    setShowUserMenu(false);
    router.push("/login");
  };

  return (
    <div className="topbar">
      <div className="topbar-left">
        <span>RankForge</span>
        {section && <><span className="breadcrumb-sq"></span><span>{section}</span></>}
        <span className="breadcrumb-sq"></span>
        <span className="topbar-title">{pageTitle}</span>
      </div>
      <div className="topbar-right flex items-center gap-3">
        <div className="live-pill">
          <span className="live-dot"></span>
          <span>Live</span>
        </div>

        <select className="site-select" value={selectedWebsiteId} onChange={handleWebsiteChange}>
          {websites.length === 0 ? (
            <option value="">+ Connect your website</option>
          ) : (
            websites.map((site: any) => (
              <option key={site.id} value={site.id}>{site.domain}</option>
            ))
          )}
          <option value="+ Add Website">+ Add Website</option>
        </select>

        {/* User Account Chip & Dropdown */}
        <div className="relative">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2 px-2.5 py-1 bg-stone border border-ink/40 hover:border-accent mono-font text-[11px] text-ink transition-colors"
          >
            <div className="w-4 h-4 rounded-full bg-accent/20 border border-accent text-accent flex items-center justify-center text-[9px] font-bold">
              {user.email ? user.email[0].toUpperCase() : "U"}
            </div>
            <span className="hidden sm:inline max-w-[120px] truncate text-muted">
              {user.email}
            </span>
            <span className="text-[9px] text-accent uppercase font-bold border border-accent/30 px-1">
              {user.role || "OWNER"}
            </span>
          </button>

          {showUserMenu && (
            <div className="absolute right-0 mt-1 w-52 bg-stone border border-ink shadow-2xl z-50 py-1">
              <div className="px-3 py-2 border-b border-ink/20">
                <div className="mono-font text-[10px] text-muted uppercase">Signed in as</div>
                <div className="mono-font text-xs text-ink font-bold truncate">{user.email}</div>
                <div className="mono-font text-[10px] text-accent mt-0.5">{user.full_name || "Lead Architect"}</div>
              </div>
              <Link
                href="/settings"
                onClick={() => setShowUserMenu(false)}
                className="block px-3 py-2 mono-font text-xs text-ink hover:bg-paper hover:text-accent transition-colors"
              >
                ⚙️ Account Settings
              </Link>
              <Link
                href="/websites"
                onClick={() => setShowUserMenu(false)}
                className="block px-3 py-2 mono-font text-xs text-ink hover:bg-paper hover:text-accent transition-colors"
              >
                🌐 Manage Websites
              </Link>
              <div className="border-t border-ink/20 my-1" />
              <button
                onClick={handleSignOut}
                className="w-full text-left px-3 py-2 mono-font text-xs text-red-400 hover:bg-red-950/30 transition-colors"
              >
                🚪 Sign Out
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export { Topbar };
