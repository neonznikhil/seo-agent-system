/**
 * Typed client for the RankForge portfolio intelligence API.
 *
 * Every view here reads real backend state. When a data source is not
 * connected the backend returns `data_available: false` / `has_data: false`
 * and these helpers pass that through so the UI can say "not connected"
 * rather than drawing an empty chart that looks like a zero.
 */

import { get, post } from "./api";

export interface IntegrationStatus {
  name: string;
  status: "ok" | "unconfigured";
  detail: string;
}

export interface PortfolioSite {
  website_id: string;
  domain: string;
  status: string;
  health_score: number | null;
  health_formula: string;
  indexed_pages: number | null;
  excluded_pages: number | null;
  errors: number | null;
  clicks: number | null;
  impressions: number | null;
  avg_position: number | null;
  open_issues: number;
  critical_issues: number;
  metrics_as_of: string | null;
}

export interface Portfolio {
  sites: PortfolioSite[];
  totals: {
    sites: number;
    clicks: number | null;
    open_issues: number;
    critical_issues: number;
  };
  storage: string;
  integrations: Record<string, IntegrationStatus>;
  data_available: boolean;
  note: string;
}

export interface ActionEvidence {
  formula?: string;
  search_volume?: number;
  ctr_current?: number;
  ctr_target?: number;
  ctr_gain?: number;
  current_position?: number;
  target_position?: number;
  confidence?: number;
  reason?: string;
  scorable?: boolean;
}

export interface ActionItem {
  id?: string;
  rank?: number;
  title: string;
  category: string;
  target_url?: string | null;
  keyword?: string | null;
  search_volume?: number | null;
  current_position?: number | null;
  target_position?: number | null;
  projected_clicks_gain?: number | null;
  priority_score?: number | null;
  impact_per_hour?: number | null;
  effort_minutes?: number;
  confidence?: number;
  severity?: string;
  status?: string;
  evidence?: ActionEvidence;
}

export interface ActionList {
  website_id: string;
  sort_by: string;
  count: number;
  total_open: number;
  actions: ActionItem[];
  unscored: ActionItem[];
  unscored_note: string;
  ctr_curve_positions: number;
}

export interface CplResult {
  keyword: string;
  landing_page: string;
  clicks: number;
  leads: number;
  conversion_rate: number | null;
  effort_cost: number;
  cost_per_lead: number | null;
  attribution_method: string;
  attribution_confidence: number;
}

export interface CplReport {
  website_id: string;
  period: { start: string; end: string };
  methodology: {
    cost_basis: string;
    cost_note: string;
    attribution_note: string;
  };
  results: CplResult[];
  total_cost: number;
  total_leads: number;
  has_data: boolean;
  data_note: string;
}

export interface ChangeEvent {
  id: string;
  target_url: string;
  change_type: string;
  actor: string;
  before_content?: string | null;
  after_content?: string | null;
  unified_diff?: string | null;
  status: "previewed" | "applied" | "undone";
  is_ymyl: boolean;
  ymyl_reason?: string | null;
  review_required: boolean;
  applied_at?: string | null;
  undone_at?: string | null;
  created_at?: string;
  status_history?: Array<{ status: string; at: string; actor?: string }>;
}

export interface ChangeLog {
  website_id: string;
  count: number;
  changes: ChangeEvent[];
  counts: {
    previewed: number;
    applied: number;
    undone: number;
    ymyl: number;
    awaiting_review: number;
  };
}

export interface CompetitorShare {
  domain: string;
  visibility: number;
  share_of_voice: number;
}

export interface ShareOfVoice {
  website_id: string;
  keyword_count: number;
  our_visibility: number;
  our_share_of_voice: number;
  competitors: CompetitorShare[];
  total_visibility: number;
  method: string;
  sov_sums_to: number;
  snapshot_id?: string;
}

export interface OutrankGap {
  keyword: string;
  competitor: string;
  our_position: number | null;
  their_position: number;
  gap: number | null;
  note: string;
}

export interface MeasurementSeriesPoint {
  day: number;
  clicks: number | null;
  impressions: number | null;
  position: number | null;
  control_clicks: number | null;
}

export interface MeasurementReport {
  ok: boolean;
  window: {
    id: string;
    target_url: string;
    keyword?: string | null;
    window_start: string;
    baseline_clicks: number;
    baseline_position: number | null;
    status: string;
  };
  status: "awaiting_data" | "in_progress" | "complete";
  days_elapsed?: number;
  days_remaining?: number;
  snapshots_recorded: number;
  series?: MeasurementSeriesPoint[];
  lift?: {
    baseline_clicks: number;
    current_clicks: number;
    raw_clicks_lift: number;
    control_adjustment: number;
    adjusted_clicks_lift: number;
    percent_lift: number | null;
    position_baseline: number | null;
    position_current: number | null;
    position_improvement: number | null;
  };
  control_note?: string;
  method?: string;
  note?: string;
}

/* ------------------------------------------------------------------ */
/* Bullet 1: multi-site portfolio                                      */
/* ------------------------------------------------------------------ */
export async function fetchPortfolio(): Promise<Portfolio> {
  return get("/api/intelligence/portfolio");
}

export async function fetchIntegrations(): Promise<
  Record<string, IntegrationStatus>
> {
  return get("/api/intelligence/integrations");
}

/* ------------------------------------------------------------------ */
/* Bullet 2: prioritized actions                                       */
/* ------------------------------------------------------------------ */
export async function fetchActions(
  websiteId: string,
  limit = 10,
  sortBy: "traffic_impact" | "effort" = "traffic_impact"
): Promise<ActionList> {
  return get(
    `/api/intelligence/actions/${websiteId}?limit=${limit}&sort_by=${sortBy}`
  );
}

export async function createAction(
  websiteId: string,
  body: Record<string, unknown>
): Promise<ActionItem> {
  return post(`/api/intelligence/actions/${websiteId}`, body);
}

/* ------------------------------------------------------------------ */
/* Bullet 3: leads and cost per lead                                   */
/* ------------------------------------------------------------------ */
export async function computeCpl(
  websiteId: string,
  body: {
    period_start: string;
    period_end: string;
    hourly_rate: number;
    keyword_page_pairs: Array<{
      keyword: string;
      landing_page: string;
      clicks: number;
      page_sessions?: number;
      attributed_sessions?: number;
    }>;
  }
): Promise<CplReport> {
  return post(`/api/intelligence/leads/cpl/${websiteId}`, body);
}

export async function addConversion(
  websiteId: string,
  body: Record<string, unknown>
): Promise<unknown> {
  return post(`/api/intelligence/leads/conversions/${websiteId}`, body);
}

export async function addEffortCost(
  websiteId: string,
  body: Record<string, unknown>
): Promise<unknown> {
  return post(`/api/intelligence/leads/effort-cost/${websiteId}`, body);
}

/* ------------------------------------------------------------------ */
/* Bullet 4: guardrails                                                */
/* ------------------------------------------------------------------ */
export async function previewChange(
  websiteId: string,
  body: {
    target_url: string;
    change_type?: string;
    before_content?: string;
    after_content: string;
    actor?: string;
  }
): Promise<ChangeEvent> {
  return post(`/api/intelligence/guardrails/preview/${websiteId}`, body);
}

export async function applyChange(
  changeId: string,
  body: { approver: string; second_reviewer?: string }
): Promise<{ ok: boolean; change: ChangeEvent; undo_available: boolean }> {
  return post(`/api/intelligence/guardrails/changes/${changeId}/apply`, body);
}

export async function undoChange(
  changeId: string,
  actor: string
): Promise<{ ok: boolean; restored_content: string }> {
  return post(`/api/intelligence/guardrails/changes/${changeId}/undo`, {
    actor,
  });
}

export async function fetchChangeLog(
  websiteId: string,
  limit = 50
): Promise<ChangeLog> {
  return get(`/api/intelligence/guardrails/changes/${websiteId}?limit=${limit}`);
}

/* ------------------------------------------------------------------ */
/* Bullet 5: competitors                                               */
/* ------------------------------------------------------------------ */
export async function computeSov(
  websiteId: string,
  body: {
    our_positions: Record<string, number | null>;
    competitor_positions: Record<string, Record<string, number | null>>;
  }
): Promise<ShareOfVoice> {
  return post(`/api/intelligence/competitors/share-of-voice/${websiteId}`, body);
}

export async function fetchGaps(
  websiteId: string,
  ourDomain: string
): Promise<{
  gaps: OutrankGap[];
  has_data: boolean;
  count: number;
  note?: string;
}> {
  return get(
    `/api/intelligence/competitors/gaps/${websiteId}?our_domain=${encodeURIComponent(
      ourDomain
    )}`
  );
}

export async function detectNewPages(
  websiteId: string,
  competitorDomain: string,
  urls: Array<{ url: string; title?: string }>
): Promise<{
  checked: number;
  known_before: number;
  new_pages: Array<{ url: string; title?: string; first_seen?: string }>;
  new_page_count: number;
}> {
  return post(`/api/intelligence/competitors/new-pages/${websiteId}`, {
    competitor_domain: competitorDomain,
    current_urls: urls,
  });
}

export async function recordCompetitorRanking(
  websiteId: string,
  body: Record<string, unknown>
): Promise<unknown> {
  return post(`/api/intelligence/competitors/rankings/${websiteId}`, body);
}

/* ------------------------------------------------------------------ */
/* Bullet 6: prove the work                                            */
/* ------------------------------------------------------------------ */
export async function openMeasurementWindow(
  websiteId: string,
  body: Record<string, unknown>
): Promise<{ id: string }> {
  return post(`/api/intelligence/measurement/windows/${websiteId}`, body);
}

export async function recordSnapshot(
  windowId: string,
  body: Record<string, unknown>
): Promise<unknown> {
  return post(
    `/api/intelligence/measurement/windows/${windowId}/snapshot`,
    body
  );
}

export async function fetchMeasurementReport(
  windowId: string
): Promise<MeasurementReport> {
  return get(`/api/intelligence/measurement/windows/${windowId}/report`);
}

export async function fetchSiteWindows(
  websiteId: string
): Promise<{
  count: number;
  windows: Array<{
    id: string;
    target_url: string;
    keyword?: string | null;
    window_start: string;
    status: string;
  }>;
  expected_offsets: number[];
}> {
  return get(`/api/intelligence/measurement/windows/site/${websiteId}`);
}

/* ------------------------------------------------------------------ */
/* Formatting helpers                                                  */
/* ------------------------------------------------------------------ */
export function fmtNum(v: number | null | undefined, fallback = "—"): string {
  if (v === null || v === undefined) return fallback;
  return v.toLocaleString();
}

export function fmtPct(
  v: number | null | undefined,
  digits = 1,
  fallback = "—"
): string {
  if (v === null || v === undefined) return fallback;
  return `${(v * 100).toFixed(digits)}%`;
}

export function fmtMoney(
  v: number | null | undefined,
  fallback = "—"
): string {
  if (v === null || v === undefined) return fallback;
  return `$${v.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}