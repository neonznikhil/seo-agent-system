"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { get } from "@/lib/api";
import { getCurrentWebsiteId, setCurrentWebsiteId } from "@/lib/website";

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/dashboard": "Dashboard",
  "/websites": "Websites",
  "/content": "Content",
  "/writer": "Writer",
  "/research": "Research",
  "/clusters": "Clusters",
  "/links": "Links",
  "/decay": "Decay",
  "/backlinks": "Backlinks",
  "/tech-seo": "Tech SEO",
  "/monitoring": "Monitoring",
  "/knowledge": "Knowledge",
  "/memory": "Memory",
  "/llms-txt": "LLMs.txt",
  "/settings": "Settings",
  "/connectors": "Connectors",
  "/proposals": "Proposals",
};

const sectionMap: Record<string, string> = {
  "/connectors": "Settings",
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
        const res = await get("/websites");
        setWebsites(Array.isArray(res) ? res : []);
      } catch {
        setWebsites([]);
      }
    }
    loadWebsites();
  }, []);

  const handleWebsiteChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    setSelectedWebsiteId(value);
    if (value !== "+ Add Website") {
      setCurrentWebsiteId(value);
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
