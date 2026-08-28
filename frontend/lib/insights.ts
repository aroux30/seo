import { api } from "@/lib/api-client";

// ---------------------------------------------------------------- vocabularies

export type OpportunityType =
  | "low_ctr_high_impressions"
  | "striking_distance"
  | "rising_query"
  | "content_gap"
  | "decaying_content"
  | "cannibalization";

export type OpportunityStatus = "open" | "in_progress" | "actioned" | "dismissed" | "expired";

export type AlertType =
  | "traffic_drop"
  | "ranking_drop"
  | "ctr_drop"
  | "content_decay"
  | "gsc_sync_failure"
  | "audit_score_drop"
  | "indexing_issue";

export type AlertSeverity = "info" | "warning" | "critical";

export type AlertStatus = "active" | "acknowledged" | "resolved" | "muted";

export const OPPORTUNITY_TYPE_LABELS_FA: Record<string, string> = {
  low_ctr_high_impressions: "نرخ کلیک پایین با نمایش بالا",
  striking_distance: "نزدیک به صفحه اول",
  rising_query: "عبارت جستجوی رو به رشد",
  content_gap: "خالی محتوایی",
  decaying_content: "افت تدریجی محتوا",
  cannibalization: "تداخل محتوایی (Cannibalization)",
};

export const OPPORTUNITY_STATUS_LABELS_FA: Record<string, string> = {
  open: "باز",
  in_progress: "در حال بررسی",
  actioned: "اقدام‌شده",
  dismissed: "رد شده",
  expired: "منقضی‌شده",
};

export const ALERT_TYPE_LABELS_FA: Record<string, string> = {
  traffic_drop: "افت ترافیک",
  ranking_drop: "افت رتبه",
  ctr_drop: "افت نرخ کلیک",
  content_decay: "افت تدریجی محتوا",
  gsc_sync_failure: "خطای همگام‌سازی سرچ کنسول",
  audit_score_drop: "افت امتیاز حسابرسی",
  indexing_issue: "مشکل ایندکس شدن",
};

export const ALERT_SEVERITY_LABELS_FA: Record<string, string> = {
  info: "اطلاعات",
  warning: "هشدار",
  critical: "بحرانی",
};

export const ALERT_STATUS_LABELS_FA: Record<string, string> = {
  active: "فعال",
  acknowledged: "تایید شده",
  resolved: "برطرف شده",
  muted: "بی‌صدا شده",
};

// -------------------------------------------------------------------- entities

export interface DashboardWebsiteRow {
  website_id: string;
  name: string;
  domain: string;
  clicks: number;
  impressions: number;
  ctr: number;
  avg_position: number;
  health_score: number;
  open_alerts: number;
  open_opportunities: number;
}

export interface DashboardSummary {
  organization_id: string;
  website_count: number;
  project_count: number;
  health_score: number;
  total_clicks: number;
  total_impressions: number;
  avg_ctr: number;
  avg_position: number;
  clicks_change_percent: number | null;
  impressions_change_percent: number | null;
  active_alerts: number;
  critical_alerts: number;
  open_opportunities: number;
  estimated_traffic_gain: number;
  published_articles: number;
  draft_articles: number;
  last_audit_score: number | null;
  last_gsc_sync_at: string | null;
  websites: DashboardWebsiteRow[];
}

export interface Opportunity {
  id: string;
  organization_id: string;
  website_id: string;
  opportunity_type: OpportunityType | string;
  status: OpportunityStatus | string;
  title: string;
  description: string | null;
  query: string | null;
  page_url: string | null;
  keyword_id: string | null;
  priority_score: number;
  estimated_traffic_gain: number;
  current_position: number | null;
  current_clicks: number;
  current_impressions: number;
  current_ctr: number | null;
  details: Record<string, any>;
  recommended_action: string | null;
  detected_at: string;
  last_seen_at: string | null;
  actioned_at: string | null;
  dismissed_at: string | null;
  dismiss_reason: string | null;
  linked_brief_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface OpportunitySummary {
  total_open: number;
  by_type: Record<string, number>;
  total_estimated_traffic_gain: number;
  top: Opportunity[];
}

export interface OpportunityDetectResult {
  website_id: string;
  scanned_queries: number;
  scanned_pages: number;
  created: number;
  updated: number;
  expired: number;
  by_type: Record<string, number>;
}

export interface Alert {
  id: string;
  organization_id: string;
  website_id: string;
  alert_type: AlertType | string;
  severity: AlertSeverity | string;
  status: AlertStatus | string;
  title: string;
  message: string;
  metric_name: string | null;
  current_value: number | null;
  previous_value: number | null;
  change_percent: number | null;
  entity_type: string | null;
  entity_id: string | null;
  details: Record<string, any>;
  occurrence_count: number;
  triggered_at: string;
  last_seen_at: string | null;
  acknowledged_at: string | null;
  resolved_at: string | null;
  resolution_note: string | null;
  muted_until: string | null;
  notified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertSummary {
  active: number;
  critical: number;
  warning: number;
  info: number;
  by_severity: Record<string, number>;
}

export interface Notification {
  id: string;
  organization_id: string;
  user_id: string | null;
  website_id: string | null;
  channel: string;
  status: string;
  event_type: string;
  title: string;
  body: string | null;
  action_url: string | null;
  alert_id: string | null;
  opportunity_id: string | null;
  payload: Record<string, any>;
  read_at: string | null;
  sent_at: string | null;
  failed_at: string | null;
  error_message: string | null;
  attempt_count: number;
  created_at: string;
}

// ------------------------------------------------------------------- requests

export interface OpportunityDetectRequest {
  lookback_days?: number;
  min_impressions?: number;
}

export interface OpportunityStatusUpdateRequest {
  status: "open" | "in_progress" | "actioned" | "dismissed";
  dismiss_reason?: string;
}

export interface AlertStatusUpdateRequest {
  status: AlertStatus;
  resolution_note?: string;
  mute_hours?: number;
}

// ----------------------------------------------------------------- formatting

/** Integer/decimal display. Returns the em-dash placeholder for null. */
export function formatNumberFa(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString("fa-IR");
}

/** Backend CTR is a 0-1 float. Shown as a percentage with one decimal. */
export function formatCtrFa(ctr: number | null | undefined): string {
  if (ctr === null || ctr === undefined || Number.isNaN(ctr)) return "—";
  return `${(ctr * 100).toLocaleString("fa-IR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}٪`;
}

/** Average position, one decimal. */
export function formatPositionFa(position: number | null | undefined): string {
  if (position === null || position === undefined || Number.isNaN(position)) return "—";
  return position.toLocaleString("fa-IR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

/** Signed change percentage, e.g. "+۱۲.۳٪". Already a percentage, not a ratio. */
export function formatChangePercentFa(change: number | null | undefined): string {
  if (change === null || change === undefined || Number.isNaN(change)) return "—";
  const sign = change > 0 ? "+" : change < 0 ? "−" : "";
  return `${sign}${Math.abs(change).toLocaleString("fa-IR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}٪`;
}

export function formatDateTimeFa(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("fa-IR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDateFa(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("fa-IR");
}

/** Persian label lookup that degrades to the raw key instead of showing undefined. */
export function labelFa(map: Record<string, string>, key: string | null | undefined): string {
  if (!key) return "—";
  return map[key] ?? key;
}

// ---------------------------------------------------------------------- calls

export function getDashboardSummary() {
  return api.get<DashboardSummary>("/dashboard/summary");
}

export function listOpportunities(params: {
  website_id: string;
  status?: string;
  opportunity_type?: string;
  limit?: number;
  offset?: number;
}) {
  const qs = new URLSearchParams();
  qs.set("website_id", params.website_id);
  if (params.status) qs.set("status", params.status);
  if (params.opportunity_type) qs.set("opportunity_type", params.opportunity_type);
  if (params.limit !== undefined) qs.set("limit", String(params.limit));
  if (params.offset !== undefined) qs.set("offset", String(params.offset));
  return api.get<Opportunity[]>(`/opportunities?${qs.toString()}`);
}

export function getOpportunitySummary(websiteId: string) {
  return api.get<OpportunitySummary>(`/opportunities/summary?website_id=${websiteId}`);
}

export function detectOpportunities(websiteId: string, body?: OpportunityDetectRequest) {
  return api.post<OpportunityDetectResult>(
    `/opportunities/detect?website_id=${websiteId}`,
    body || {}
  );
}

export function updateOpportunityStatus(
  opportunityId: string,
  body: OpportunityStatusUpdateRequest
) {
  return api.patch<Opportunity>(`/opportunities/${opportunityId}/status`, body);
}

export function listAlerts(params?: {
  website_id?: string;
  status?: string;
  severity?: string;
  limit?: number;
  offset?: number;
}) {
  const qs = new URLSearchParams();
  if (params?.website_id) qs.set("website_id", params.website_id);
  if (params?.status) qs.set("status", params.status);
  if (params?.severity) qs.set("severity", params.severity);
  if (params?.limit !== undefined) qs.set("limit", String(params.limit));
  if (params?.offset !== undefined) qs.set("offset", String(params.offset));
  const qsStr = qs.toString();
  return api.get<Alert[]>(`/alerts${qsStr ? `?${qsStr}` : ""}`);
}

export function getAlertSummary() {
  return api.get<AlertSummary>("/alerts/summary");
}

export function updateAlertStatus(alertId: string, body: AlertStatusUpdateRequest) {
  return api.patch<Alert>(`/alerts/${alertId}/status`, body);
}

export function listNotifications(params?: { unread_only?: boolean; limit?: number; offset?: number }) {
  const qs = new URLSearchParams();
  if (params?.unread_only !== undefined) qs.set("unread_only", String(params.unread_only));
  if (params?.limit !== undefined) qs.set("limit", String(params.limit));
  if (params?.offset !== undefined) qs.set("offset", String(params.offset));
  const qsStr = qs.toString();
  return api.get<Notification[]>(`/notifications${qsStr ? `?${qsStr}` : ""}`);
}

export function getUnreadNotificationCount() {
  return api.get<{ unread: number }>("/notifications/unread-count");
}

export function markNotificationsRead(notificationIds?: string[]) {
  return api.post<{ marked: number }>("/notifications/mark-read", {
    notification_ids: notificationIds,
  });
}
