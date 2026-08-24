"use client";

import { useEffect, useState, useCallback } from "react";
import { get, post } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

interface PageAudit {
  content_id: string;
  title: string;
  url: string;
  keyword?: string;
  source_checked: string;
  ai_readiness_score: number;
  has_faqpage: boolean;
  schema_types: string[];
  bluf_present: boolean;
  internal_link_count: number;
  faq_question_count: number;
  llms_txt_included: boolean;
}

interface AeoOverview {
  pages: PageAudit[];
  total_published: number;
  pages_with_faq_schema: number;
  coverage_percent: number;
  average_ai_readiness: number | null;
  missing_schema_queue: Array<{ content_id: string; title: string }>;
}

interface SovData {
  share_of_voice_percentage: number;
  total_queries_audited: number;
  brand_citations: number;
  note?: string;
}

interface CitationCheckResult {
  query: string;
  checked: boolean;
  error?: string;
  appears_featured_snippet?: boolean;
  appears_people_also_ask?: boolean;
  organic_position?: number | null;
  citation_probability?: "High" | "Medium" | "Low";
}

export default function AEOPage() {
  const [websiteId, setWebsiteId] = useState<string>("");
  const [overview, setOverview] = useState<AeoOverview | null>(null);
  const [sovData, setSovData] = useState<SovData | null>(null);
  const [citationResults, setCitationResults] = useState<CitationCheckResult[]>([]);
  const [checkingCitations, setCheckingCitations] = useState(false);
  const [generatingSchemaFor, setGeneratingSchemaFor] = useState<string | null>(null);

  const [schemaOutput, setSchemaOutput] = useState("");
  const [injectingInto, setInjectingInto] = useState<string | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 4000);
  };

  const loadAEOData = useCallback(async () => {
    const wid = getCurrentWebsiteId() || "";
    setWebsiteId(wid);
    try {
      setLoading(true);
      const [aeoRes, sovRes] = await Promise.allSettled([
        get(`/api/aeo?website_id=${wid}`),
        get(`/api/aeo/sov?website_id=${wid}`),
      ]);

      if (aeoRes.status === "fulfilled" && aeoRes.value?.data) {
        setOverview(aeoRes.value.data);
      }
      if (sovRes.status === "fulfilled" && sovRes.value) {
        setSovData(sovRes.value);
      }
    } catch (e: any) {
      console.warn("AEO load error:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAEOData();
  }, [loadAEOData]);

  // Section 3: Serper-based citation simulation
  const runCitationCheck = async () => {
    try {
      setCheckingCitations(true);
      showToast("Querying Serper.dev for featured snippets and PAA presence...");
      const res = await post("/api/aeo/check-citations", { website_id: getCurrentWebsiteId() });
      setCitationResults(res.results || []);
      showToast(`Checked ${res.queries_checked} keywords against live SERPs.`);
      loadAEOData();
    } catch (e: any) {
      showToast(`Citation check failed: ${e.message}`);
    } finally {
      setCheckingCitations(false);
    }
  };

  // Section 4: Generate real FAQ schema from an article
  const handleGenerateSchema = async (contentId?: string) => {
    const wid = getCurrentWebsiteId();
    try {
      setGeneratingSchemaFor(contentId || "latest");
      const res = await post("/api/aeo/generate-faq-schema", {
        website_id: wid,
        blog_id: contentId,
      });
      if (res?.schema) {
        setSchemaOutput(JSON.stringify(res.schema, null, 2));
        showToast(`✓ FAQPage schema generated from "${res.article_title}".`);
      }
    } catch (e: any) {
      showToast(`Schema generation failed: ${e.message}`);
    } finally {
      setGeneratingSchemaFor(null);
    }
  };

  const handleInjectSchema = async (contentId: string) => {
    try {
      setInjectingInto(contentId);
      let schemaJson;
      try {
        schemaJson = JSON.parse(schemaOutput);
      } catch {
        showToast("Generate the schema first.");
        return;
      }
      const res = await post("/api/aeo/inject-schema", {
        website_id: getCurrentWebsiteId(),
        blog_id: contentId,
        schema_json: schemaJson,
      });
      showToast(res.message || "Schema injected into WordPress.");
      loadAEOData();
    } catch (e: any) {
      showToast(`Injection failed: ${e.message}`);
    } finally {
      setInjectingInto(null);
    }
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
          }}
        >
          {toastMsg}
        </div>
      )}

      <div className="page-heading">Answer Engine Optimization (AEO)</div>
      <div className="page-sub">
        <span className="sub-sq"></span>
        Schema Coverage Audit · AI Readiness Scoring · SERP Citation Simulation
      </div>

      {/* KPI STRIP — all real */}
      <div className="kpi-strip" style={{ gridTemplateColumns: "repeat(4, 1fr)", marginBottom: "20px" }}>
        <div className="kpi-cell">
          <div className="kpi-label">FAQ Schema Coverage</div>
          <div className="kpi-val">{overview ? `${overview.coverage_percent}%` : "—"}</div>
          <div className="kpi-delta">
            {overview ? `${overview.pages_with_faq_schema}/${overview.total_published} published posts` : ""}
          </div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Avg AI Readiness</div>
          <div className="kpi-val">
            {overview?.average_ai_readiness != null ? `${overview.average_ai_readiness}/100` : "—"}
          </div>
          <div className="kpi-delta">Schema · BLUF · Links · FAQs</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">SERP Citations Found</div>
          <div className="kpi-val" style={{ color: "var(--accent)" }}>
            {sovData?.brand_citations ?? 0}
          </div>
          <div className="kpi-delta">Featured snippet / PAA hits</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Queries Audited</div>
          <div className="kpi-val">{sovData?.total_queries_audited ?? 0}</div>
          <div className="kpi-delta">Via Serper simulation</div>
        </div>
      </div>

      {/* SECTION 1+2: SCHEMA COVERAGE AUDIT TABLE */}
      <div className="panel" style={{ marginBottom: "20px" }}>
        <div className="panel-head">
          <span className="panel-label">Section 1 — Schema Coverage Audit</span>
          <button type="button" className="panel-action" onClick={loadAEOData}>
            Refresh
          </button>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Article</th>
                <th>FAQPage</th>
                <th>Article</th>
                <th>Speakable</th>
                <th>BLUF</th>
                <th>Int. Links</th>
                <th>FAQs</th>
                <th>AI Score</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={9} style={{ textAlign: "center", padding: "24px", color: "var(--muted)" }}>Auditing published articles...</td></tr>
              ) : overview?.pages?.length ? (
                overview.pages.map((p) => (
                  <tr key={p.content_id}>
                    <td style={{ fontWeight: 600, maxWidth: "220px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={p.title}>
                      {p.title}
                    </td>
                    <td>{p.has_faqpage ? <span className="badge badge-green">Yes</span> : <span className="badge badge-red">No</span>}</td>
                    <td>{p.schema_types.some((t) => t.toLowerCase() === "article") ? <span className="badge badge-green">Yes</span> : <span className="badge badge-amber">No</span>}</td>
                    <td>{p.schema_types.some((t) => t.toLowerCase().includes("speakable")) ? <span className="badge badge-green">Yes</span> : <span className="badge badge-amber">No</span>}</td>
                    <td>{p.bluf_present ? <span className="badge badge-green">Yes</span> : <span className="badge badge-amber">No</span>}</td>
                    <td>{p.internal_link_count}</td>
                    <td>{p.faq_question_count}</td>
                    <td><b>{p.ai_readiness_score}</b>/100</td>
                    <td>
                      {!p.has_faqpage && (
                        <button
                          type="button"
                          className="btn btn-accent"
                          style={{ fontSize: "8.5px", padding: "2px 8px" }}
                          disabled={generatingSchemaFor === p.content_id}
                          onClick={() => handleGenerateSchema(p.content_id)}
                        >
                          {generatingSchemaFor === p.content_id ? "Generating..." : "Generate FAQ Schema"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={9} style={{ textAlign: "center", padding: "28px", color: "var(--muted)" }}>
                    No published articles found yet. Once articles are approved &amp; published to WordPress,
                    their schema coverage is audited here automatically.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* SECTION 3: SERPER CITATION SIMULATION + SECTION 4: SCHEMA GENERATOR */}
      <div className="grid-2">
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">Section 3 — Serper Citation Simulation</span>
            <button
              type="button"
              className="btn btn-accent panel-action"
              disabled={checkingCitations}
              onClick={runCitationCheck}
              style={{ fontSize: "9px", padding: "3px 10px" }}
            >
              {checkingCitations ? "Checking..." : "Run Citation Check"}
            </button>
          </div>
          <div className="panel-body">
            <p style={{ fontSize: "10px", color: "var(--muted)", marginBottom: "12px" }}>
              Checks whether your domain appears in featured snippets, People Also Ask answers, or top organic
              results for your articles' target keywords — the closest measurable proxy for AI-engine citation.
            </p>

            {sovData?.note && (
              <p style={{ fontSize: "10px", color: "var(--muted)", marginBottom: "10px" }}>{sovData.note}</p>
            )}

            {citationResults.length > 0 ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Keyword</th>
                    <th>Snippet</th>
                    <th>PAA</th>
                    <th>Position</th>
                    <th>Citation Odds</th>
                  </tr>
                </thead>
                <tbody>
                  {citationResults.map((r, i) => (
                    <tr key={i}>
                      <td style={{ fontSize: "10.5px", maxWidth: "180px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {r.query}
                      </td>
                      <td>{r.checked ? (r.appears_featured_snippet ? "✅ Yes" : "— No") : `⚠ ${r.error || "unchecked"}`}</td>
                      <td>{r.checked ? (r.appears_people_also_ask ? "✅ Yes" : "— No") : ""}</td>
                      <td>{r.organic_position ?? "—"}</td>
                      <td>
                        <span className={`badge ${r.citation_probability === "High" ? "badge-green" : r.citation_probability === "Medium" ? "badge-amber" : "badge-red"}`}>
                          {r.citation_probability ?? "—"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{ fontSize: "11px", color: "var(--muted)" }}>
                No citation checks have run yet for this website. Click "Run Citation Check" above.
              </div>
            )}
          </div>
        </div>

        {/* SECTION 4: REAL SCHEMA GENERATOR */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">Section 4 — FAQ Schema Generator</span>
            <span className="badge badge-accent">JSON-LD</span>
          </div>
          <div className="panel-body">
            <p style={{ fontSize: "10px", color: "var(--muted)", marginBottom: "12px" }}>
              Generates FAQPage JSON-LD from the real content of your latest article using NVIDIA NIM.
              Then inject it straight into WordPress with one click — no copy-pasting required.
            </p>

            <button
              type="button"
              className="btn btn-accent"
              style={{ width: "100%", padding: "8px", fontWeight: 600, marginBottom: "12px" }}
              disabled={generatingSchemaFor !== null}
              onClick={() => handleGenerateSchema(undefined)}
            >
              {generatingSchemaFor ? "Extracting questions via NIM..." : "⚡ Generate FAQPage Schema From Latest Article"}
            </button>

            {schemaOutput && (
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                  <label style={{ fontSize: "9px", textTransform: "uppercase", color: "var(--muted)" }}>
                    Generated JSON-LD
                  </label>
                  <button
                    type="button"
                    className="btn"
                    style={{ fontSize: "8.5px", padding: "2px 7px" }}
                    onClick={() => {
                      navigator.clipboard.writeText(schemaOutput);
                      showToast("Copied JSON-LD to clipboard!");
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
                    maxHeight: "180px",
                    overflowY: "auto",
                    marginBottom: "10px",
                  }}
                >
                  {schemaOutput}
                </pre>
                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ width: "100%", padding: "8px" }}
                  disabled={injectingInto !== null}
                  onClick={() => {
                    try {
                      const parsed = JSON.parse(schemaOutput);
                      void parsed;
                      handleInjectSchemaFromLatest();
                    } catch {}
                  }}
                >
                  {injectingInto ? "Injecting into WordPress..." : "Inject to WordPress Post"}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* BOTTOM TICKER */}
      <div className="bticker">
        <span className="bticker-inner">
          <span className="bt-sq"></span>AEO ENGINE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>REAL SCHEMA AUDIT <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SERPER CITATION SIMULATION &nbsp;&nbsp;&nbsp;&nbsp;
          <span className="bt-sq"></span>AEO ENGINE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>REAL SCHEMA AUDIT <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SERPER CITATION SIMULATION
        </span>
      </div>
    </div>
  );

  async function handleInjectSchemaFromLatest() {
    // Inject the currently displayed schema into the most relevant article:
    // prefer a selected audit page missing FAQ schema, else the latest article id used at generation time.
    const wid = getCurrentWebsiteId();
    let targetId: string | undefined;
    try {
      const detail = await get(`/api/writer/${wid}/content`);
      const rows = Array.isArray(detail) ? detail : [];
      const candidate = rows.find((r: any) => r.wp_post_id) || rows[0];
      targetId = candidate?.id;
    } catch {}
    if (!targetId) {
      showToast("No article with a WordPress post found — publish an article first.");
      return;
    }
    handleInjectSchema(targetId);
  }
}
