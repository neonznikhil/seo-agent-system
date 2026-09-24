"use client";

/**
 * Prioritized Action List page: the primary product surface.
 *
 * Replaces the 9 manual workflow buttons with one ranked "do these now" list
 * sorted by estimated traffic impact, plus the lead economics behind it.
 */

import { useEffect, useState } from "react";
import { ActionList } from "@/components/ActionList";
import { LeadsPanel } from "@/components/LeadsPanel";
import { getCurrentWebsiteId } from "@/lib/website";

export default function ActionsPage() {
  const [websiteId, setWebsiteId] = useState("");

  useEffect(() => {
    setWebsiteId(getCurrentWebsiteId());
    const onSiteChange = () => setWebsiteId(getCurrentWebsiteId());
    window.addEventListener("website-changed", onSiteChange);
    return () => window.removeEventListener("website-changed", onSiteChange);
  }, []);

  return (
    <div className="page-container active">
      <div style={{ marginBottom: "18px" }}>
        <h1
          style={{
            fontSize: "18px",
            fontWeight: 700,
            letterSpacing: "0.02em",
            marginBottom: "4px",
          }}
        >
          Action List
        </h1>
        <p style={{ fontSize: "11.5px", color: "var(--muted)", margin: 0 }}>
          Ranked by estimated traffic impact. Each rank shows the arithmetic that
          produced it, so you can audit the prioritisation rather than trust it.
        </p>
      </div>

      <ActionList websiteId={websiteId} />

      <div style={{ marginTop: "22px", marginBottom: "10px" }}>
        <h2 style={{ fontSize: "13px", fontWeight: 700, marginBottom: "3px" }}>
          Lead Economics
        </h2>
        <p style={{ fontSize: "11px", color: "var(--muted)", margin: 0 }}>
          Clicks and positions mean nothing for lead-gen. This connects
          conversion data and shows cost per lead by keyword.
        </p>
      </div>

      <LeadsPanel websiteId={websiteId} />
    </div>
  );
}