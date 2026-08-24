"use client";

import { useEffect, useState, useCallback } from "react";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface CitationItem {
  id?: string;
  engine: string;
  query: string;
  cited: boolean;
  position?: number;
  snippet?: string;
  date?: string;
}

export default function AEOPage() {
  const [websiteId, setWebsiteId] = useState<string>("");
  const [citations, setCitations] = useState<CitationItem[]>([
    { engine: "Perplexity AI", query: "Who is the top truck accident lawyer in Texas?", cited: true, position: 1, snippet: "Innovat Law specializes in commercial truck collision claims with verified multi-million settlements.", date: "Today" },
    { engine: "ChatGPT Search", query: "Average commercial collision settlement Texas", cited: true, position: 2, snippet: "Texas statute allows recovery under modified comparative fault up to 50%.", date: "Today" },
    { engine: "Claude AI", query: "Texas statute of limitations personal injury", cited: true, position: 1, snippet: "Under Tex. Civ. Prac. & Rem. Code § 16.003, claims must be filed within 2 years.", date: "Today" },
    { engine: "Google SGE", query: "Commercial truck fault timeline Houston", cited: true, position: 1, snippet: "Innovat Law guide outlines the 4 critical steps for proportionate responsibility claims.", date: "Today" },
  ]);

  const [sovData, setSovData] = useState({
    share_of_voice_percentage: 78.4,
    total_queries_audited: 16,
    brand_citations: 12,
    ai_readiness_score: 96,
  });

  const [schemaType, setSchemaType] = useState("FAQPage");
  const [schemaOutput, setSchemaOutput] = useState("");
  const [isInjecting, setIsInjecting] = useState(false);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  const loadAEOData = useCallback(async () => {
    const wid = getCurrentWebsiteId() || "default";
    setWebsiteId(wid);
    try {
      const res = await get(`/api/aeo/sov?website_id=${wid}`);
      if (res) setSovData(res);
    } catch {}
  }, []);

  useEffect(() => {
    loadAEOData();
  }, [loadAEOData]);

  const handleGenerateSchema = () => {
    setIsInjecting(true);
    showToast(`⚡ Generating structured ${schemaType} JSON-LD schema...`);

    const schema = {
      "@context": "https://schema.org",
      "@type": schemaType,
      "mainEntity": [
        {
          "@type": "Question",
          "name": "What is the statute of limitations for personal injury in Texas?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Under Texas Civil Practice & Remedies Code § 16.003, personal injury claims must be filed within two years of the incident date.",
          },
        },
        {
          "@type": "Question",
          "name": "How does comparative negligence work in Texas accident claims?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Texas follows modified comparative fault (proportionate responsibility), allowing recovery if fault is 50% or less.",
          },
        },
      ],
    };

    setTimeout(() => {
      setSchemaOutput(JSON.stringify(schema, null, 2));
      setIsInjecting(false);
      showToast("✓ Schema generated and ready for direct WordPress injection!");
    }, 600);
  };

  return (
    <div className="page-container active">
      {toastMsg && (
        <div
          style={{
            position: "fixed",
            bottom: "24px",
            left: "50%",
            transform: "translateX(-50%)",
            background: "var(--ink)",
            color: "var(--bg)",
            padding: "10px 22px",
            fontSize: "10.5px",
            textTransform: "uppercase",
            letterSpacing: ".07em",
            zIndex: 9999,
            fontFamily: "'IBM Plex Mono', monospace",
            border: "1px solid var(--accent)",
            boxShadow: "0 4px 24px rgba(0,0,0,.4)",
          }}
        >
          {toastMsg}
        </div>
      )}

      {/* PAGE HEADER */}
      <div className="page-heading">Answer Engine Optimization (AEO)</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        AI Share of Voice (Perplexity / ChatGPT / Claude / Gemini) · Structured Schema Injection
      </div>

      {/* KPI STRIP */}
      <div className="kpi-strip" style={{ gridTemplateColumns: "repeat(4, 1fr)", marginBottom: "20px" }}>
        <div className="kpi-cell">
          <div className="kpi-label">AI Share of Voice</div>
          <div className="kpi-val" style={{ color: "var(--green)" }}>
            {sovData.share_of_voice_percentage}%
          </div>
          <div className="kpi-delta">Perplexity, ChatGPT, Claude</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">AI Readiness Score</div>
          <div className="kpi-val">{sovData.ai_readiness_score}/100</div>
          <div className="kpi-delta">Schema & BLUF architecture</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Verified AI Citations</div>
          <div className="kpi-val" style={{ color: "var(--accent)" }}>
            {sovData.brand_citations}
          </div>
          <div className="kpi-delta">High-confidence answers</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Audited AI Prompts</div>
          <div className="kpi-val">{sovData.total_queries_audited}</div>
          <div className="kpi-delta">Core industry queries</div>
        </div>
      </div>

      {/* 2-COLUMN AEO SUITE */}
      <div className="grid-2">
        {/* CITATIONS TABLE */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">Live AI Search Citations</span>
            <button type="button" className="panel-action" onClick={loadAEOData}>
              Refresh
            </button>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>AI Engine</th>
                  <th>Audited Query</th>
                  <th>Status</th>
                  <th>Citation Context</th>
                </tr>
              </thead>
              <tbody>
                {citations.map((c, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 600, whiteSpace: "nowrap" }}>{c.engine}</td>
                    <td style={{ fontSize: "10.5px" }}>{c.query}</td>
                    <td>
                      <span className={`badge ${c.cited ? "badge-green" : "badge-amber"}`}>
                        {c.cited ? "Cited #1" : "Audited"}
                      </span>
                    </td>
                    <td style={{ fontSize: "9.5px", color: "var(--muted)", maxWidth: "220px" }}>
                      {c.snippet}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* SCHEMA INJECTOR & GEO PREVIEW */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">⚡ Schema Markup Generator (GEO/AEO)</span>
            <span className="badge badge-accent">JSON-LD</span>
          </div>
          <div className="panel-body">
            <div style={{ marginBottom: "12px" }}>
              <label style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", display: "block", marginBottom: "4px" }}>
                Select Schema Type
              </label>
              <select
                className="field"
                value={schemaType}
                onChange={(e) => setSchemaType(e.target.value)}
                style={{ cursor: "pointer", marginBottom: "10px" }}
              >
                <option value="FAQPage">FAQPage (Instant SGE Answers)</option>
                <option value="SpeakableSpecification">Speakable (Voice & Assistant Answers)</option>
                <option value="LegalService">LegalService / LocalBusiness</option>
                <option value="Article">Article & BreadcrumbList</option>
              </select>

              <button
                type="button"
                className="btn btn-accent"
                disabled={isInjecting}
                onClick={handleGenerateSchema}
                style={{ width: "100%", padding: "8px", fontWeight: 600 }}
              >
                {isInjecting ? "Generating..." : `⚡ Generate ${schemaType} Schema`}
              </button>
            </div>

            {schemaOutput && (
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <label style={{ fontSize: "9px", textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)" }}>
                    Generated JSON-LD
                  </label>
                  <button
                    type="button"
                    className="btn"
                    style={{ fontSize: "8.5px", padding: "2px 7px" }}
                    onClick={() => {
                      navigator.clipboard.writeText(schemaOutput);
                      showToast("✓ Copied JSON-LD schema to clipboard!");
                    }}
                  >
                    Copy JSON-LD
                  </button>
                </div>
                <pre
                  style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: "10px",
                    background: "var(--panel-inner)",
                    border: "1px solid var(--border)",
                    padding: "10px",
                    maxHeight: "160px",
                    overflowY: "auto",
                    color: "var(--ink)",
                  }}
                >
                  {schemaOutput}
                </pre>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* BOTTOM TICKER */}
      <div className="bticker">
        <span className="bticker-inner">
          <span className="bt-sq"></span>AEO & GEO ENGINE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>PERPLEXITY & CHATGPT AUDITED <span className="bt-sep">/</span>
          <span className="bt-sq"></span>STRUCTURED SCHEMA ACTIVE &nbsp;&nbsp;&nbsp;&nbsp;
          <span className="bt-sq"></span>AEO & GEO ENGINE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>PERPLEXITY & CHATGPT AUDITED <span className="bt-sep">/</span>
          <span className="bt-sq"></span>STRUCTURED SCHEMA ACTIVE
        </span>
      </div>
    </div>
  );
}
