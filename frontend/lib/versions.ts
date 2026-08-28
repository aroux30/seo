/**
 * Content versioning — types, Persian vocabulary and API wrappers.
 *
 * Field names are lifted verbatim from `backend/app/schemas/versions.py`
 * (ContentVersionListItem / ContentVersionRead / ContentVersionDiff /
 * ContentVersionSummary). Renaming anything here silently produces `undefined`
 * in the UI instead of a type error, because the responses arrive as plain JSON.
 *
 * There is no create/update type in here on purpose: revisions are minted by
 * the backend whenever an article changes, never posted by a client. The only
 * writable payload in the whole module is the rollback note.
 *
 * Note the two read shapes. The history list returns metadata only — no
 * `content_markdown` / `content_html` — so a 50-revision sidebar does not ship
 * a megabyte of duplicated article bodies. Bodies arrive only from
 * `getVersion()`.
 */

import { api } from "@/lib/api-client";

// ---------------------------------------------------------------- vocabularies

export type ContentChangeType =
  | "created"
  | "edited"
  | "ai_rewrite"
  | "rollback"
  | "published"
  | "imported";

export const CHANGE_TYPE_LABELS_FA: Record<string, string> = {
  created: "ایجاد شد",
  edited: "ویرایش دستی",
  ai_rewrite: "بازنویسی با هوش مصنوعی",
  rollback: "بازگردانی نسخه",
  published: "انتشار",
  imported: "درون‌ریزی",
};

/**
 * Mirrors CONTENT_SYSTEM_CHANGE_TYPES in the model. `changed_by` is null on
 * these, so the author cell shows "سیستم" rather than an empty space.
 */
export const SYSTEM_CHANGE_TYPES: string[] = ["ai_rewrite", "imported"];

export function isSystemChange(changeType: string | null | undefined): boolean {
  if (!changeType) return false;
  return SYSTEM_CHANGE_TYPES.includes(changeType);
}

/** Diff line kinds as normalised by the service's `_classify_diff_line`. */
export type DiffLineKind = "context" | "added" | "removed" | "header" | "hunk";

// -------------------------------------------------------------------- entities

export interface ContentVersionDiffStats {
  added_chars: number;
  removed_chars: number;
  added_words: number;
  removed_words: number;
}

/** History sidebar row — deliberately no bodies. */
export interface ContentVersionListItem {
  id: string;
  organization_id: string;
  website_id: string;
  article_id: string;
  version_number: number;
  title: string;
  seo_score: number;
  change_type: ContentChangeType | string;
  change_summary: string | null;
  changed_by: string | null;
  diff_stats: Record<string, number>;
  is_current: boolean;
  created_at: string;
}

/** Full snapshot, as returned by `GET /versions/{id}`. */
export interface ContentVersion extends ContentVersionListItem {
  content_markdown: string;
  content_html: string;
  seo_metadata: Record<string, any>;
}

export interface ContentVersionDiffLine {
  kind: DiffLineKind | string;
  text: string;
}

export interface ContentVersionDiff {
  article_id: string;
  from_version_number: number;
  to_version_number: number;
  from_created_at: string;
  to_created_at: string;
  title_changed: boolean;
  from_title: string;
  to_title: string;
  from_seo_score: number;
  to_seo_score: number;
  seo_score_delta: number;
  stats: ContentVersionDiffStats;
  lines: ContentVersionDiffLine[];
  identical: boolean;
  truncated: boolean;
}

export interface ContentVersionSummary {
  article_id: string;
  total_versions: number;
  current_version_number: number | null;
  last_changed_at: string | null;
  contributors: number;
}

// ------------------------------------------------------------------- requests

export interface ContentVersionRollbackRequest {
  change_summary?: string;
}

export interface ContentVersionRollbackResult {
  restored_from_version_number: number;
  new_version: ContentVersion;
}

// ----------------------------------------------------------------- formatting

/**
 * Renders diff_stats as a compact Persian summary, e.g. "۳۴۰ واژه افزوده، ۱۲
 * واژه حذف شده". Words, not characters: a Persian reader judges the size of an
 * edit in words, and character counts inflate wildly on RTL text with diacritics.
 *
 * Returns "بدون تغییر" when both sides are zero so a caller never has to decide
 * what an empty string should look like. Accepts the loose
 * `Record<string, number>` that the list rows carry, because JSONB round-trips
 * as an untyped object and an older row may predate a key.
 */
export function formatDiffStatsFa(
  stats: Record<string, number> | ContentVersionDiffStats | null | undefined
): string {
  if (!stats) return "بدون تغییر";
  const added = Number((stats as any).added_words ?? 0);
  const removed = Number((stats as any).removed_words ?? 0);
  if (!added && !removed) return "بدون تغییر";

  const parts: string[] = [];
  if (added) parts.push(`${added.toLocaleString("fa-IR")} واژه افزوده`);
  if (removed) parts.push(`${removed.toLocaleString("fa-IR")} واژه حذف شده`);
  return parts.join("، ");
}

/** Signed SEO score delta for the diff header, or null when unchanged. */
export function formatScoreDeltaFa(delta: number | null | undefined): string | null {
  if (!delta) return null;
  const magnitude = Math.abs(delta).toLocaleString("fa-IR");
  return delta > 0 ? `${magnitude}+ امتیاز سئو` : `${magnitude}- امتیاز سئو`;
}

/**
 * Author cell text. Returns null when a real user id is present, so the caller
 * resolves and renders the name itself; "سیستم" covers every write with no user
 * behind it (worker, AI, import).
 */
export function changeAuthorLabelFa(version: ContentVersionListItem): string | null {
  return version.changed_by ? null : "سیستم";
}

// ---------------------------------------------------------------------- calls

export function listVersions(params: {
  article_id: string;
  limit?: number;
  offset?: number;
}) {
  const qs = new URLSearchParams({ article_id: params.article_id });
  if (params.limit !== undefined) qs.set("limit", String(params.limit));
  if (params.offset !== undefined) qs.set("offset", String(params.offset));
  return api.get<ContentVersionListItem[]>(`/versions?${qs.toString()}`);
}

export function getVersionSummary(articleId: string) {
  const qs = new URLSearchParams({ article_id: articleId });
  return api.get<ContentVersionSummary>(`/versions/summary?${qs.toString()}`);
}

export function diffVersions(params: {
  article_id: string;
  from_version: number;
  to_version: number;
}) {
  const qs = new URLSearchParams({
    article_id: params.article_id,
    from_version: String(params.from_version),
    to_version: String(params.to_version),
  });
  return api.get<ContentVersionDiff>(`/versions/diff?${qs.toString()}`);
}

export function getVersion(versionId: string) {
  return api.get<ContentVersion>(`/versions/${versionId}`);
}

export function rollbackToVersion(
  versionId: string,
  body?: ContentVersionRollbackRequest
) {
  return api.post<ContentVersionRollbackResult>(
    `/versions/${versionId}/rollback`,
    body || {}
  );
}
