"use client";

/**
 * Portfolio page: one table of all sites with health, indexation, clicks and
 * open issues. Single-site only does not work for a network.
 */

import { PortfolioTable } from "@/components/PortfolioTable";

export default function PortfolioPage() {
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
          Portfolio
        </h1>
        <p style={{ fontSize: "11.5px", color: "var(--muted)", margin: 0 }}>
          Every site in one table with health, indexation, clicks and open
          issues, so a network can be triaged in a single view.
        </p>
      </div>

      <PortfolioTable />
    </div>
  );
}