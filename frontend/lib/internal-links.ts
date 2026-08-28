import { api } from "@/lib/api-client";

// ---------------------------------------------------------------- vocabularies

export type SuggestionStatus =
  | "suggested"
  | "accepted"
  | "rejected"
  | "applied"
  | "expired";

export type SuggestionReason =
  | "keyword_overlap"
  | "same_category"
  | "orphan_target"
  | "topic_cluster"
  | "anchor_opportunity";

export const SUGGESTION_REASON_LABELS_FA: Record<string, string> = {
  keyword_overlap: "اشتراک کلمات کلیدی",
  same_category: "دسته‌بندی یکسان",
  orphan_target: "مقاله بدون لینک ورودی (Orphan)",
  topic_cluster: "خوشه موضوعی",
  anchor_opportunity: "فرصت لنگر متنی",
};

/** Why each reason matters, shown under the group heading. */
export const SUGGESTION_REASON_HINTS_FA: Record<string, string> = {
  keyword_overlap:
    "این دو مقاله اصطلاحات کم‌تکرار و معناداری را به اشتراک می‌گذارند؛ لینک بین آن‌ها به موتور جستجو ارتباط موضوعی را نشان می‌دهد.",
  same_category: "هر دو مقاله در یک دسته‌بندی قرار دارند.",
  orphan_target:
    "مقاله هدف هیچ لینک داخلی ورودی ندارد. این پرارزش‌ترین اصلاح ممکن است، چون صفحه بدون لینک ورودی تقریباً برای خزنده‌ها نامرئی است.",
  topic_cluster: "هر دو مقاله حول یک کلمه کلیدی اصلی خوشه شده‌اند.",
  anchor_opportunity:
    "عنوان مقاله هدف عیناً در متن مقاله مبدأ آمده اما لینک نشده است. قوی‌ترین سیگنال ممکن، چون نیازی به بازنویسی متن نیست.",
};

export const SUGGESTION_STATUS_LABELS_FA: Record<string, string> = {
  suggested: "پیشنهاد شده",
  accepted: "پذیرفته شده",
  rejected: "رد شده",
  applied: "اعمال شده",
  expired: "منقضی شده",
};

/** Mirrors SCORE_WEIGHTS in internal_link_service.py. */
export const SCORE_COMPONENT_LABELS_FA: Record<string, string> = {
  shared_term_weight: "اشتراک اصطلاحات (وزن‌دار بر اساس کمیابی)",
  orphan_boost: "مقاله هدف بدون لینک ورودی",
  anchor_exact_match: "تطابق دقیق عنوان در متن مبدأ",
  title_term_hit: "اصطلاح مشترک در عنوان مقاله هدف",
  corpus_scarcity: "کوچک بودن مجموعه مقالات",
};

// -------------------------------------------------------------------- entities

export interface InternalLinkSuggestion {
  id: string;
  organization_id: string;
  website_id: string;
  source_article_id: string;
  target_article_id: string;
  anchor_text: string;
  context_snippet: string | null;
  relevance_score: number;
  score_breakdown: Record<string, any>;
  status: SuggestionStatus | string;
  reason: SuggestionReason | string;
  fingerprint: string;
  detected_at: string;
  last_seen_at: string | null;
  decided_at: string | null;
  decided_by: string | null;
  applied_at: string | null;
  created_at: string;
  updated_at: string;
  source_title: string | null;
  target_title: string | null;
  target_url: string | null;
}

export interface InternalLink {
  id: string;
  organization_id: string;
  website_id: string;
  source_article_id: string;
  target_article_id: string;
  anchor_text: string;
  target_url: string | null;
  is_active: boolean;
  suggestion_id: string | null;
  first_seen_at: string;
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
  source_title: string | null;
  target_title: string | null;
}

export interface OrphanArticleRow {
  article_id: string;
  title: string;
  slug: string | null;
  published_url: string | null;
  status: string | null;
}

export interface SuggestionSummary {
  total_suggested: number;
  by_reason: Record<string, number>;
  by_status: Record<string, number>;
  orphan_article_count: number;
  avg_relevance: number;
  orphan_articles: OrphanArticleRow[];
  total_articles: number;
  active_link_count: number;
}

export interface LinkDetectResult {
  website_id: string;
  scanned_articles: number;
  created: number;
  updated: number;
  expired: number;
  orphan_article_count: number;
  by_reason: Record<string, number>;
}

// -------------------------------------------------------------------- requests

export interface LinkDetectRequest {
  min_relevance?: number;
  max_per_article?: number;
}

export interface SuggestionDecisionRequest {
  /** "applied" and "expired" are server-side only. */
  status: "accepted" | "rejected" | "suggested";
}

// ------------------------------------------------------------------ formatting

/** Relevance is 0-100 from the detector. Higher means link this sooner. */
export function relevanceStyle(score: number): string {
  if (score >= 70) return "bg-emerald-500/15 text-emerald-400 border-emerald-500/20";
  if (score >= 45) return "bg-amber-500/15 text-amber-400 border-amber-500/20";
  return "bg-blue-500/15 text-blue-400 border-blue-500/20";
}

/** Fill colour for the relevance bar, matching relevanceStyle's thresholds. */
export function relevanceBarStyle(score: number): string {
  if (score >= 70) return "bg-emerald-500";
  if (score >= 45) return "bg-amber-500";
  return "bg-blue-500";
}

export function reasonStyle(reason: string): string {
  switch (reason) {
    case "anchor_opportunity":
      return "bg-emerald-500/10 text-emerald-300";
    case "orphan_target":
      return "bg-purple-500/10 text-purple-300";
    case "keyword_overlap":
      return "bg-blue-500/10 text-blue-300";
    case "same_category":
      return "bg-teal-500/10 text-teal-300";
    case "topic_cluster":
      return "bg-amber-500/10 text-amber-300";
    default:
      return "bg-white/5 text-muted-foreground";
  }
}

export function suggestionStatusStyle(status: string): string {
  switch (status) {
    case "suggested":
      return "bg-blue-500/15 text-blue-400";
    case "accepted":
      return "bg-emerald-500/15 text-emerald-400";
    case "applied":
      return "bg-emerald-500/15 text-emerald-400";
    case "rejected":
      return "bg-white/5 text-muted-foreground";
    case "expired":
      return "bg-white/5 text-muted-foreground";
    default:
      return "bg-white/5 text-muted-foreground";
  }
}

/**
 * Turn score_breakdown into label/points rows for the evidence panel.
 *
 * Only numeric components are shown; the breakdown also carries context keys
 * (shared_terms, corpus_size, matched_phrase) that are rendered separately.
 */
export function scoreComponents(
  breakdown: Record<string, any> | null | undefined
): { key: string; label: string; points: number }[] {
  if (!breakdown) return [];
  return Object.keys(SCORE_COMPONENT_LABELS_FA)
    .filter((key) => typeof breakdown[key] === "number" && breakdown[key] > 0)
    .map((key) => ({
      key,
      label: SCORE_COMPONENT_LABELS_FA[key],
      points: breakdown[key] as number,
    }))
    .sort((a, b) => b.points - a.points);
}

/** Shared terms are stored in the breakdown as a string array. */
export function sharedTerms(
  breakdown: Record<string, any> | null | undefined
): string[] {
  const terms = breakdown?.shared_terms;
  return Array.isArray(terms) ? terms.filter((t) => typeof t === "string") : [];
}

/** Group suggestions by reason, preserving the server's relevance ordering. */
export function groupByReason(
  items: InternalLinkSuggestion[]
): { reason: string; items: InternalLinkSuggestion[] }[] {
  const groups = new Map<string, InternalLinkSuggestion[]>();
  for (const item of items) {
    const bucket = groups.get(item.reason);
    if (bucket) {
      bucket.push(item);
    } else {
      groups.set(item.reason, [item]);
    }
  }
  // Highest top-scoring group first, so the most actionable block leads.
  return Array.from(groups.entries())
    .map(([reason, group]) => ({ reason, items: group }))
    .sort((a, b) => (b.items[0]?.relevance_score ?? 0) - (a.items[0]?.relevance_score ?? 0));
}

// ----------------------------------------------------------------------- calls

export function detectInternalLinks(websiteId: string, body?: LinkDetectRequest) {
  return api.post<LinkDetectResult>(
    `/internal-links/detect?website_id=${websiteId}`,
    body || {}
  );
}

export function listLinkSuggestions(params: {
  website_id: string;
  status?: string;
  reason?: string;
  limit?: number;
  offset?: number;
}) {
  const qs = new URLSearchParams();
  qs.set("website_id", params.website_id);
  if (params.status) qs.set("status", params.status);
  if (params.reason) qs.set("reason", params.reason);
  if (params.limit !== undefined) qs.set("limit", String(params.limit));
  if (params.offset !== undefined) qs.set("offset", String(params.offset));
  return api.get<InternalLinkSuggestion[]>(
    `/internal-links/suggestions?${qs.toString()}`
  );
}

export function getSuggestionSummary(websiteId: string) {
  return api.get<SuggestionSummary>(
    `/internal-links/suggestions/summary?website_id=${websiteId}`
  );
}

export function decideSuggestion(
  suggestionId: string,
  body: SuggestionDecisionRequest
) {
  return api.patch<InternalLinkSuggestion>(
    `/internal-links/suggestions/${suggestionId}`,
    body
  );
}

/** Bulk reject or hard-delete suggestions (list UI multi-select). */
export function bulkSuggestionAction(
  websiteId: string,
  ids: string[],
  action: "reject" | "delete"
) {
  return api.post<{ applied: number; skipped: number }>(
    `/internal-links/suggestions/bulk?website_id=${websiteId}`,
    { ids, action }
  );
}

/** Hard-delete one suggestion regardless of its status. */
export function deleteSuggestion(suggestionId: string) {
  return api.delete<{ deleted: boolean; id: string }>(
    `/internal-links/suggestions/${suggestionId}`
  );
}

export function listInternalLinks(params: {
  website_id: string;
  limit?: number;
  offset?: number;
}) {
  const qs = new URLSearchParams();
  qs.set("website_id", params.website_id);
  if (params.limit !== undefined) qs.set("limit", String(params.limit));
  if (params.offset !== undefined) qs.set("offset", String(params.offset));
  return api.get<InternalLink[]>(`/internal-links/links?${qs.toString()}`);
}

export function deactivateInternalLink(linkId: string) {
  return api.delete<InternalLink>(`/internal-links/links/${linkId}`);
}
