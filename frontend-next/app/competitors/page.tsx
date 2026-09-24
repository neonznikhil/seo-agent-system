"use client";

/**
 * Competitor tracking page: share of voice on your keyword set, their new
 * pages, and where they outrank you.
 */

import { useEffect, useState } from "react";
import { CompetitorPanel } from "@/components/CompetitorPanel";
import { fetchPortfolio } from "@/lib/intelligence";
import { getCurrentWebsiteId } from "@/lib/website";

export default function CompetitorsPage() {
  const [websiteId, setWebsiteId] = useState("");
  const [ownDomain, setOwnDomain] = useState("");

  useEffect(() => {
    const wid = getCurrentWebsiteId();
    setWebsiteId(wid);

    // Prefill our domain from the portfolio so the comparison baseline is clear.
    if (wid) {
      fetchPortfolio()
        .then((p) => {
          const match = p.sites.find((s) => s.website_id === wid);
          if (match) setOwnDomain(match.domain);
        })
        .catch(() => {});
    }

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
          Competitors
        </h1>
        <p style={{ fontSize: "11.5px", color: "var(--muted)", margin: 0 }}>
          Share of voice on your keyword set, their new pages, and where they
          outrank you. Positions are saved so the comparison is reproducible.
        </p>
      </div>

      {!websiteId ? (
        <div
          className="panel"
          style={{ padding: "28px 16px", textAlign: "center", fontSize: "11.5px", color: "var(--muted)" }}
        >
          Select a website to set up its competitor set.
        </div>
      ) : (
        <CompetitorPanel websiteId={websiteId} ownDomain={ownDomain} />
      )}
    </div>
  );
}