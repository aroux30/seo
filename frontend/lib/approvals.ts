/**
 * Approval queue — types, Persian vocabulary and API wrappers.
 *
 * Field names are lifted verbatim from `backend/app/schemas/approvals.py`
 * (ApprovalRead / ApprovalReadWithNames / ApprovalSummary). Renaming anything
 * here silently produces `undefined` in the table instead of a type error,
 * because the responses arrive as plain JSON.
 *
 * The write side is split the same way the backend splits it: a requester may
 * describe an action, a reviewer may only approve or reject. There is
 * deliberately no client type that can set `status` directly — that would make
 * the whole gate bypassable in one call.
 */

import { api } from "@/lib/api-client";

// ---------------------------------------------------------------- vocabularies

export type ApprovalActionType =
  | "publish_article"
  | "bulk_publish"
  | "bulk_delete_content"
  | "restructure_categories"
  | "change_site_settings"
  | "delete_website"
  | "ai_auto_publish"
  | "ai_bulk_rewrite"
  | "ai_keyword_campaign";

export type ApprovalStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "cancelled"
  | "executed"
  | "failed";

export type ApprovalPriority = "low" | "normal" | "high" | "urgent";

export type ApprovalRiskLevel = "low" | "medium" | "high" | "critical";

export const APPROVAL_ACTION_LABELS_FA: Record<string, string> = {
  publish_article: "انتشار مقاله",
  bulk_publish: "انتشار گروهی",
  bulk_delete_content: "حذف گروهی محتوا",
  restructure_categories: "بازچینی دسته‌بندی‌ها",
  change_site_settings: "تغییر تنظیمات سایت",
  delete_website: "حذف وب‌سایت",
  ai_auto_publish: "انتشار خودکار توسط هوش مصنوعی",
  ai_bulk_rewrite: "بازنویسی گروهی توسط هوش مصنوعی",
  ai_keyword_campaign: "کمپین کلمات کلیدی هوش مصنوعی",
};

/** Mirrors APPROVAL_ACTION_CATEGORIES in the model, for grouping the queue. */
export const APPROVAL_ACTION_CATEGORIES_FA: Record<string, string> = {
  publish_article: "محتوا",
  bulk_publish: "محتوا",
  bulk_delete_content: "محتوا",
  restructure_categories: "ساختاری",
  change_site_settings: "ساختاری",
  delete_website: "ساختاری",
  ai_auto_publish: "هوش مصنوعی",
  ai_bulk_rewrite: "هوش مصنوعی",
  ai_keyword_campaign: "هوش مصنوعی",
};

export const APPROVAL_STATUS_LABELS_FA: Record<string, string> = {
  pending: "در انتظار بررسی",
  approved: "تأیید شده",
  rejected: "رد شده",
  cancelled: "لغو شده",
  executed: "اجرا شده",
  failed: "اجرا با خطا",
};

export const APPROVAL_PRIORITY_LABELS_FA: Record<string, string> = {
  low: "کم",
  normal: "معمولی",
  high: "زیاد",
  urgent: "فوری",
};

export const APPROVAL_RISK_LABELS_FA: Record<string, string> = {
  low: "کم",
  medium: "متوسط",
  high: "زیاد",
  critical: "بحرانی",
};

/**
 * Statuses a request can no longer move out of. Mirrors
 * APPROVAL_TERMINAL_STATUSES in the model — the UI hides the decide/cancel
 * buttons on these instead of letting the user post a call that will 409.
 */
export const APPROVAL_TERMINAL_STATUSES: string[] = [
  "rejected",
  "cancelled",
  "executed",
  "failed",
];

export function isApprovalTerminal(status: string | null | undefined): boolean {
  if (!status) return false;
  return APPROVAL_TERMINAL_STATUSES.includes(status);
}

// -------------------------------------------------------------------- entities

export interface ApprovalRequest {
  id: string;
  organization_id: string;
  website_id: string | null;
  action_type: ApprovalActionType | string;
  status: ApprovalStatus | string;
  priority: ApprovalPriority | string;
  title: string;
  description: string | null;
  requester_id: string;
  reviewer_id: string | null;
  payload: Record<string, any>;
  risk_level: ApprovalRiskLevel | string;
  affected_items_count: number;
  decided_by: string | null;
  decided_at: string | null;
  reviewer_comment: string | null;
  executed_at: string | null;
  execution_error: string | null;
  execution_result: Record<string, any> | null;
  expires_at: string | null;
  related_article_id: string | null;
  related_brief_id: string | null;
  created_at: string;
  updated_at: string;
}

/** The list endpoint resolves display names via outer joins; all are nullable. */
export interface ApprovalRequestWithNames extends ApprovalRequest {
  requester_name: string | null;
  requester_email: string | null;
  reviewer_name: string | null;
  decided_by_name: string | null;
  website_name: string | null;
}

export interface ApprovalSummary {
  pending: number;
  pending_urgent: number;
  pending_high_risk: number;
  approved_awaiting_execution: number;
  expiring_soon: number;
  by_action_type: Record<string, number>;
  by_priority: Record<string, number>;
}

export interface ApprovalExpireResult {
  expired: number;
}

// ------------------------------------------------------------------- requests

export interface ApprovalCreateRequest {
  action_type: ApprovalActionType | string;
  title: string;
  description?: string;
  website_id?: string;
  reviewer_id?: string;
  priority?: ApprovalPriority;
  risk_level?: ApprovalRiskLevel;
  affected_items_count?: number;
  payload?: Record<string, any>;
  expires_in_hours?: number;
  related_article_id?: string;
  related_brief_id?: string;
}

export interface ApprovalDecisionRequest {
  decision: "approved" | "rejected";
  reviewer_comment?: string;
}

export interface ApprovalCancelRequest {
  reason?: string;
}

// ----------------------------------------------------------------- formatting

/**
 * Human countdown to the deadline. Returns null when there is no deadline, so
 * the caller can omit the column rather than print a placeholder.
 */
export function formatExpiryFa(expiresAt: string | null | undefined): string | null {
  if (!expiresAt) return null;
  const target = new Date(expiresAt);
  if (Number.isNaN(target.getTime())) return null;

  const diffMs = target.getTime() - Date.now();
  if (diffMs <= 0) return "مهلت پایان یافته";

  const hours = Math.floor(diffMs / 3_600_000);
  if (hours < 1) {
    const minutes = Math.max(1, Math.floor(diffMs / 60_000));
    return `${minutes.toLocaleString("fa-IR")} دقیقه باقی مانده`;
  }
  if (hours < 24) return `${hours.toLocaleString("fa-IR")} ساعت باقی مانده`;
  const days = Math.floor(hours / 24);
  return `${days.toLocaleString("fa-IR")} روز باقی مانده`;
}

/** True when the deadline is inside the window the summary calls "expiring soon". */
export function isExpiringSoon(
  expiresAt: string | null | undefined,
  withinHours = 24
): boolean {
  if (!expiresAt) return false;
  const target = new Date(expiresAt);
  if (Number.isNaN(target.getTime())) return false;
  const diffMs = target.getTime() - Date.now();
  return diffMs > 0 && diffMs <= withinHours * 3_600_000;
}

// ---------------------------------------------------------------------- calls

export function listApprovals(params?: {
  website_id?: string;
  status?: string;
  action_type?: string;
  priority?: string;
  mine_only?: boolean;
  assigned_to_me?: boolean;
  limit?: number;
  offset?: number;
}) {
  const qs = new URLSearchParams();
  if (params?.website_id) qs.set("website_id", params.website_id);
  if (params?.status) qs.set("status", params.status);
  if (params?.action_type) qs.set("action_type", params.action_type);
  if (params?.priority) qs.set("priority", params.priority);
  if (params?.mine_only !== undefined) qs.set("mine_only", String(params.mine_only));
  if (params?.assigned_to_me !== undefined)
    qs.set("assigned_to_me", String(params.assigned_to_me));
  if (params?.limit !== undefined) qs.set("limit", String(params.limit));
  if (params?.offset !== undefined) qs.set("offset", String(params.offset));
  const qsStr = qs.toString();
  return api.get<ApprovalRequestWithNames[]>(`/approvals${qsStr ? `?${qsStr}` : ""}`);
}

export function getApprovalSummary() {
  return api.get<ApprovalSummary>("/approvals/summary");
}

export function getApproval(approvalId: string) {
  return api.get<ApprovalRequest>(`/approvals/${approvalId}`);
}

export function createApproval(body: ApprovalCreateRequest) {
  return api.post<ApprovalRequest>("/approvals", body);
}

export function decideApproval(approvalId: string, body: ApprovalDecisionRequest) {
  return api.post<ApprovalRequest>(`/approvals/${approvalId}/decide`, body);
}

export function cancelApproval(approvalId: string, body?: ApprovalCancelRequest) {
  return api.post<ApprovalRequest>(`/approvals/${approvalId}/cancel`, body || {});
}

export function expireStaleApprovals() {
  return api.post<ApprovalExpireResult>("/approvals/expire-stale", {});
}
