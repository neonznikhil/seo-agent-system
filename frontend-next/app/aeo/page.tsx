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

interface RedditOpportunity {
  title: string;
  url: string;
  snippet: string;
  keyword: string;
  subreddit: string;
  opportunity_type: string;
  suggested_action: string;
}

interface SemanticScoreResult {
  average_semantic_score: number;
  overall_grade: string;
  query_scores: Array<{
    query: string;
    similarity_score: number;
    grade: string;
  }>;
  recommendation: string;
}

export default function AEOPage() {
  const [websiteId, setWebsiteId] = useState<string>("");
  const [overview, setOverview] = useState<AeoOverview | null>(null);
  const [sovData, setSovData] = useState<SovData | null>(null);
  const [citationResults, setCitationResults] = useState<CitationCheckResult[]>([]);
  const [checkingCitations, setCheckingCitations] = useState(false);
  const [generatingSchemaFor, setGeneratingSchemaFor] = useState<string | null>(null);
  const [schemaOutput, setSchemaOutput] = useState("");

  const [redditOpportunities, setRedditOpportunities] = useState<RedditOpportunity[]>([]);
  const [loadingReddit, setLoadingReddit] = useState(false);

  const [semanticText, setSemanticText] = useState("");
  const [semanticKeyword, setSemanticKeyword] = useState("");
  const [semanticResult, setSemanticResult] = useState<SemanticScoreResult | null>(null);
  const [testingSemantic, setTestingSemantic] = useState(false);

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
      // warn removed
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAEOData();
  }, [loadAEOData]);

  const loadRedditOpportunities = async () => {
    try {
      setLoadingReddit(true);
      const wid = getCurrentWebsiteId() || "";
      const res = await get(`/api/aeo/reddit/opportunities?website_id=${wid}`);
      setRedditOpportunities(res.opportunities || []);
    } catch (e: any) {
      showToast(`Reddit load failed: ${e.message}`);
    } finally {
      setLoadingReddit(false);
    }
  };

  useEffect(() => {
    loadRedditOpportunities();
  }, [loadAEOData]);

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
        showToast(`FAQPage schema generated from "${res.article_title}".`);
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

  const [injectingInto, setInjectingInto] = useState<string | null>(null);

  const handleSemanticTest = async () => {
    if (!semanticText.trim()) {
      showToast("Paste article HTML or text first.");
      return;
    }
    try {
      setTestingSemantic(true);
      const res = await post("/api/aeo/semantic-score", {
        html_content: semanticText,
        target_keyword: semanticKeyword || "personal injury lawyer",
      });
      setSemanticResult(res);
    } catch (e: any) {
      showToast(`Semantic test failed: ${e.message}`);
    } finally {
      setTestingSemantic(false);
    }
  };

  const aiVisibilityScore = overview && overview.average_ai_readiness != null
    ? Math.round(overview.average_ai_readiness)
    : (sovData ? Math.round((sovData.brand_citations / Math.max(sovData.total_queries_audited, 1)) * 100) : 0);

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
        AI Visibility Tracking · Citation Injection · Semantic Scoring · Reddit Presence · Schema Health
      </div>

      {/* SECTION 1 — AI VISIBILITY SCORE */}
      <div className="kpi-strip" style={{ gridTemplateColumns: "repeat(4, 1fr)", marginBottom: "20px" }}>
        <div className="kpi-cell">
          <div className="kpi-label">AI Visibility Score</div>
          <div className="kpi-val" style={{ color: aiVisibilityScore > 70 ? "var(--accent)" : undefined }}>
            {aiVisibilityScore}/100
          </div>
          <div className="kpi-delta">
            {sovData ? `${sovData.brand_citations} citations found` : "Run citation check"}
          </div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">AI Overview Appearances</div>
          <div className="kpi-val">{sovData?.total_queries_audited ?? 0}</div>
          <div className="kpi-delta">Keywords audited this cycle</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Cited by AI</div>
          <div className="kpi-val" style={{ color: "var(--accent)" }}>
            {sovData?.brand_citations ?? 0}
          </div>
          <div className="kpi-delta">Featured snippet / PAA hits</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-label">Schema Coverage</div>
          <div className="kpi-val">{overview ? `${overview.coverage_percent}%` : "—"}</div>
          <div className="kpi-delta">{overview ? `${overview.pages_with_faq_schema}/${overview.total_published} posts` : ""}</div>
        </div>
      </div>

      {/* SECTION 2 — KEYWORD TRACKING TABLE */}
      <div className="panel" style={{ marginBottom: "20px" }}>
        <div className="panel-head">
          <span className="panel-label">Section 2 — Keyword AI Tracking</span>
          <button type="button" className="panel-action" onClick={runCitationCheck}>
            {checkingCitations ? "Checking..." : "Run Citation Check"}
          </button>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Keyword</th>
                <th>Organic Position</th>
                <th>AI Overview</th>
                <th>Cited by AI</th>
                <th>Last Checked</th>
                <th>Trend</th>
              </tr>
            </thead>
            <tbody>
              {citationResults.length > 0 ? (
                citationResults.map((r, i) => (
                  <tr key={i}>
                    <td style={{ fontSize: "10.5px", maxWidth: "180px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.query}
                    </td>
                    <td>{r.organic_position ?? "—"}</td>
                    <td>{r.checked ? (r.appears_featured_snippet ? "Yes" : "No") : "—"}</td>
                    <td>{r.checked ? (r.appears_featured_snippet || r.appears_people_also_ask ? "Yes" : "No") : "—"}</td>
                    <td style={{ fontSize: "10px", color: "var(--muted)" }}>
                      {r.checked ? new Date().toLocaleDateString() : "—"}
                    </td>
                    <td>
                      <span className={`badge ${r.citation_probability === "High" ? "badge-green" : r.citation_probability === "Medium" ? "badge-amber" : "badge-red"}`}>
                        {r.citation_probability ?? "—"}
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: "28px", color: "var(--muted)" }}>
                    No citation checks have run yet. Click &quot;Run Citation Check&quot; to query Serper.dev for your top keywords.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid-2">
        {/* SECTION 3 — REDDIT OPPORTUNITIES */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">Section 3 — Reddit Opportunities</span>
            <button type="button" className="panel-action" onClick={loadRedditOpportunities}>
              Refresh
            </button>
          </div>
          <div className="panel-body">
            {redditOpportunities.length > 0 ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Thread</th>
                    <th>Subreddit</th>
                    <th>Type</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {redditOpportunities.slice(0, 10).map((opp, i) => (
                    <tr key={i}>
                      <td style={{ fontSize: "10.5px", maxWidth: "200px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        <a href={opp.url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--accent)" }}>
                          {opp.title}
                        </a>
                      </td>
                      <td>r/{opp.subreddit}</td>
                      <td><span className="badge badge-amber">{opp.opportunity_type}</span></td>
                      <td>
                        <button
                          type="button"
                          className="btn btn-accent"
                          style={{ fontSize: "8.5px", padding: "2px 8px" }}
                          onClick={async () => {
                            try {
                              const res = await post("/api/aeo/reddit/generate-comment", {
                                thread_title: opp.title,
                                thread_snippet: opp.snippet,
                                relevant_article_url: "",
                              });
                              showToast(`Comment generated: ${res.comment?.slice(0, 80)}...`);
                            } catch (e: any) {
                              showToast(`Comment generation failed: ${e.message}`);
                            }
                          }}
                        >
                          Generate Comment
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{ fontSize: "11px", color: "var(--muted)" }}>
                {loadingReddit ? "Scanning Reddit for opportunities..." : "No Reddit opportunities found yet. Publish more articles to discover threads."}
              </div>
            )}
          </div>
        </div>

        {/* SECTION 4 — SEMANTIC SCORE TESTER */}
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">Section 4 — Semantic Score Tester</span>
          </div>
          <div className="panel-body">
            <p style={{ fontSize: "10px", color: "var(--muted)", marginBottom: "12px" }}>
              Paste any article HTML or text to test how well it matches common AI search queries.
            </p>
            <textarea
              value={semanticText}
              onChange={(e) => setSemanticText(e.target.value)}
              placeholder="Paste article HTML or text here..."
              style={{
                width: "100%",
                height: "120px",
                background: "var(--panel-inner)",
                border: "1px solid var(--border)",
                color: "var(--fg)",
                padding: "8px",
                fontSize: "10px",
                fontFamily: "'IBM Plex Mono', monospace",
                marginBottom: "8px",
                resize: "vertical",
              }}
            />
            <input
              type="text"
              value={semanticKeyword}
              onChange={(e) => setSemanticKeyword(e.target.value)}
              placeholder="Target keyword (e.g. personal injury lawyer)"
              style={{
                width: "100%",
                padding: "6px 8px",
                background: "var(--panel-inner)",
                border: "1px solid var(--border)",
                color: "var(--fg)",
                fontSize: "10px",
                marginBottom: "8px",
              }}
            />
            <button
              type="button"
              className="btn btn-accent"
              style={{ width: "100%", padding: "8px", fontWeight: 600 }}
              disabled={testingSemantic}
              onClick={handleSemanticTest}
            >
              {testingSemantic ? "Testing..." : "Test AI Readability"}
            </button>

            {semanticResult && (
              <div style={{ marginTop: "12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                  <span style={{ fontSize: "10px", color: "var(--muted)" }}>Average Score</span>
                  <span style={{ fontSize: "12px", fontWeight: 700 }}>
                    {semanticResult.average_semantic_score} / 1.0
                  </span>
                </div>
                <div style={{ background: "var(--panel-inner)", border: "1px solid var(--border)", padding: "10px", marginBottom: "8px" }}>
                  <span className={`badge ${semanticResult.overall_grade.startsWith("Excellent") ? "badge-green" : semanticResult.overall_grade.startsWith("Good") ? "badge-amber" : "badge-red"}`}>
                    {semanticResult.overall_grade}
                  </span>
                  <p style={{ fontSize: "9px", color: "var(--muted)", marginTop: "6px" }}>{semanticResult.recommendation}</p>
                </div>
                {semanticResult.query_scores.map((qs, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: "9px", padding: "2px 0", borderBottom: "1px solid var(--border)" }}>
                    <span style={{ color: "var(--muted)", maxWidth: "60%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{qs.query}</span>
                    <span>{qs.similarity_score} — {qs.grade}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* SECTION 5 — SCHEMA HEALTH */}
      <div className="panel" style={{ marginBottom: "20px" }}>
        <div className="panel-head">
          <span className="panel-label">Section 5 — Schema Health</span>
          <button type="button" className="panel-action" onClick={loadAEOData}>Refresh</button>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Article</th>
                <th>Article Schema</th>
                <th>FAQ Schema</th>
                <th>Entity Mentions</th>
                <th>Markdown Version</th>
                <th>AI Score</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} style={{ textAlign: "center", padding: "24px", color: "var(--muted)" }}>Auditing published articles...</td></tr>
              ) : overview?.pages?.length ? (
                overview.pages.map((p) => (
                  <tr key={p.content_id}>
                    <td style={{ fontWeight: 600, maxWidth: "220px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={p.title}>
                      {p.title}
                    </td>
                    <td>{p.schema_types.some((t) => t.toLowerCase() === "article") ? "Yes" : "No"}</td>
                    <td>{p.has_faqpage ? "Yes" : "No"}</td>
                    <td>{p.schema_types.length > 2 ? "Yes" : "No"}</td>
                    <td>{p.llms_txt_included ? "Yes" : "No"}</td>
                    <td><b>{p.ai_readiness_score}</b>/100</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: "28px", color: "var(--muted)" }}>
                    No published articles found yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* BOTTOM TICKER */}
      <div className="bticker">
        <span className="bticker-inner">
          <span className="bt-sq"></span>AEO ENGINE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>CITATION TRACKING <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SEMANTIC SCORING &nbsp;&nbsp;&nbsp;&nbsp;
          <span className="bt-sq"></span>AEO ENGINE <span className="bt-sep">/</span>
          <span className="bt-sq"></span>CITATION TRACKING <span className="bt-sep">/</span>
          <span className="bt-sq"></span>SEMANTIC SCORING
        </span>
      </div>
    </div>
  );
}
