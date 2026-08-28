"use client";

import { StyledSelect } from "@/components/StyledSelect";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import {
  listOpportunities,
  getOpportunitySummary,
  detectOpportunities,
  updateOpportunityStatus,
  formatNumberFa,
  formatCtrFa,
  formatPositionFa,
  formatDateFa,
  labelFa,
  OPPORTUNITY_TYPE_LABELS_FA,
  OPPORTUNITY_STATUS_LABELS_FA,
  type Opportunity,
  type OpportunitySummary,
} from "@/lib/insights";
import {
  Lightbulb,
  RefreshCw,
  TrendingUp,
  Target,
  Eye,
  MousePointerClick,
  ExternalLink,
  CheckCircle2,
  X,
  AlertTriangle,
  Filter,
  Search,
} from "lucide-react";
import toast from "react-hot-toast";

const STATUS_TABS: { id: string; label: string }[] = [
  { id: "open", label: "باز" },
  { id: "in_progress", label: "در حال بررسی" },
  { id: "actioned", label: "اقدام‌شده" },
  { id: "dismissed", label: "رد شده" },
  { id: "all", label: "همه" },
];

const TYPE_FILTERS: { id: string; label: string }[] = [
  { id: "all", label: "همه انواع" },
  { id: "low_ctr_high_impressions", label: "نرخ کلیک پایین با نمایش بالا" },
  { id: "striking_distance", label: "نزدیک به صفحه اول" },
  { id: "rising_query", label: "عبارت رو به رشد" },
  { id: "content_gap", label: "خالی محتوایی" },
  { id: "decaying_content", label: "افت تدریجی محتوا" },
  { id: "cannibalization", label: "تداخل محتوایی" },
];

/** Priority score is 0-100 from the detector. Higher means act sooner. */
function priorityStyle(score: number): string {
  if (score >= 70) return "bg-rose-500/15 text-rose-400 border-rose-500/20";
  if (score >= 40) return "bg-amber-500/15 text-amber-400 border-amber-500/20";
  return "bg-blue-500/15 text-blue-400 border-blue-500/20";
}

function typeStyle(opportunityType: string): string {
  switch (opportunityType) {
    case "low_ctr_high_impressions":
      return "bg-amber-500/10 text-amber-300";
    case "striking_distance":
      return "bg-emerald-500/10 text-emerald-300";
    case "rising_query":
      return "bg-teal-500/10 text-teal-300";
    case "content_gap":
      return "bg-purple-500/10 text-purple-300";
    case "decaying_content":
      return "bg-rose-500/10 text-rose-300";
    case "cannibalization":
      return "bg-blue-500/10 text-blue-300";
    default:
      return "bg-white/5 text-muted-foreground";
  }
}

function statusStyle(status: string): string {
  switch (status) {
    case "open":
      return "bg-emerald-500/15 text-emerald-400";
    case "in_progress":
      return "bg-blue-500/15 text-blue-400";
    case "actioned":
      return "bg-purple-500/15 text-purple-400";
    case "dismissed":
      return "bg-white/5 text-muted-foreground";
    case "expired":
      return "bg-white/5 text-muted-foreground";
    default:
      return "bg-white/5 text-muted-foreground";
  }
}

export default function WebsiteOpportunitiesPage() {
  const params = useParams();
  const websiteId = params.id as string;

  const [items, setItems] = useState<Opportunity[]>([]);
  const [summary, setSummary] = useState<OpportunitySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [detecting, setDetecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("open");
  const [typeFilter, setTypeFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  // Dismiss modal state
  const [dismissTarget, setDismissTarget] = useState<Opportunity | null>(null);
  const [dismissReason, setDismissReason] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, sum] = await Promise.all([
        listOpportunities({
          website_id: websiteId,
          status: statusFilter === "all" ? undefined : statusFilter,
          opportunity_type: typeFilter === "all" ? undefined : typeFilter,
          limit: 100,
        }),
        getOpportunitySummary(websiteId),
      ]);
      setItems(Array.isArray(list) ? list : []);
      setSummary(sum);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("خطا در دریافت فرصت‌های سئو");
      }
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [websiteId, statusFilter, typeFilter]);

  useEffect(() => {
    load();
  }, [load]);

  // Client-side text narrowing on top of the server filters.
  const visibleItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((o) => {
      const haystack = [o.title, o.query, o.page_url, o.description]
        .filter((v): v is string => typeof v === "string" && v.length > 0)
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [items, search]);

  const handleDetect = async () => {
    setDetecting(true);
    setError(null);
    try {
      const res = await detectOpportunities(websiteId, {
        lookback_days: 28,
        min_impressions: 1,
      });
      toast.success(
        `شناسایی کامل شد: ${formatNumberFa(res.created)} فرصت جدید، ${formatNumberFa(
          res.updated
        )} بروزرسانی`
      );
      await load();
    } catch (err: any) {
      const message =
        err instanceof ApiError ? err.message : "خطا در اجرای شناسایی فرصت‌ها";
      setError(message);
      toast.error(message);
    } finally {
      setDetecting(false);
    }
  };

  const changeStatus = async (
    opportunity: Opportunity,
    status: "open" | "in_progress" | "actioned" | "dismissed",
    reason?: string
  ) => {
    setBusyId(opportunity.id);
    try {
      await updateOpportunityStatus(opportunity.id, {
        status,
        dismiss_reason: reason,
      });
      toast.success("وضعیت فرصت بروزرسانی شد");
      setDismissTarget(null);
      setDismissReason("");
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در بروزرسانی وضعیت فرصت"
      );
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
            فرصت‌های رشد سئو (SEO Opportunities)
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            فرصت‌های کشف‌شده از داده‌های سرچ کنسول، به‌ترتیب اولویت اثرگذاری
          </p>
        </div>
        <button
          onClick={handleDetect}
          disabled={detecting}
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-amber-500/20 transition hover:from-amber-600 hover:to-orange-700 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${detecting ? "animate-spin" : ""}`} />
          {detecting ? "در حال شناسایی فرصت‌ها..." : "شناسایی فرصت‌های جدید"}
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">
              فرصت‌های باز
            </span>
            <div className="rounded-xl bg-amber-500/10 p-2 text-amber-400">
              <Lightbulb className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-bold text-white">
            {summary ? formatNumberFa(summary.total_open) : "—"}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">
              ترافیک تخمینی قابل کسب
            </span>
            <div className="rounded-xl bg-emerald-500/10 p-2 text-emerald-400">
              <TrendingUp className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-bold text-emerald-400">
            {summary
              ? `+${formatNumberFa(summary.total_estimated_traffic_gain)}`
              : "—"}
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            کلیک ماهانه تخمینی در صورت اجرای فرصت‌ها
          </p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">
              پرتکرارترین نوع فرصت
            </span>
            <div className="rounded-xl bg-purple-500/10 p-2 text-purple-400">
              <Target className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 space-y-1.5">
            {summary && Object.keys(summary.by_type).length > 0 ? (
              Object.entries(summary.by_type)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 3)
                .map(([key, count]) => (
                  <div
                    key={key}
                    className="flex items-center justify-between text-[11px]"
                  >
                    <span className="text-muted-foreground">
                      {labelFa(OPPORTUNITY_TYPE_LABELS_FA, key)}
                    </span>
                    <span className="font-bold text-white">
                      {formatNumberFa(count)}
                    </span>
                  </div>
                ))
            ) : (
              <span className="text-xs text-muted-foreground">—</span>
            )}
          </div>
        </div>
      </div>

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

      {/* Filters */}
      <div className="rounded-2xl border border-white/10 bg-card/60 p-4 backdrop-blur-md">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-1 rounded-xl bg-white/5 p-1">
            {STATUS_TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setStatusFilter(tab.id)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  statusFilter === tab.id
                    ? "bg-white/10 text-white shadow-sm"
                    : "text-muted-foreground hover:text-white"
                }`}
              >
                {tab.label}
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
                placeholder="جستجو در عنوان، عبارت یا آدرس صفحه"
                className="w-full rounded-xl border border-white/10 bg-black/40 py-2 pr-9 pl-3 text-xs text-white placeholder-muted-foreground focus:border-primary focus:outline-none sm:w-64"
              />
            </div>

            <div className="sm:w-56">
              <StyledSelect
                value={typeFilter}
                onChange={setTypeFilter}
                options={TYPE_FILTERS.map((t) => ({ value: t.id, label: t.label }))}
                placeholder="فیلتر نوع فرصت"
              />
            </div>
          </div>
        </div>
      </div>

      {/* List */}
      {loading ? (
        <div className="space-y-3">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="animate-pulse rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md"
            >
              <div className="h-2.5 w-32 rounded bg-white/10" />
              <div className="mt-4 h-4 w-2/3 rounded bg-white/[0.07]" />
              <div className="mt-3 h-2 w-full rounded bg-white/[0.05]" />
              <div className="mt-2 h-2 w-1/2 rounded bg-white/[0.05]" />
            </div>
          ))}
        </div>
      ) : visibleItems.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-white/10 bg-card/60 py-16 text-center backdrop-blur-md">
          <Lightbulb className="mx-auto h-10 w-10 text-muted-foreground/50" />
          <h3 className="mt-3 text-sm font-semibold text-white">
            {items.length === 0
              ? "فرصتی با این فیلترها یافت نشد"
              : "نتیجه‌ای برای این جستجو یافت نشد"}
          </h3>
          <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-muted-foreground">
            {items.length === 0
              ? "برای کشف فرصت‌های رشد از داده‌های سرچ کنسول، دکمه «شناسایی فرصت‌های جدید» را بزنید. اتصال سرچ کنسول باید فعال و همگام‌سازی شده باشد."
              : "عبارت جستجو را تغییر دهید یا فیلترها را بازنشانی کنید."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {visibleItems.map((o) => (
            <div
              key={o.id}
              className="rounded-2xl border border-white/10 bg-card/60 p-5 shadow-lg backdrop-blur-md transition hover:border-white/20"
            >
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 flex-1 space-y-2.5">
                  {/* Badges */}
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-bold ${priorityStyle(
                        o.priority_score
                      )}`}
                    >
                      اولویت {formatNumberFa(o.priority_score)}
                    </span>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${typeStyle(
                        o.opportunity_type
                      )}`}
                    >
                      {labelFa(OPPORTUNITY_TYPE_LABELS_FA, o.opportunity_type)}
                    </span>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${statusStyle(
                        o.status
                      )}`}
                    >
                      {labelFa(OPPORTUNITY_STATUS_LABELS_FA, o.status)}
                    </span>
                    <span className="text-[11px] text-muted-foreground">
                      شناسایی: {formatDateFa(o.detected_at)}
                    </span>
                  </div>

                  <h3 className="text-sm font-bold text-white">{o.title}</h3>

                  {o.description && (
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      {o.description}
                    </p>
                  )}

                  {/* Query / URL */}
                  <div className="flex flex-wrap items-center gap-3 text-[11px]">
                    {o.query && (
                      <span className="inline-flex items-center gap-1 rounded-lg bg-white/5 px-2 py-1 text-white">
                        <Search className="h-3 w-3 text-muted-foreground" />
                        {o.query}
                      </span>
                    )}
                    {o.page_url && (
                      <a
                        href={o.page_url}
                        target="_blank"
                        rel="noreferrer"
                        dir="ltr"
                        className="inline-flex max-w-full items-center gap-1 truncate text-blue-400 hover:underline"
                      >
                        <span className="truncate">{o.page_url}</span>
                        <ExternalLink className="h-3 w-3 shrink-0" />
                      </a>
                    )}
                  </div>

                  {/* Metrics strip */}
                  <div className="flex flex-wrap items-center gap-4 border-t border-white/5 pt-3 text-[11px]">
                    <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                      <MousePointerClick className="h-3.5 w-3.5" />
                      کلیک:{" "}
                      <span className="font-bold text-white">
                        {formatNumberFa(o.current_clicks)}
                      </span>
                    </span>
                    <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                      <Eye className="h-3.5 w-3.5" />
                      نمایش:{" "}
                      <span className="font-bold text-white">
                        {formatNumberFa(o.current_impressions)}
                      </span>
                    </span>
                    <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                      نرخ کلیک:{" "}
                      <span className="font-bold text-white">
                        {formatCtrFa(o.current_ctr)}
                      </span>
                    </span>
                    <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                      <Target className="h-3.5 w-3.5" />
                      رتبه:{" "}
                      <span className="font-bold text-white">
                        {formatPositionFa(o.current_position)}
                      </span>
                    </span>
                    <span className="inline-flex items-center gap-1.5 text-emerald-400">
                      <TrendingUp className="h-3.5 w-3.5" />
                      رشد تخمینی:{" "}
                      <span className="font-bold">
                        +{formatNumberFa(o.estimated_traffic_gain)}
                      </span>
                    </span>
                  </div>

                  {o.recommended_action && (
                    <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3 text-xs leading-relaxed text-emerald-300">
                      <span className="mb-1 block font-semibold">
                        اقدام پیشنهادی سیستم:
                      </span>
                      {o.recommended_action}
                    </div>
                  )}

                  {o.status === "dismissed" && o.dismiss_reason && (
                    <div className="rounded-lg border border-white/10 bg-white/[0.02] p-2.5 text-[11px] text-muted-foreground">
                      <span className="font-semibold">دلیل رد شدن: </span>
                      {o.dismiss_reason}
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex shrink-0 flex-wrap gap-2 lg:flex-col">
                  {o.status !== "in_progress" && o.status !== "actioned" && (
                    <button
                      onClick={() => changeStatus(o, "in_progress")}
                      disabled={busyId === o.id}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-blue-500/20 bg-blue-500/10 px-3 py-2 text-xs font-semibold text-blue-400 transition hover:bg-blue-500/20 disabled:opacity-50"
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                      شروع بررسی
                    </button>
                  )}
                  {o.status !== "actioned" && (
                    <button
                      onClick={() => changeStatus(o, "actioned")}
                      disabled={busyId === o.id}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-400 transition hover:bg-emerald-500/20 disabled:opacity-50"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      اقدام شد
                    </button>
                  )}
                  {o.status !== "dismissed" && (
                    <button
                      onClick={() => {
                        setDismissTarget(o);
                        setDismissReason("");
                      }}
                      disabled={busyId === o.id}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-muted-foreground transition hover:bg-white/10 hover:text-white disabled:opacity-50"
                    >
                      <X className="h-3.5 w-3.5" />
                      رد کردن
                    </button>
                  )}
                  {o.status === "dismissed" && (
                    <button
                      onClick={() => changeStatus(o, "open")}
                      disabled={busyId === o.id}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-muted-foreground transition hover:bg-white/10 hover:text-white disabled:opacity-50"
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                      بازگردانی
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Dismiss reason modal */}
      {dismissTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md space-y-4 rounded-2xl border border-white/10 bg-card p-6 shadow-2xl">
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-6 w-6 shrink-0 text-amber-400" />
              <h3 className="text-base font-bold text-white">رد کردن فرصت</h3>
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              فرصت «{dismissTarget.title}» رد می‌شود. در صورت تمایل دلیل را ثبت کنید
              تا در آینده قابل پیگیری باشد.
            </p>
            <textarea
              value={dismissReason}
              onChange={(e) => setDismissReason(e.target.value)}
              rows={3}
              maxLength={1000}
              placeholder="دلیل رد شدن (اختیاری)"
              className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-xs text-white placeholder-muted-foreground focus:border-primary focus:outline-none"
            />
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => {
                  setDismissTarget(null);
                  setDismissReason("");
                }}
                className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-muted-foreground transition hover:bg-white/5"
              >
                انصراف
              </button>
              <button
                type="button"
                onClick={() =>
                  changeStatus(
                    dismissTarget,
                    "dismissed",
                    dismissReason.trim() || undefined
                  )
                }
                disabled={busyId === dismissTarget.id}
                className="rounded-xl bg-rose-600 px-5 py-2 text-xs font-semibold text-white shadow-lg transition hover:bg-rose-500 disabled:opacity-50"
              >
                {busyId === dismissTarget.id ? "در حال ثبت..." : "رد کردن فرصت"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
