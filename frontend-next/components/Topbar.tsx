"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { get } from "@/lib/api";
import { getCurrentWebsiteId, setCurrentWebsiteId } from "@/lib/website";

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/dashboard": "Dashboard",
  "/generate": "Generate Article",
  "/content": "Content Studio",
  "/brain": "Brand Brain",
  "/knowledge": "Knowledge Base",
  "/wordpress": "WordPress Manager",
  "/backlinks": "Backlinks & Authority",
  "/tech-seo": "Technical SEO",
  "/monitoring": "24/7 Monitoring",
  "/calendar": "Publishing Calendar",
  "/llms-txt": "LLMs.txt & GEO",
  "/connectors": "Connectors & Integrations",
  "/settings": "System Settings",
  "/websites": "Websites",
};

const sectionMap: Record<string, string> = {
  "/generate": "Core",
  "/content": "Core",
  "/backlinks": "SEO Studio",
  "/tech-seo": "SEO Studio",
  "/monitoring": "SEO Studio",
  "/calendar": "SEO Studio",
  "/brain": "AI Intelligence",
  "/knowledge": "AI Intelligence",
  "/llms-txt": "AI Intelligence",
  "/wordpress": "Integrations",
  "/connectors": "Integrations",
  "/settings": "Integrations",
};

function Topbar() {
  const pathname = usePathname();
  const [websites, setWebsites] = useState<any[]>([]);
  const [selectedWebsiteId, setSelectedWebsiteId] = useState<string>(getCurrentWebsiteId());

  const pageTitle = pageTitles[pathname] || "Dashboard";
  const section = sectionMap[pathname];

  useEffect(() => {
    async function loadWebsites() {
      try {
        let res = await get("/api/websites");
        if (!Array.isArray(res) || res.length === 0) {
          res = await get("/websites");
        }
        const sites = Array.isArray(res) && res.length > 0 
          ? res 
          : [{ id: "03b7febf-0c44-4830-a42a-cfcd84ae6464", domain: "accident.innovatcs.com" }];
        
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
        const fallback = [{ id: "03b7febf-0c44-4830-a42a-cfcd84ae6464", domain: "accident.innovatcs.com" }];
        setWebsites(fallback);
        setSelectedWebsiteId(fallback[0].id);
        setCurrentWebsiteId(fallback[0].id);
      }
    }
    loadWebsites();
  }, []);

  const handleWebsiteChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    setSelectedWebsiteId(value);
    if (value !== "+ Add Website") {
      setCurrentWebsiteId(value);
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("website-changed", { detail: value }));
      }
    }
  };

  return (
    <div className="topbar">
      <div className="topbar-left">
        <span>RankForge</span>
        {section && <><span className="breadcrumb-sq"></span><span>{section}</span></>}
        <span className="breadcrumb-sq"></span>
        <span className="topbar-title">{pageTitle}</span>
      </div>
      <div className="topbar-right">
        <div className="live-pill">
          <span className="live-dot"></span>
          <span>Live</span>
        </div>
        <select className="site-select" value={selectedWebsiteId} onChange={handleWebsiteChange}>
          {websites.length === 0 ? (
            <option value="default-website-id">No websites</option>
          ) : (
            websites.map((site: any) => (
              <option key={site.id} value={site.id}>{site.domain}</option>
            ))
          )}
          <option value="+ Add Website">+ Add Website</option>
        </select>
      </div>
    </div>
  );
}

export { Topbar };
