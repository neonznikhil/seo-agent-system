"use client";

/**
 * Proof page: after a fix ships, the 28-day position and traffic lift.
 * This is the ROI evidence view.
 */

import { useEffect, useState } from "react";
import { MeasurementPanel } from "@/components/MeasurementPanel";
import { getCurrentWebsiteId } from "@/lib/website";

export default function ProofPage() {
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
          Proof of Work
        </h1>
        <p style={{ fontSize: "11.5px", color: "var(--muted)", margin: 0 }}>
          Every shipped fix is tracked for 28 days. Lift is measured against a
          control set where one exists, so seasonality is never reported as
          success.
        </p>
      </div>

      {!websiteId ? (
        <div
          className="panel"
          style={{ padding: "28px 16px", textAlign: "center", fontSize: "11.5px", color: "var(--muted)" }}
        >
          Select a website to see its measurement windows.
        </div>
      ) : (
        <MeasurementPanel websiteId={websiteId} />
      )}
    </div>
  );
}