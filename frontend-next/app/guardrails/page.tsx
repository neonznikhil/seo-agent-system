"use client";

/**
 * Guardrails page: preview diff, undo, and change log for every automated
 * change to a live site. Legal/YMYL pages require a second reviewer.
 */

import { useEffect, useState } from "react";
import { GuardrailsPanel } from "@/components/GuardrailsPanel";
import { getCurrentWebsiteId } from "@/lib/website";

export default function GuardrailsPage() {
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
          Guardrails & Rollback
        </h1>
        <p style={{ fontSize: "11.5px", color: "var(--muted)", margin: 0 }}>
          Every automated change to a live site gets a preview diff, an undo
          button and a change log entry. Legal, medical and financial pages
          require a second reviewer before anything ships.
        </p>
      </div>

      {!websiteId ? (
        <div
          className="panel"
          style={{ padding: "28px 16px", textAlign: "center", fontSize: "11.5px", color: "var(--muted)" }}
        >
          Select a website to view its change log and propose changes.
        </div>
      ) : (
        <GuardrailsPanel websiteId={websiteId} />
      )}
    </div>
  );
}