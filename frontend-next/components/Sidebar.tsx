"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";

const coreNav = [
  { label: "Dashboard", href: "/" },
  { label: "Websites", href: "/websites" },
  { label: "Writer", href: "/writer" },
  { label: "Content", href: "/content" },
  { label: "Approvals", href: "/approvals" },
];

const seoNav = [
  { label: "Backlinks", href: "/backlinks" },
  { label: "Tech SEO", href: "/tech-seo" },
  { label: "Monitoring", href: "/monitoring" },
];

const aiNav = [
  { label: "Workforce", href: "/workforce" },
  { label: "Brain", href: "/brain" },
  { label: "AEO / Schema", href: "/aeo" },
  { label: "LLMs.txt", href: "/llms-txt" },
];

const integrationsNav = [
  { label: "Connectors", href: "/connectors" },
  { label: "WordPress", href: "/wordpress" },
  { label: "Settings", href: "/settings" },
];

interface NavItem {
  label: string;
  href: string;
  badge?: number | string;
}

export function Sidebar() {
  const pathname = usePathname();
  const [theme, setTheme] = useState("light");

  useEffect(() => {
    const saved = localStorage.getItem("theme");
    if (saved) {
      setTheme(saved);
      document.documentElement.setAttribute("data-theme", saved);
    } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      setTheme("dark");
      document.documentElement.setAttribute("data-theme", "dark");
    }
  }, []);

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
  };

  const renderNav = (items: NavItem[], sectionLabel?: string) => (
    <>
      {sectionLabel && <div className="sidebar-section-label">{sectionLabel}</div>}
      {items.map((item) => {
        const isActive = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`nav-item ${isActive ? 'active' : ''}`}
          >
            <span className="nav-sq"></span>
            {item.label}
            {item.badge && <span className="nav-badge">{item.badge}</span>}
          </Link>
        );
      })}
    </>
  );

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-mark">*</div>
        <div className="logo-sq"></div>
        <span className="logo-text">RankForge</span>
      </div>
      <nav className="sidebar-nav">
        {renderNav(coreNav, "Core")}
        {renderNav(seoNav, "SEO Studio")}
        {renderNav(aiNav, "AI Intelligence")}
        {renderNav(integrationsNav, "Integrations")}
      </nav>
      <div className="sidebar-footer">
        <div className="sys-row">
          <div className="sys-indicators">
            <span className="sq-ind"></span>
            <span className="sq-ind"></span>
            <span className="sq-ind off"></span>
          </div>
          <button type="button" className="theme-toggle" onClick={toggleTheme} title="Toggle dark mode" aria-label="Toggle dark mode">
            <div className="theme-toggle-knob"></div>
            <span className="theme-toggle-icon" id="theme-icon">☀</span>
          </button>
        </div>
        <div className="sys-label">System Active</div>
        <div className="sidebar-ticker">
          <span className="ticker-inner">
            <span className="tick-sq"></span>AUTONOMOUS SEO &nbsp;/&nbsp;
            <span className="tick-sq"></span>REAL-TIME &nbsp;/&nbsp;
            <span className="tick-sq"></span>AI AGENTS RUNNING &nbsp;&nbsp;&nbsp;
            <span className="tick-sq"></span>AUTONOMOUS SEO &nbsp;/&nbsp;
            <span className="tick-sq"></span>REAL-TIME &nbsp;/&nbsp;
            <span className="tick-sq"></span>AI AGENTS RUNNING
          </span>
        </div>
      </div>
    </aside>
  );
}
