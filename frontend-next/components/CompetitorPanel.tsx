"use client";

/**
 * Competitor tracking: share of voice on your keyword set, their new pages,
 * and where they outrank you.
 *
 * There is no automatic competitor feed yet, so positions are entered here and
 * persisted to the backend. SOV is computed server-side from the same CTR curve
 * used for action ranking, which keeps the two views consistent.
 */

import { useCallback, useEffect, useState } from "react";
import {
  OutrankGap,
  ShareOfVoice,
  computeSov,
  detectNewPages,
  fetchGaps,
  fmtPct,
  recordCompetitorRanking,
} from "@/lib/intelligence";

interface Props {
  websiteId: string;
  ownDomain?: string;
}

interface KeywordRow {
  keyword: string;
  ourPosition: string;
  competitorPositions: Record<string, string>;
}

export function CompetitorPanel({ websiteId, ownDomain = "" }: Props) {
  const [domain, setDomain] = useState(ownDomain);
  const [competitors, setCompetitors] = useState<string[]>([]);
  const [competitorInput, setCompetitorInput] = useState("");
  const [rows, setRows] = useState<KeywordRow[]>([]);
  const [sov, setSov] = useState<ShareOfVoice | null>(null);
  const [gaps, setGaps] = useState<OutrankGap[]>([]);
  const [gapsNote, setGapsNote] = useState<string>("");
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // new page detector
  const [scanDomain, setScanDomain] = useState("");
  const [scanUrls, setScanUrls] = useState("");
  const [newPages, setNewPages] = useState<
    Array<{ url: string; title?: string; first_seen?: string }>
  >([]);

  useEffect(() => {
    setDomain(ownDomain);
  }, [ownDomain]);

  const loadGaps = useCallback(async () => {
    if (!websiteId || !domain) return;
    try {
      const res = await fetchGaps(websiteId, domain);
      setGaps(res.gaps || []);
      setGapsNote(res.has_data ? "" : res.note || "No stored ranking data yet.");
    } catch {
      setGaps([]);
    }
  }, [websiteId, domain]);

  useEffect(() => {
    loadGaps();
  }, [loadGaps]);

  const flash = (m: string) => {
    setNotice(m);
    setTimeout(() => setNotice(null), 4500);
  };

  const addCompetitor = () => {
    const d = competitorInput.trim().replace(/^https?:\/\//, "").replace(/\/.*$/, "");
    if (!d || competitors.includes(d) || d === domain) return;
    setCompetitors([...competitors, d]);
    setRows(rows.map((r) => ({ ...r, competitorPositions: { ...r.competitorPositions, [d]: "" } })));
    setCompetitorInput("");
  };

  const removeCompetitor = (d: string) => {
    setCompetitors(competitors.filter((c) => c !== d));
    setRows(
      rows.map((r) => {
        const next = { ...r.competitorPositions };
        delete next[d];
        return { ...r, competitorPositions: next };
      })
    );
  };

  const addRow = () => {
    setRows([
      ...rows,
      {
        keyword: "",
        ourPosition: "",
        competitorPositions: Object.fromEntries(competitors.map((c) => [c, ""])),
      },
    ]);
  };

  const saveAndCompute = async () => {
    if (!websiteId) return;
    if (!domain) {
      flash("Enter your own domain first.");
      return;
    }
    const valid = rows.filter((r) => r.keyword.trim());
    if (valid.length === 0) {
      flash("Add at least one keyword row.");
      return;
    }

    try {
      setBusy("save");
      const today = new Date().toISOString().slice(0, 10);

      // Persist every position so share of voice and gaps are reproducible.
      for (const r of valid) {
        if (r.ourPosition !== "") {
          await recordCompetitorRanking(websiteId, {
            competitor_domain: domain,
            keyword: r.keyword.trim(),
            position: Number(r.ourPosition),
            captured_date: today,
          });
        }
        for (const c of competitors) {
          const v = r.competitorPositions[c];
          if (v !== undefined && v !== "") {
            await recordCompetitorRanking(websiteId, {
              competitor_domain: c,
              keyword: r.keyword.trim(),
              position: Number(v),
              captured_date: today,
            });
          }
        }
      }

      const ourPositions: Record<string, number | null> = {};
      const competitorPositions: Record<string, Record<string, number | null>> = {};
      for (const r of valid) {
        ourPositions[r.keyword.trim()] =
          r.ourPosition === "" ? null : Number(r.ourPosition);
        for (const c of competitors) {
          const v = r.competitorPositions[c];
          if (v !== undefined && v !== "") {
            competitorPositions[c] = competitorPositions[c] || {};
            competitorPositions[c][r.keyword.trim()] = Number(v);
          }
        }
      }

      const result = await computeSov(websiteId, {
        our_positions: ourPositions,
        competitor_positions: competitorPositions,
      });
      setSov(result);
      await loadGaps();
      flash("Share of voice computed and positions saved.");
    } catch (e) {
      flash(e instanceof Error ? e.message : "Failed to compute share of voice");
    } finally {
      setBusy(null);
    }
  };

  const runScan = async () => {
    if (!websiteId || !scanDomain) {
      flash("Enter a competitor domain to scan.");
      return;
    }
    const urls = scanUrls
      .split("\n")
      .map((u) => u.trim())
      .filter(Boolean)
      .map((u) => ({ url: u }));
    if (urls.length === 0) {
      flash("Paste at least one URL.");
      return;
    }
    try {
      setBusy("scan");
      const res = await detectNewPages(websiteId, scanDomain, urls);
      setNewPages(res.new_pages || []);
      flash(`${res.new_page_count} new page(s) found.`);
    } catch (e) {
      flash(e instanceof Error ? e.message : "Scan failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      {notice && (
        <div
          className="panel"
          style={{ padding: "10px 14px", borderColor: "var(--accent)", fontSize: "11.5px" }}
        >
          {notice}
        </div>
      )}

      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Competitor Set</span>
          <span style={{ fontSize: "10px", color: "var(--muted)" }}>
            Positions are saved so share of voice is reproducible
          </span>
        </div>
        <div className="panel-body">
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginBottom: "12px" }}>
            <div style={{ flex: "1 1 220px" }}>
              <label style={labelStyle}>Your domain</label>
              <input
                className="chat-input"
                style={{ width: "100%" }}
                placeholder="client.com"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
              />
            </div>
            <div style={{ flex: "1 1 220px" }}>
              <label style={labelStyle}>Add competitor domain</label>
              <div style={{ display: "flex", gap: "6px" }}>
                <input
                  className="chat-input"
                  style={{ flex: 1 }}
                  placeholder="rival.com"
                  value={competitorInput}
                  onChange={(e) => setCompetitorInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addCompetitor()}
                />
                <button className="btn" onClick={addCompetitor}>
                  Add
                </button>
              </div>
            </div>
          </div>

          {competitors.length > 0 && (
            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "14px" }}>
              {competitors.map((c) => (
                <span
                  key={c}
                  className="badge badge-accent"
                  style={{ display: "flex", alignItems: "center", gap: "6px" }}
                >
                  {c}
                  <button
                    onClick={() => removeCompetitor(c)}
                    style={{
                      background: "transparent",
                      border: "none",
                      color: "inherit",
                      cursor: "pointer",
                      padding: 0,
                      fontWeight: 700,
                    }}
                    title="Remove"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}

          {competitors.length === 0 ? (
            <div style={{ fontSize: "11px", color: "var(--muted)" }}>
              Add at least one competitor domain to compare visibility.
            </div>
          ) : (
            <>
              <table className="data-table" style={{ marginBottom: "10px" }}>
                <thead>
                  <tr>
                    <th>Keyword</th>
                    <th style={{ width: "100px" }}>{domain || "You"}</th>
                    {competitors.map((c) => (
                      <th key={c} style={{ width: "100px" }}>
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i}>
                      <td>
                        <input
                          className="chat-input"
                          style={{ width: "100%" }}
                          placeholder="keyword"
                          value={r.keyword}
                          onChange={(e) => {
                            const next = [...rows];
                            next[i].keyword = e.target.value;
                            setRows(next);
                          }}
                        />
                      </td>
                      <td>
                        <input
                          className="chat-input"
                          style={{ width: "100%" }}
                          placeholder="pos"
                          value={r.ourPosition}
                          onChange={(e) => {
                            const next = [...rows];
                            next[i].ourPosition = e.target.value.replace(/[^\d]/g, "");
                            setRows(next);
                          }}
                        />
                      </td>
                      {competitors.map((c) => (
                        <td key={c}>
                          <input
                            className="chat-input"
                            style={{ width: "100%" }}
                            placeholder="pos"
                            value={r.competitorPositions[c] ?? ""}
                            onChange={(e) => {
                              const next = [...rows];
                              next[i].competitorPositions[c] = e.target.value.replace(/[^\d]/g, "");
                              setRows(next);
                            }}
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ display: "flex", gap: "8px" }}>
                <button className="btn" onClick={addRow}>
                  + Add keyword
                </button>
                <button
                  className="btn btn-primary"
                  onClick={saveAndCompute}
                  disabled={busy === "save"}
                >
                  {busy === "save" ? "Computing..." : "Save & compute share of voice"}
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {sov && (
        <div className="panel">
          <div className="panel-head">
            <span className="panel-label">
              Share of Voice · {sov.keyword_count} keywords
            </span>
            <span style={{ fontSize: "10px", color: "var(--muted)" }}>
              {sov.method}
            </span>
          </div>
          <div className="panel-body">
            {[
              {
                domain: domain || "You",
                sov: sov.our_share_of_voice,
                ours: true,
              },
              ...sov.competitors.map((c) => ({
                domain: c.domain,
                sov: c.share_of_voice,
                ours: false,
              })),
            ]
              .sort((a, b) => b.sov - a.sov)
              .map((entry) => (
                <div key={entry.domain} style={{ marginBottom: "10px" }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: "11px",
                      marginBottom: "3px",
                    }}
                  >
                    <span
                      style={{
                        fontWeight: entry.ours ? 700 : 500,
                        color: entry.ours ? "var(--accent)" : "var(--ink)",
                      }}
                    >
                      {entry.domain}
                      {entry.ours ? " (you)" : ""}
                    </span>
                    <span style={{ fontFamily: "monospace" }}>
                      {fmtPct(entry.sov)}
                    </span>
                  </div>
                  <div
                    style={{
                      height: "6px",
                      background: "var(--line)",
                      borderRadius: "3px",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.min(100, entry.sov * 100)}%`,
                        height: "100%",
                        background: entry.ours ? "var(--accent)" : "var(--muted)",
                      }}
                    />
                  </div>
                </div>
              ))}
            <div style={{ fontSize: "10px", color: "var(--muted)", marginTop: "6px" }}>
              Shares sum to {(sov.sov_sums_to * 100).toFixed(1)}% of total
              visibility across the tracked keyword set.
            </div>
          </div>
        </div>
      )}

      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">
            Where They Outrank You
            {gaps.length > 0 && (
              <span className="badge badge-red" style={{ marginLeft: "8px" }}>
                {gaps.length}
              </span>
            )}
          </span>
          <button className="panel-action" onClick={loadGaps}>
            Refresh
          </button>
        </div>
        <div className="panel-body" style={{ padding: 0 }}>
          {gaps.length === 0 ? (
            <div
              style={{
                padding: "24px 16px",
                textAlign: "center",
                fontSize: "11.5px",
                color: "var(--muted)",
              }}
            >
              {gapsNote || "No competitor outranks you on the stored keyword set."}
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Keyword</th>
                  <th style={{ width: "130px" }}>Competitor</th>
                  <th style={{ width: "90px" }}>Their pos</th>
                  <th style={{ width: "90px" }}>Your pos</th>
                  <th style={{ width: "80px" }}>Gap</th>
                </tr>
              </thead>
              <tbody>
                {gaps.map((g, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 600 }}>{g.keyword}</td>
                    <td>{g.competitor}</td>
                    <td style={{ color: "var(--red)", fontWeight: 600 }}>
                      {g.their_position}
                    </td>
                    <td>
                      {g.our_position === null ? (
                        <span style={{ color: "var(--muted)" }}>not ranking</span>
                      ) : (
                        g.our_position
                      )}
                    </td>
                    <td>
                      {g.gap === null ? (
                        <span className="badge badge-red">—</span>
                      ) : (
                        <span className="badge badge-amber">{g.gap}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <span className="panel-label">Their New Pages</span>
          <span style={{ fontSize: "10px", color: "var(--muted)" }}>
            Paste their current URLs to diff against what we last saw
          </span>
        </div>
        <div className="panel-body">
          <div style={{ display: "flex", gap: "10px", marginBottom: "10px", flexWrap: "wrap" }}>
            <input
              className="chat-input"
              style={{ flex: "1 1 200px" }}
              placeholder="rival.com"
              value={scanDomain}
              onChange={(e) => setScanDomain(e.target.value)}
            />
            <button
              className="btn btn-primary"
              onClick={runScan}
              disabled={busy === "scan"}
            >
              {busy === "scan" ? "Scanning..." : "Detect new pages"}
            </button>
          </div>
          <textarea
            className="chat-input"
            style={{ width: "100%", minHeight: "80px", resize: "vertical" }}
            placeholder={"https://rival.com/blog/post-1\nhttps://rival.com/blog/post-2"}
            value={scanUrls}
            onChange={(e) => setScanUrls(e.target.value)}
          />
          {newPages.length > 0 && (
            <div style={{ marginTop: "10px" }}>
              {newPages.map((p) => (
                <div
                  key={p.url}
                  style={{
                    padding: "8px 10px",
                    borderLeft: "3px solid var(--accent)",
                    background: "var(--surface)",
                    marginBottom: "6px",
                    fontSize: "11px",
                    fontFamily: "monospace",
                  }}
                >
                  {p.url}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: "9.5px",
  textTransform: "uppercase",
  color: "var(--muted)",
  marginBottom: "4px",
};