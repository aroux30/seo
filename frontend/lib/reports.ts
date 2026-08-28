import { api, ApiError } from "@/lib/api-client";

// ---------------------------------------------------------------- vocabularies

/** Mirrors REPORT_TYPES in backend/app/models/reports.py. */
export const REPORT_TYPES = ["weekly", "monthly", "executive", "custom"] as const;
export type ReportType = (typeof REPORT_TYPES)[number];

export const REPORT_TYPE_LABELS_FA: Record<string, string> = {
  weekly: "هفتگی",
  monthly: "ماهانه",
  executive: "اجرایی (خلاصه مدیریتی)",
  custom: "دلخواه",
};

/** Mirrors REPORT_STATUSES in backend/app/models/reports.py. Terminal: ready/failed. */
export const REPORT_STATUS_LABELS_FA: Record<string, string> = {
  pending: "در انتظار",
  generating: "در حال تولید",
  ready: "آماده",
  failed: "ناموفق",
};

export const REPORT_STATUS_STYLE: Record<string, string> = {
  pending: "bg-slate-500/15 text-slate-300",
  generating: "bg-amber-500/15 text-amber-300",
  ready: "bg-emerald-500/15 text-emerald-300",
  failed: "bg-red-500/15 text-red-300",
};

export function isReportTerminal(status: string): boolean {
  return status === "ready" || status === "failed";
}

// -------------------------------------------------------------------- entities

export interface ReportListItem {
  id: string;
  website_id: string | null;
  report_type: ReportType | string;
  status: string;
  title: string;
  period_start: string;
  period_end: string;
  generated_at: string | null;
  metrics_snapshot: Record<string, any>;
  share_enabled: boolean;
  view_count: number;
  created_at: string;
}

export interface ReportRead extends ReportListItem {
  organization_id: string;
  generated_by: string | null;
  content: Record<string, any>;
  share_expires_at: string | null;
  error_message: string | null;
  updated_at: string;
}

export interface ReportSummaryTypeCount {
  report_type: string;
  count: number;
  latest_report_id: string | null;
  latest_generated_at: string | null;
}

export interface ReportSummary {
  total: number;
  by_type: ReportSummaryTypeCount[];
  ready: number;
  generating: number;
  failed: number;
}

export interface ReportTemplateSection {
  key: string;
  title_fa: string;
}

export interface ReportTemplate {
  report_type: string;
  title_fa: string;
  description_fa: string;
  default_period_days: number;
  sections: ReportTemplateSection[];
}

export interface ReportShareResult {
  share_token: string;
  share_enabled: boolean;
  share_expires_at: string | null;
}

// ----------------------------------------------------------------- write bodies

export interface ReportGenerateBody {
  report_type: ReportType;
  title?: string | null;
  period_start: string; // ISO date, "YYYY-MM-DD"
  period_end: string;
  website_id?: string | null;
}

// ----------------------------------------------------------------------- calls

export function listReports(params: {
  website_id?: string;
  report_type?: string;
  status?: string;
  limit?: number;
  offset?: number;
}) {
  const qs = new URLSearchParams();
  if (params.website_id) qs.set("website_id", params.website_id);
  if (params.report_type) qs.set("report_type", params.report_type);
  if (params.status) qs.set("status", params.status);
  if (params.limit !== undefined) qs.set("limit", String(params.limit));
  if (params.offset !== undefined) qs.set("offset", String(params.offset));
  return api.get<ReportListItem[]>(`/reports?${qs.toString()}`);
}

export function getReportSummary() {
  return api.get<ReportSummary>(`/reports/summary`);
}

export function getReportTemplates() {
  return api.get<ReportTemplate[]>(`/reports/templates`);
}

export function generateReport(body: ReportGenerateBody) {
  return api.post<ReportRead>(`/reports/generate`, body);
}

export function getReport(reportId: string) {
  return api.get<ReportRead>(`/reports/${reportId}`);
}

export function shareReport(reportId: string, ttlDays?: number) {
  return api.post<ReportShareResult>(`/reports/${reportId}/share`, {
    ttl_days: ttlDays ?? null,
  });
}

export function revokeReportShare(reportId: string) {
  return api.delete<ReportShareResult>(`/reports/${reportId}/share`);
}

export function deleteReport(reportId: string) {
  return api.delete<{ deleted: boolean }>(`/reports/${reportId}`);
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || (typeof window !== "undefined" ? "/api/v1" : "http://localhost:8000/api/v1");

/**
 * CSV export is a raw file download, not a JSON envelope, so it bypasses the
 * shared `request()` helper and does its own auth header + blob handling.
 */
export async function downloadReportCsv(reportId: string, filename?: string) {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const orgId =
    typeof window !== "undefined" ? localStorage.getItem("current_org_id") : null;

  const res = await fetch(`${API_URL}/reports/${reportId}/export.csv`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(orgId ? { "X-Organization-Id": orgId } : {}),
    },
  });
  if (!res.ok) {
    throw new ApiError(res.status, "خطا در دریافت خروجی CSV گزارش");
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || `report-${reportId}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export function publicReportUrl(shareToken: string): string {
  // Points at the frontend's own public viewer route, not the API host.
  if (typeof window === "undefined") return `/reports/public/${shareToken}`;
  return `${window.location.origin}/reports/public/${shareToken}`;
}
