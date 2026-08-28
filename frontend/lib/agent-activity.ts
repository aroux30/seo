/**
 * Agent Activity Center — types, Persian vocabulary and API wrappers.
 *
 * Field names are lifted verbatim from `backend/app/schemas/agent_activity.py`
 * (AgentActivityRead / AgentActivitySummary / AgentTokenUsageSeries). Renaming
 * anything here silently yields `undefined` in the table rather than a type
 * error, because the responses arrive as untyped JSON.
 *
 * There is deliberately no write wrapper. Agent logs are an audit trail written
 * by the backend service that ran the agent; a client-side "create log" call
 * would let the UI forge the record of what an AI decided.
 *
 * `organization_id` and the two Numeric-backed fields are nullable on purpose:
 * rows predating migration 0015 have no org, and `confidence_score` /
 * `estimated_cost_usd` are null when the agent reported no confidence and when
 * the provider has no known price. Null must render as "—", never as zero.
 */

import { api } from "@/lib/api-client";

// ---------------------------------------------------------------- vocabularies

export type AgentType =
  | "audit"
  | "strategy"
  | "brief"
  | "article"
  | "opportunity"
  | "alert"
  | "automation"
  | "other";

export type AgentStatus = "success" | "failed" | "partial" | "skipped";

export const AGENT_TYPE_LABELS_FA: Record<string, string> = {
  audit: "حسابرسی فنی",
  strategy: "استراتژی سئو",
  brief: "بریف محتوا",
  article: "تولید مقاله",
  opportunity: "شناسایی فرصت",
  alert: "تشخیص هشدار",
  automation: "اتوماسیون",
  other: "سایر",
};

export const AGENT_STATUS_LABELS_FA: Record<string, string> = {
  success: "موفق",
  failed: "ناموفق",
  partial: "نیمه‌موفق",
  skipped: "رد شده",
};

export const AGENT_PROVIDER_LABELS_FA: Record<string, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  google: "Google",
  algorithmic_fallback: "الگوریتم داخلی (بدون هوش مصنوعی)",
};

// -------------------------------------------------------------------- entities

export interface AgentActivity {
  id: string;
  website_id: string;
  organization_id: string | null;
  agent_name: string;
  agent_type: AgentType | string;
  provider: string;
  action_taken: string;
  status: AgentStatus | string;
  prompt_tokens: number;
  completion_tokens: number;
  confidence_score: number | null;
  decision_summary: string | null;
  input_context: Record<string, any> | null;
  output_result: Record<string, any> | null;
  duration_ms: number | null;
  error_message: string | null;
  estimated_cost_usd: number | null;
  related_entity_type: string | null;
  related_entity_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentActivitySummary {
  days: number;
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  success_rate: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  unpriced_runs: number;
  avg_confidence: number | null;
  avg_duration_ms: number | null;
  by_agent_type: Record<string, number>;
  by_provider: Record<string, number>;
  by_status: Record<string, number>;
  most_active_agent: string | null;
  last_run_at: string | null;
}

export interface AgentTokenUsagePoint {
  date: string;
  runs: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
}

export interface AgentTokenUsageSeries {
  days: number;
  points: AgentTokenUsagePoint[];
  total_tokens: number;
  total_cost_usd: number;
  peak_tokens: number;
}

// ----------------------------------------------------------------- formatting

/** Integer display in Persian digits. Em-dash for null. */
export function formatTokensFa(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString("fa-IR");
}

/**
 * USD cost. Kept in Latin digits with a `$` because it is a currency amount in
 * a foreign currency — rendering it in Persian digits reads as if it were rial.
 * Sub-cent runs are shown with 4 decimals so a cheap call is not displayed as
 * $0.00, which would look like a bug.
 */
export function formatCostUsd(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (value === 0) return "$0";
  if (value < 0.01) return `$${value.toFixed(4)}`;
  return `$${value.toFixed(2)}`;
}

/** Confidence is stored 0-100. Null means the agent reported none. */
export function formatConfidenceFa(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toLocaleString("fa-IR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 1,
  })}٪`;
}

/** Percentage already expressed 0-100 (e.g. success_rate). */
export function formatPercentFa(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toLocaleString("fa-IR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 1,
  })}٪`;
}

/** Milliseconds, promoted to seconds once it stops being readable as ms. */
export function formatDurationFa(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms).toLocaleString("fa-IR")} میلی‌ثانیه`;
  const seconds = ms / 1000;
  if (seconds < 60) {
    return `${seconds.toLocaleString("fa-IR", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })} ثانیه`;
  }
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes.toLocaleString("fa-IR")} دقیقه و ${rest.toLocaleString("fa-IR")} ثانیه`;
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

/** Short label for the chart axis: day + month, no year. */
export function formatChartDayFa(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("fa-IR", { month: "short", day: "numeric" });
}

/** Persian label lookup that degrades to the raw key instead of `undefined`. */
export function labelFa(map: Record<string, string>, key: string | null | undefined): string {
  if (!key) return "—";
  return map[key] ?? key;
}

/** Pretty-print a JSON audit-trail blob for the expanded row. */
export function formatJsonBlock(value: Record<string, any> | null | undefined): string {
  if (value === null || value === undefined) return "—";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    // Circular or otherwise unserialisable: show something rather than crashing
    // the row that is meant to be the audit trail.
    return String(value);
  }
}

// ---------------------------------------------------------------------- calls

export function listAgentActivity(params?: {
  website_id?: string;
  agent_name?: string;
  agent_type?: string;
  status?: string;
  days?: number;
  limit?: number;
  offset?: number;
}) {
  const qs = new URLSearchParams();
  if (params?.website_id) qs.set("website_id", params.website_id);
  if (params?.agent_name) qs.set("agent_name", params.agent_name);
  if (params?.agent_type) qs.set("agent_type", params.agent_type);
  if (params?.status) qs.set("status", params.status);
  if (params?.days !== undefined) qs.set("days", String(params.days));
  if (params?.limit !== undefined) qs.set("limit", String(params.limit));
  if (params?.offset !== undefined) qs.set("offset", String(params.offset));
  const qsStr = qs.toString();
  return api.get<AgentActivity[]>(`/agent-activity${qsStr ? `?${qsStr}` : ""}`);
}

export function getAgentActivitySummary(days?: number) {
  const qs = days !== undefined ? `?days=${days}` : "";
  return api.get<AgentActivitySummary>(`/agent-activity/summary${qs}`);
}

export function getAgentTokenUsage(days?: number) {
  const qs = days !== undefined ? `?days=${days}` : "";
  return api.get<AgentTokenUsageSeries>(`/agent-activity/token-usage${qs}`);
}

export function getAgentActivity(logId: string) {
  return api.get<AgentActivity>(`/agent-activity/${logId}`);
}
