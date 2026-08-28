"use client";

/**
 * Internal links workspace.
 *
 * Two tabs over one website:
 *  - "پیشنهادها": detector output grouped by reason, each row with an auditable
 *    relevance bar and accept/reject buttons.
 *  - "لینک‌های اعمال‌شده": what actually got applied.
 *
 * Every hook below is called before any conditional return. A hook placed after
 * an early return reorders the hook list between renders and React rejects it —
 * that has broken a page in this project already, so the guard for "no website
 * selected" is rendered inside the JSX rather than short-circuiting above.
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import { StyledSelect } from "@/components/StyledSelect";
import {
  detectInternalLinks,
  listLinkSuggestions,
  getSuggestionSummary,
  decideSuggestion,
  bulkSuggestionAction,
  deleteSuggestion,
  listInternalLinks,
  deactivateInternalLink,
  groupByReason,
  scoreComponents,
  sharedTerms,
  relevanceStyle,
  relevanceBarStyle,
  reasonStyle,
  suggestionStatusStyle,
  SUGGESTION_REASON_LABELS_FA,
  SUGGESTION_REASON_HINTS_FA,
  SUGGESTION_STATUS_LABELS_FA,
  type InternalLinkSuggestion,
  type InternalLink,
  type SuggestionSummary,
} from "@/lib/internal-links";
import {
  formatNumberFa,
  formatDateFa,
  labelFa,
} from "@/lib/insights";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ExternalLink,
  Eye,
  FileText,
  Filter,
  Info,
  Lightbulb,
  RefreshCw,
  Search,
  Target,
  Trash2,
  TrendingUp,
  X,
  Zap,
} from "lucide-react";
import toast from "react-hot-toast";

const STATUS_TABS: { id: string; label: string }[] = [
  { id: "suggested", label: "پیشنهاد شده" },
  { id: "applied", label: "اعمال‌شده" },
  { id: "rejected", label: "رد شده" },
  { id: "expired", label: "منقضی‌شده" },
  { id: "all", label: "همه" },
];

const REASON_FILTERS: { id: string; label: string }[] = [
  { id: "all", label: "همه دلایل" },
  { id: "anchor_opportunity", label: "فرصت انکر متنی" },
  { id: "orphan_target", label: "مقاله بی‌لینک (Orphan)" },
  { id: "keyword_overlap", label: "هم‌پوشانی کلمات کلیدی" },
  { id: "same_category", label: "دسته‌بندی مشترک" },
  { id: "topic_cluster", label: "خوشه موضوعی" },
];

export default function WebsiteInternalLinksPage() {
  const params = useParams();
  const websiteId = params.id as string;

  const [tab, setTab] = useState<"suggestions" | "links">("suggestions");
  const [items, setItems] = useState<InternalLinkSuggestion[]>([]);
  const [links, setLinks] = useState<InternalLink[]>([]);
  const [summary, setSummary] = useState<SuggestionSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [detecting, setDetecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("suggested");
  const [reasonFilter, setReasonFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!websiteId) return;
    setLoading(true);
    setError(null);
    try {
      const [list, sum, linkRows] = await Promise.all([
        listLinkSuggestions({
          website_id: websiteId,
          status: statusFilter === "all" ? undefined : statusFilter,
          reason: reasonFilter === "all" ? undefined : reasonFilter,
          limit: 200,
        }),
        getSuggestionSummary(websiteId),
        listInternalLinks({ website_id: websiteId, limit: 200 }),
      ]);
      setItems(Array.isArray(list) ? list : []);
      setSummary(sum);
      setLinks(Array.isArray(linkRows) ? linkRows : []);
    } catch (err: any) {
      setError(
        err instanceof ApiError ? err.message : "خطا در دریافت لینک‌های داخلی"
      );
      setItems([]);
      setLinks([]);
    } finally {
      setLoading(false);
    }
  }, [websiteId, statusFilter, reasonFilter]);

  useEffect(() => {
    load();
  }, [load]);

  // Client-side text narrowing on top of the server filters.
  const visibleItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((s) => {
      const haystack = [
        s.source_title,
        s.target_title,
        s.anchor_text,
        s.context_snippet,
      ]
        .filter((v): v is string => typeof v === "string" && v.length > 0)
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [items, search]);

  const grouped = useMemo(() => groupByReason(visibleItems), [visibleItems]);

  const activeLinks = useMemo(
    () => links.filter((l) => l.is_active),
    [links]
  );

  const handleDetect = async () => {
    setDetecting(true);
    setError(null);
    try {
      const res = await detectInternalLinks(websiteId, {
        min_relevance: 30,
        max_per_article: 5,
      });
      toast.success(
        `تحلیل کامل شد: ${formatNumberFa(res.created)} پیشنهاد جدید، ${formatNumberFa(
          res.updated
        )} بروزرسانی از ${formatNumberFa(res.scanned_articles)} مقاله`
      );
      await load();
    } catch (err: any) {
      const message =
        err instanceof ApiError ? err.message : "خطا در اجرای تحلیل لینک داخلی";
      setError(message);
      toast.error(message);
    } finally {
      setDetecting(false);
    }
  };

  const decide = async (
    suggestion: InternalLinkSuggestion,
    status: "accepted" | "rejected" | "suggested"
  ) => {
    setBusyId(suggestion.id);
    try {
      await decideSuggestion(suggestion.id, { status });
      toast.success(
        status === "accepted"
          ? "لینک داخلی ثبت و اعمال شد"
          : status === "rejected"
          ? "پیشنهاد رد شد"
          : "پیشنهاد بازگردانی شد"
      );
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در ثبت تصمیم روی پیشنهاد"
      );
    } finally {
      setBusyId(null);
    }
  };

  const removeLink = async (link: InternalLink) => {
    setBusyId(link.id);
    try {
      await deactivateInternalLink(link.id);
      toast.success("لینک داخلی غیرفعال شد");
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در حذف لینک داخلی"
      );
    } finally {
      setBusyId(null);
    }
  };

  // ---- bulk selection over the visible suggestion list ----
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const allVisibleSelected =
    visibleItems.length > 0 && visibleItems.every((s) => selectedIds.has(s.id));

  const toggleSelectAll = () => {
    if (allVisibleSelected) setSelectedIds(new Set());
    else setSelectedIds(new Set(visibleItems.map((s) => s.id)));
  };

  const bulkAction = async (action: "reject" | "delete") => {
    const ids = [...selectedIds];
    if (ids.length === 0) return;
    const verb = action === "delete" ? "حذف" : "رد";
    if (
      !window.confirm(
        `${formatNumberFa(ids.length)} پیشنهاد ${verb} شود؟ این عمل بازگشت‌پذیر نیست.`
      )
    )
      return;
    setBulkBusy(true);
    try {
      const res = await bulkSuggestionAction(websiteId, ids, action);
      toast.success(
        `${formatNumberFa(res.applied)} پیشنهاد ${verb} شد` +
          (res.skipped ? ` · ${formatNumberFa(res.skipped)} رد شد` : "")
      );
      setSelectedIds(new Set());
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : `خطا در ${verb} گروهی پیشنهادها`
      );
    } finally {
      setBulkBusy(false);
    }
  };

  const deleteOne = async (suggestion: InternalLinkSuggestion) => {
    if (!window.confirm("این پیشنهاد برای همیشه حذف شود؟")) return;
    setBusyId(suggestion.id);
    try {
      await deleteSuggestion(suggestion.id);
      toast.success("پیشنهاد حذف شد");
      await load();
    } catch (err: any) {
      toast.error(err instanceof ApiError ? err.message : "خطا در حذف پیشنهاد");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">
            لینک‌سازی داخلی (Internal Links)
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            پیشنهاد لینک بین مقالات همین سایت، بر اساس هم‌پوشانی واقعی کلمات و
            شناسایی مقالات بی‌لینک
          </p>
        </div>
        <button
          onClick={handleDetect}
          disabled={detecting || !websiteId}
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-sky-500/20 transition hover:from-sky-600 hover:to-indigo-700 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${detecting ? "animate-spin" : ""}`} />
          {detecting ? "در حال تحلیل مقالات..." : "تحلیل و پیشنهاد لینک داخلی"}
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">
              پیشنهادهای باز
            </span>
            <div className="rounded-xl bg-sky-500/10 p-2 text-sky-400">
              <Lightbulb className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-bold text-white">
            {summary ? formatNumberFa(summary.total_suggested) : "—"}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">
              مقالات بی‌لینک
            </span>
            <div className="rounded-xl bg-amber-500/10 p-2 text-amber-400">
              <AlertTriangle className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-bold text-amber-400">
            {summary ? formatNumberFa(summary.orphan_article_count) : "—"}
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            هیچ لینک داخلی به این مقالات وارد نمی‌شود
          </p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">
              میانگین امتیاز ارتباط
            </span>
            <div className="rounded-xl bg-emerald-500/10 p-2 text-emerald-400">
              <TrendingUp className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-bold text-emerald-400">
            {summary ? formatNumberFa(Math.round(summary.avg_relevance)) : "—"}
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">از ۱۰۰</p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">
              لینک‌های فعال
            </span>
            <div className="rounded-xl bg-purple-500/10 p-2 text-purple-400">
              <Zap className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-bold text-white">
            {formatNumberFa(activeLinks.length)}
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            از {summary ? formatNumberFa(summary.total_articles) : "—"} مقاله
          </p>
        </div>
      </div>

      {/* Orphan callout: the highest-value fix, so it gets its own block. */}
      {summary && summary.orphan_article_count > 0 && (
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/[0.07] p-5 backdrop-blur-md">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-amber-500/15 p-2 text-amber-400">
              <AlertCircle className="h-5 w-5" />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="text-sm font-bold text-amber-200">
                {formatNumberFa(summary.orphan_article_count)} مقاله بدون هیچ
                لینک داخلی ورودی
              </h3>
              <p className="mt-1 text-xs leading-relaxed text-amber-200/70">
                مقاله‌ای که هیچ صفحه‌ای به آن لینک نمی‌دهد، از نگاه موتور جستجو
                عملاً بخشی از ساختار سایت نیست؛ رفع این مورد بیشترین اثر را در
                بین همه پیشنهادهای این صفحه دارد.
              </p>
              {summary.orphan_articles.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {summary.orphan_articles.map((o) => (
                    <span
                      key={o.article_id}
                      className="inline-flex max-w-full items-center gap-1.5 rounded-lg border border-amber-500/20 bg-black/20 px-2.5 py-1 text-[11px] text-amber-100"
                    >
                      <FileText className="h-3 w-3 shrink-0 text-amber-400" />
                      <span className="truncate">{o.title}</span>
                      {o.published_url && (
                        <a
                          href={o.published_url}
                          target="_blank"
                          rel="noreferrer"
                          dir="ltr"
                          className="shrink-0 text-amber-400 hover:text-amber-300"
                          title="مشاهده مقاله"
                        >
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="flex flex-col gap-3 rounded-2xl border border-rose-500/20 bg-rose-500/10 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-xs leading-relaxed text-rose-300">
            <span className="font-semibold">خطا: </span>
            {error}
          </div>
          <button
            onClick={load}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-rose-500/30 px-3 py-2 text-xs font-semibold text-rose-200 transition hover:bg-rose-500/10"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            تلاش مجدد
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex flex-wrap items-center gap-1 rounded-xl bg-white/5 p-1">
        <button
          onClick={() => setTab("suggestions")}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-medium transition ${
            tab === "suggestions"
              ? "bg-white/10 text-white shadow-sm"
              : "text-muted-foreground hover:text-white"
          }`}
        >
          <Lightbulb className="h-3.5 w-3.5" />
          پیشنهادها
          {summary ? ` (${formatNumberFa(summary.total_suggested)})` : ""}
        </button>
        <button
          onClick={() => setTab("links")}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-medium transition ${
            tab === "links"
              ? "bg-white/10 text-white shadow-sm"
              : "text-muted-foreground hover:text-white"
          }`}
        >
          <Zap className="h-3.5 w-3.5" />
          لینک‌های اعمال‌شده ({formatNumberFa(activeLinks.length)})
        </button>
      </div>

      {/* Bulk selection bar — only meaningful on the suggestions tab */}
      {tab === "suggestions" && visibleItems.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5">
          <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={allVisibleSelected}
              onChange={toggleSelectAll}
              className="h-4 w-4 cursor-pointer rounded border-white/20 bg-black/30 accent-indigo-500"
            />
            انتخاب همه ({formatNumberFa(visibleItems.length)})
          </label>
          {selectedIds.size > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">
                {formatNumberFa(selectedIds.size)} انتخاب‌شده
              </span>
              <button
                onClick={() => bulkAction("reject")}
                disabled={bulkBusy}
                className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-muted-foreground transition hover:bg-white/10 hover:text-white disabled:opacity-50"
              >
                رد کردن گروهی
              </button>
              <button
                onClick={() => bulkAction("delete")}
                disabled={bulkBusy}
                className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-1.5 text-xs font-semibold text-red-400 transition hover:bg-red-500/20 disabled:opacity-50"
              >
                حذف گروهی
              </button>
            </div>
          )}
        </div>
      )}

      {tab === "suggestions" ? (
        <>
          {/* Filters */}
          <div className="rounded-2xl border border-white/10 bg-card/80 p-4 backdrop-blur-md">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex flex-wrap items-center gap-1 rounded-xl bg-white/5 p-1">
                {STATUS_TABS.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setStatusFilter(t.id)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                      statusFilter === t.id
                        ? "bg-white/10 text-white shadow-sm"
                        : "text-muted-foreground hover:text-white"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <div className="relative">
                  <Search className="absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="جستجو در عنوان مقاله یا انکر"
                    className="w-full rounded-xl border border-white/10 bg-black/40 py-2 pr-9 pl-3 text-xs text-white placeholder-muted-foreground focus:border-primary focus:outline-none sm:w-64"
                  />
                </div>

                <div className="sm:w-56">
                  <StyledSelect
                    value={reasonFilter}
                    onChange={setReasonFilter}
                    options={REASON_FILTERS.map((r) => ({ value: r.id, label: r.label }))}
                    placeholder="همه دلایل"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Suggestion list, grouped by reason */}
          {loading ? (
            <div className="space-y-3">
              {[0, 1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="animate-pulse rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md"
                >
                  <div className="h-2.5 w-32 rounded bg-white/10" />
                  <div className="mt-4 h-4 w-2/3 rounded bg-white/[0.07]" />
                  <div className="mt-3 h-2 w-full rounded bg-white/[0.05]" />
                  <div className="mt-2 h-2 w-1/2 rounded bg-white/[0.05]" />
                </div>
              ))}
            </div>
          ) : visibleItems.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-white/10 bg-card/80 py-16 text-center backdrop-blur-md">
              <Lightbulb className="mx-auto h-10 w-10 text-muted-foreground/50" />
              <h3 className="mt-3 text-sm font-semibold text-white">
                {items.length === 0
                  ? "پیشنهادی با این فیلترها یافت نشد"
                  : "نتیجه‌ای برای این جستجو یافت نشد"}
              </h3>
              <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-muted-foreground">
                {items.length === 0
                  ? "برای کشف فرصت‌های لینک داخلی، دکمه «تحلیل و پیشنهاد لینک داخلی» را بزنید. این سایت باید حداقل دو مقاله داشته باشد."
                  : "عبارت جستجو را تغییر دهید یا فیلترها را بازنشانی کنید."}
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {grouped.map((group) => (
                <div key={group.reason} className="space-y-3">
                  {/* Group header */}
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-bold ${reasonStyle(
                        group.reason
                      )}`}
                    >
                      {labelFa(SUGGESTION_REASON_LABELS_FA, group.reason)}
                    </span>
                    <span className="text-[11px] text-muted-foreground">
                      {formatNumberFa(group.items.length)} پیشنهاد
                    </span>
                    <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                      <Info className="h-3 w-3" />
                      {labelFa(SUGGESTION_REASON_HINTS_FA, group.reason)}
                    </span>
                  </div>

                  {group.items.map((s) => {
                    const components = scoreComponents(s.score_breakdown);
                    const terms = sharedTerms(s.score_breakdown);
                    const isOpen = expandedId === s.id;
                    return (
                      <div
                        key={s.id}
                        className="rounded-2xl border border-white/10 bg-card/80 p-5 shadow-lg backdrop-blur-md transition hover:border-white/20"
                      >
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                          <div className="min-w-0 flex-1 space-y-3">
                            {/* Badges */}
                            <div className="flex flex-wrap items-center gap-2">
                              <span
                                className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-bold ${relevanceStyle(
                                  s.relevance_score
                                )}`}
                              >
                                ارتباط {formatNumberFa(s.relevance_score)}
                              </span>
                              <span
                                className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${suggestionStatusStyle(
                                  s.status
                                )}`}
                              >
                                {labelFa(SUGGESTION_STATUS_LABELS_FA, s.status)}
                              </span>
                              <span className="text-[11px] text-muted-foreground">
                                شناسایی: {formatDateFa(s.detected_at)}
                              </span>
                            </div>

                            {/* Source -> target */}
                            <div className="flex flex-wrap items-center gap-2 text-xs">
                              <span className="inline-flex min-w-0 items-center gap-1.5 rounded-lg bg-white/5 px-2.5 py-1.5 text-white">
                                <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                                <span className="truncate">
                                  {s.source_title || "مقاله مبدأ"}
                                </span>
                              </span>
                              {/* ArrowRight rotated: in this RTL layout the
                                  source sits right of the target, so the
                                  flow arrow must point left. ArrowRight is
                                  the grep-confirmed icon in this repo. */}
                              <ArrowRight className="h-4 w-4 shrink-0 rotate-180 text-sky-400" />
                              <span className="inline-flex min-w-0 items-center gap-1.5 rounded-lg bg-sky-500/10 px-2.5 py-1.5 text-sky-200">
                                <Target className="h-3.5 w-3.5 shrink-0 text-sky-400" />
                                <span className="truncate">
                                  {s.target_title || "مقاله مقصد"}
                                </span>
                                {s.target_url && (
                                  <a
                                    href={s.target_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    dir="ltr"
                                    className="shrink-0 text-sky-400 hover:text-sky-300"
                                    title="مشاهده مقاله مقصد"
                                  >
                                    <ExternalLink className="h-3 w-3" />
                                  </a>
                                )}
                              </span>
                            </div>

                            {/* Anchor */}
                            <div className="text-xs">
                              <span className="text-muted-foreground">
                                انکر پیشنهادی:{" "}
                              </span>
                              <span className="rounded-md bg-emerald-500/10 px-2 py-0.5 font-semibold text-emerald-300">
                                {s.anchor_text}
                              </span>
                            </div>

                            {/* Relevance bar */}
                            <div className="space-y-1">
                              <div
                                className="h-1.5 w-full overflow-hidden rounded-full bg-white/5"
                                role="progressbar"
                                aria-valuenow={s.relevance_score}
                                aria-valuemin={0}
                                aria-valuemax={100}
                                aria-label="امتیاز ارتباط"
                              >
                                <div
                                  className={`h-full rounded-full transition-all ${relevanceBarStyle(
                                    s.relevance_score
                                  )}`}
                                  style={{
                                    width: `${Math.max(
                                      0,
                                      Math.min(100, s.relevance_score)
                                    )}%`,
                                  }}
                                />
                              </div>
                            </div>

                            {s.context_snippet && (
                              <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-[11px] leading-relaxed text-muted-foreground">
                                <span className="mb-1 block font-semibold text-white">
                                  جای پیشنهادی لینک در متن مبدأ:
                                </span>
                                {s.context_snippet}
                              </div>
                            )}

                            {/* Shared terms */}
                            {terms.length > 0 && (
                              <div className="flex flex-wrap items-center gap-1.5">
                                <span className="text-[11px] text-muted-foreground">
                                  کلمات مشترک:
                                </span>
                                {terms.map((t) => (
                                  <span
                                    key={t}
                                    className="rounded-md bg-white/5 px-1.5 py-0.5 text-[11px] text-white"
                                  >
                                    {t}
                                  </span>
                                ))}
                              </div>
                            )}

                            {/* Score breakdown: the score is shown next to an
                                accept button, so its evidence must be visible. */}
                            <div>
                              <button
                                type="button"
                                onClick={() =>
                                  setExpandedId(isOpen ? null : s.id)
                                }
                                className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-sky-400 transition hover:text-sky-300"
                              >
                                <Eye className="h-3.5 w-3.5" />
                                {isOpen
                                  ? "بستن جزئیات امتیاز"
                                  : "چرا این امتیاز؟"}
                              </button>
                              {isOpen && components.length > 0 && (
                                <div className="mt-2 space-y-1.5 rounded-lg border border-white/10 bg-black/20 p-3">
                                  {components.map((c) => (
                                    <div
                                      key={c.key}
                                      className="flex items-center justify-between gap-3 text-[11px]"
                                    >
                                      <span className="text-muted-foreground">
                                        {c.label}
                                      </span>
                                      <span className="font-bold text-white">
                                        {formatNumberFa(Math.round(c.points))}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>

                          {/* Actions */}
                          <div className="flex shrink-0 flex-wrap items-center gap-2 lg:flex-col">
                            <label
                              className="flex cursor-pointer items-center gap-1.5 text-[11px] text-muted-foreground"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <input
                                type="checkbox"
                                checked={selectedIds.has(s.id)}
                                onChange={() => toggleSelect(s.id)}
                                className="h-4 w-4 cursor-pointer rounded border-white/20 bg-black/30 accent-indigo-500"
                              />
                              انتخاب
                            </label>
                            {s.status !== "applied" && (
                              <button
                                onClick={() => decide(s, "accepted")}
                                disabled={busyId === s.id}
                                className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-400 transition hover:bg-emerald-500/20 disabled:opacity-50"
                              >
                                <CheckCircle2 className="h-3.5 w-3.5" />
                                تایید و اعمال
                              </button>
                            )}
                            {s.status !== "rejected" && (
                              <button
                                onClick={() => decide(s, "rejected")}
                                disabled={busyId === s.id}
                                className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-muted-foreground transition hover:bg-white/10 hover:text-white disabled:opacity-50"
                              >
                                <X className="h-3.5 w-3.5" />
                                رد کردن
                              </button>
                            )}
                            {s.status === "rejected" && (
                              <button
                                onClick={() => decide(s, "suggested")}
                                disabled={busyId === s.id}
                                className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-muted-foreground transition hover:bg-white/10 hover:text-white disabled:opacity-50"
                              >
                                <RefreshCw className="h-3.5 w-3.5" />
                                بازگردانی
                              </button>
                            )}
                            <button
                              onClick={() => deleteOne(s)}
                              disabled={busyId === s.id}
                              title="حذف پیشنهاد"
                              className="inline-flex items-center gap-1.5 rounded-xl border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs font-semibold text-red-400 transition hover:bg-red-500/20 disabled:opacity-50"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                              حذف
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        /* Applied links tab */
        <div className="overflow-hidden rounded-2xl border border-white/10 bg-card/80 backdrop-blur-md">
          {loading ? (
            <div className="space-y-3 p-5">
              {[0, 1, 2].map((i) => (
                <div key={i} className="animate-pulse">
                  <div className="h-3 w-1/2 rounded bg-white/[0.07]" />
                  <div className="mt-2 h-2 w-1/3 rounded bg-white/[0.05]" />
                </div>
              ))}
            </div>
          ) : links.length === 0 ? (
            <div className="py-16 text-center">
              <Zap className="mx-auto h-10 w-10 text-muted-foreground/50" />
              <h3 className="mt-3 text-sm font-semibold text-white">
                هنوز لینک داخلی ثبت نشده
              </h3>
              <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-muted-foreground">
                با تایید پیشنهادها در تب «پیشنهادها»، لینک‌های داخلی اینجا ثبت و
                پیگیری می‌شوند.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-right text-xs">
                <thead className="border-b border-white/10 bg-white/[0.02]">
                  <tr className="text-[11px] text-muted-foreground">
                    <th className="px-4 py-3 font-medium">از مقاله</th>
                    <th className="px-4 py-3 font-medium">به مقاله</th>
                    <th className="px-4 py-3 font-medium">انکر</th>
                    <th className="px-4 py-3 font-medium">وضعیت</th>
                    <th className="px-4 py-3 font-medium">ثبت</th>
                    <th className="px-4 py-3 font-medium">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {links.map((l) => (
                    <tr
                      key={l.id}
                      className="border-b border-white/5 transition hover:bg-white/[0.02]"
                    >
                      <td className="max-w-[200px] truncate px-4 py-3 text-white">
                        {l.source_title || "—"}
                      </td>
                      <td className="max-w-[200px] px-4 py-3 text-white">
                        <span className="flex items-center gap-1.5">
                          <span className="truncate">
                            {l.target_title || "—"}
                          </span>
                          {l.target_url && (
                            <a
                              href={l.target_url}
                              target="_blank"
                              rel="noreferrer"
                              dir="ltr"
                              className="shrink-0 text-sky-400 hover:text-sky-300"
                              title="مشاهده مقاله مقصد"
                            >
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          )}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="rounded-md bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-300">
                          {l.anchor_text}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {l.is_active ? (
                          <span className="rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-400">
                            فعال
                          </span>
                        ) : (
                          <span className="rounded-full bg-white/5 px-2.5 py-0.5 text-[11px] font-semibold text-muted-foreground">
                            غیرفعال
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {formatDateFa(l.first_seen_at)}
                      </td>
                      <td className="px-4 py-3">
                        {l.is_active && (
                          <button
                            onClick={() => removeLink(l)}
                            disabled={busyId === l.id}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-rose-500/20 bg-rose-500/10 px-2.5 py-1.5 text-[11px] font-semibold text-rose-300 transition hover:bg-rose-500/20 disabled:opacity-50"
                          >
                            <Trash2 className="h-3 w-3" />
                            غیرفعال کردن
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
