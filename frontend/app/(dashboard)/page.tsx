"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/context/auth-context";
import { ApiError } from "@/lib/api-client";
import {
  getDashboardSummary,
  formatNumberFa,
  formatCtrFa,
  formatPositionFa,
  formatChangePercentFa,
  formatDateTimeFa,
  type DashboardSummary,
} from "@/lib/insights";
import {
  Globe,
  ArrowUpRight,
  Sparkles,
  Zap,
  Activity,
  Plus,
  MousePointerClick,
  Eye,
  Lightbulb,
  ShieldAlert,
  TrendingUp,
  FileText,
  RefreshCw,
  Target,
} from "lucide-react";

/** Tailwind colour for a 0-100 health score. */
function healthColor(score: number): string {
  if (score >= 80) return "text-emerald-400";
  if (score >= 50) return "text-amber-400";
  return "text-rose-400";
}

/** Change deltas: positive is good for clicks/impressions. Null renders neutral. */
function changeColor(change: number | null): string {
  if (change === null) return "text-muted-foreground";
  if (change > 0) return "text-emerald-400";
  if (change < 0) return "text-rose-400";
  return "text-muted-foreground";
}

export default function DashboardHomePage() {
  const { user, currentOrg } = useAuth();

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getDashboardSummary();
      setSummary(res);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("خطا در دریافت اطلاعات داشبورد");
      }
      setSummary(null);
    } finally {
      setLoading(false);
    }
  }, []);

  // Reload when the active organization changes: the summary is org-scoped via
  // the X-Organization-Id header that api-client attaches.
  useEffect(() => {
    load();
  }, [load, currentOrg?.id]);

  return (
    <div className="space-y-8">
      {/* Welcome Hero Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-l from-primary/15 via-card to-card p-6 shadow-xl">
        <div className="relative z-10 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <div className="mb-1 inline-flex items-center gap-2 rounded-full bg-primary/20 px-3 py-1 text-xs font-semibold text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              <span>داشبورد هوشمند سئو — داده‌های زنده</span>
            </div>
            <h1 className="mt-2 text-2xl font-bold tracking-tight text-white">
              خوش آمدید، {user?.full_name}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              سازمان فعال شما:{" "}
              <span className="font-semibold text-white">
                {currentOrg ? currentOrg.name : "انتخاب نشده"}
              </span>{" "}
              | وب‌سایت‌های متصل:{" "}
              <span className="font-semibold text-emerald-400">
                {summary ? formatNumberFa(summary.website_count) : "—"} وب‌سایت
              </span>{" "}
              | پروژه‌ها:{" "}
              <span className="font-semibold text-white">
                {summary ? formatNumberFa(summary.project_count) : "—"}
              </span>
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={load}
              disabled={loading}
              className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-white/10 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              <span>{loading ? "در حال بروزرسانی..." : "بروزرسانی"}</span>
            </button>
            <Link
              href="/alerts"
              className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-white/10"
            >
              <ShieldAlert className="h-4 w-4" />
              <span>هشدارها</span>
            </Link>
            <Link
              href="/websites"
              className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-xs font-semibold text-primary-foreground shadow-lg shadow-primary/25 transition hover:bg-primary/90"
            >
              <Plus className="h-4 w-4" />
              <span>افزودن وب‌سایت</span>
            </Link>
          </div>
        </div>
      </div>

      {error && (
        <div className="flex flex-col gap-3 rounded-2xl border border-rose-500/20 bg-rose-500/10 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-xs leading-relaxed text-rose-300">
            <span className="font-semibold">خطا در بارگذاری داشبورد: </span>
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

      {loading ? (
        <div className="space-y-8">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <div
                key={i}
                className="animate-pulse rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md"
              >
                <div className="h-2.5 w-1/2 rounded bg-white/10" />
                <div className="mt-6 h-7 w-2/3 rounded bg-white/[0.07]" />
                <div className="mt-3 h-2 w-1/3 rounded bg-white/[0.05]" />
              </div>
            ))}
          </div>
          <div className="animate-pulse rounded-2xl border border-white/10 bg-card/60 p-6 backdrop-blur-md">
            <div className="h-3 w-40 rounded bg-white/10" />
            <div className="mt-6 space-y-3">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="h-8 w-full rounded bg-white/[0.05]" />
              ))}
            </div>
          </div>
        </div>
      ) : !summary ? (
        !error && (
          <div className="rounded-2xl border border-dashed border-white/10 bg-card/60 py-16 text-center backdrop-blur-md">
            <Activity className="mx-auto h-10 w-10 text-muted-foreground/50" />
            <h3 className="mt-3 text-sm font-semibold text-white">
              داده‌ای برای نمایش وجود ندارد
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              یک سازمان فعال انتخاب کنید یا اولین وب‌سایت خود را ثبت کنید.
            </p>
          </div>
        )
      ) : (
        <>
          {/* Primary KPI Cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">
                  کل کلیک‌ها (۲۸ روز)
                </span>
                <div className="rounded-xl bg-primary/10 p-2 text-primary">
                  <MousePointerClick className="h-5 w-5" />
                </div>
              </div>
              <div className="mt-4 flex items-baseline justify-between">
                <span className="text-3xl font-bold text-white">
                  {formatNumberFa(summary.total_clicks)}
                </span>
                <span
                  className={`text-xs font-semibold ${changeColor(
                    summary.clicks_change_percent
                  )}`}
                >
                  {summary.clicks_change_percent === null
                    ? "بدون مقایسه"
                    : formatChangePercentFa(summary.clicks_change_percent)}
                </span>
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">
                  کل نمایش‌ها (Impressions)
                </span>
                <div className="rounded-xl bg-blue-500/10 p-2 text-blue-400">
                  <Eye className="h-5 w-5" />
                </div>
              </div>
              <div className="mt-4 flex items-baseline justify-between">
                <span className="text-3xl font-bold text-white">
                  {formatNumberFa(summary.total_impressions)}
                </span>
                <span
                  className={`text-xs font-semibold ${changeColor(
                    summary.impressions_change_percent
                  )}`}
                >
                  {summary.impressions_change_percent === null
                    ? "بدون مقایسه"
                    : formatChangePercentFa(summary.impressions_change_percent)}
                </span>
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">
                  نرخ کلیک و میانگین رتبه
                </span>
                <div className="rounded-xl bg-purple-500/10 p-2 text-purple-400">
                  <Target className="h-5 w-5" />
                </div>
              </div>
              <div className="mt-4 flex items-baseline justify-between">
                <span className="text-3xl font-bold text-white">
                  {formatCtrFa(summary.avg_ctr)}
                </span>
                <span className="text-xs text-muted-foreground">
                  رتبه {formatPositionFa(summary.avg_position)}
                </span>
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">
                  امتیاز سلامت سئو
                </span>
                <div className="rounded-xl bg-emerald-500/10 p-2 text-emerald-400">
                  <Activity className="h-5 w-5" />
                </div>
              </div>
              <div className="mt-4 flex items-baseline justify-between">
                <span
                  className={`text-3xl font-bold ${summary.health_score > 0 ? healthColor(summary.health_score) : "text-muted-foreground text-xl"}`}
                >
                  {summary.health_score > 0 ? formatNumberFa(summary.health_score) : "در حال بررسی"}
                </span>
                <span className="text-xs text-muted-foreground">
                  {summary.last_audit_score === null || summary.last_audit_score === 0
                    ? "حسابرسی نشده"
                    : `آخرین حسابرسی: ${formatNumberFa(summary.last_audit_score)}`}
                </span>
              </div>
              <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                <div
                  className="h-full bg-emerald-500 transition-all duration-500"
                  style={{
                    width: `${Math.max(0, Math.min(100, summary.health_score))}%`,
                  }}
                />
              </div>
            </div>
          </div>

          {/* Secondary Cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Link
              href="/alerts"
              className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md transition hover:border-white/20 hover:bg-card/80"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">
                  هشدارهای فعال
                </span>
                <div className="rounded-xl bg-rose-500/10 p-2 text-rose-400">
                  <ShieldAlert className="h-5 w-5" />
                </div>
              </div>
              <div className="mt-4 flex items-baseline justify-between">
                <span className="text-3xl font-bold text-white">
                  {formatNumberFa(summary.active_alerts)}
                </span>
                <span
                  className={`text-xs font-semibold ${
                    summary.critical_alerts > 0 ? "text-rose-400" : "text-muted-foreground"
                  }`}
                >
                  {formatNumberFa(summary.critical_alerts)} بحرانی
                </span>
              </div>
            </Link>

            <div className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">
                  فرصت‌های باز سئو
                </span>
                <div className="rounded-xl bg-amber-500/10 p-2 text-amber-400">
                  <Lightbulb className="h-5 w-5" />
                </div>
              </div>
              <div className="mt-4 flex items-baseline justify-between">
                <span className="text-3xl font-bold text-white">
                  {formatNumberFa(summary.open_opportunities)}
                </span>
                <span className="text-xs text-emerald-400">
                  +{formatNumberFa(summary.estimated_traffic_gain)} کلیک تخمینی
                </span>
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">
                  وضعیت تولید محتوا
                </span>
                <div className="rounded-xl bg-teal-500/10 p-2 text-teal-400">
                  <FileText className="h-5 w-5" />
                </div>
              </div>
              <div className="mt-4 flex items-baseline justify-between">
                <span className="text-3xl font-bold text-white">
                  {formatNumberFa(summary.published_articles)}
                </span>
                <span className="text-xs text-muted-foreground">
                  {formatNumberFa(summary.draft_articles)} پیش‌نویس
                </span>
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">
                  آخرین همگام‌سازی سرچ کنسول
                </span>
                <div className="rounded-xl bg-blue-500/10 p-2 text-blue-400">
                  <Zap className="h-5 w-5" />
                </div>
              </div>
              <div className="mt-4">
                {summary.last_gsc_sync_at === null ? (
                  <span className="text-sm font-semibold text-amber-400">
                    هنوز همگام‌سازی نشده
                  </span>
                ) : (
                  <span className="text-sm font-semibold text-white">
                    {formatDateTimeFa(summary.last_gsc_sync_at)}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Per-website performance table */}
          <div className="rounded-2xl border border-white/10 bg-card/60 p-6 shadow-xl backdrop-blur-md">
            <div className="mb-6 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-white">
                  عملکرد وب‌سایت‌های سازمان
                </h2>
                <p className="text-xs text-muted-foreground">
                  کلیک، نمایش، نرخ کلیک، میانگین رتبه و وضعیت هشدارها
                </p>
              </div>
              <Link
                href="/websites"
                className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
              >
                <span>مشاهده همه</span>
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            {summary.websites.length === 0 ? (
              <div className="rounded-xl border border-dashed border-white/10 py-12 text-center">
                <Globe className="mx-auto h-10 w-10 text-muted-foreground/50" />
                <h3 className="mt-3 text-sm font-semibold text-white">
                  هنوز وب‌سایتی به این سازمان اضافه نشده است
                </h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  برای آغاز مانیتورینگ و اتوماسیون سئو، اولین وب‌سایت خود را ثبت کنید.
                </p>
                <Link
                  href="/websites"
                  className="mt-4 inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-md shadow-primary/20"
                >
                  <Plus className="h-4 w-4" />
                  <span>افزودن وب‌سایت</span>
                </Link>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-white/10 text-muted-foreground">
                    <tr>
                      <th className="pb-3 text-right">دامنه</th>
                      <th className="pb-3 text-right">نام وب‌سایت</th>
                      <th className="pb-3 text-right">کلیک</th>
                      <th className="pb-3 text-right">نمایش</th>
                      <th className="pb-3 text-right">نرخ کلیک</th>
                      <th className="pb-3 text-right">میانگین رتبه</th>
                      <th className="pb-3 text-right">سلامت</th>
                      <th className="pb-3 text-right">هشدار</th>
                      <th className="pb-3 text-right">فرصت</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {summary.websites.map((site) => (
                      <tr key={site.website_id} className="transition hover:bg-white/5">
                        <td
                          className="py-3.5 text-right font-medium text-emerald-400"
                          dir="ltr"
                        >
                          <Link href={`/websites/${site.website_id}/analytics`} className="hover:underline">
                            {site.domain}
                          </Link>
                        </td>
                        <td className="py-3.5 text-right text-white">
                          <Link href={`/websites/${site.website_id}/analytics`} className="hover:underline">
                            {site.name}
                          </Link>
                        </td>
                        <td className="py-3.5 text-right font-medium text-white">
                          {formatNumberFa(site.clicks)}
                        </td>
                        <td className="py-3.5 text-right text-muted-foreground">
                          {formatNumberFa(site.impressions)}
                        </td>
                        <td className="py-3.5 text-right text-white">
                          {formatCtrFa(site.ctr)}
                        </td>
                        <td className="py-3.5 text-right text-white">
                          {formatPositionFa(site.avg_position)}
                        </td>
                        <td className="py-3.5 text-right">
                          {site.health_score > 0 ? (
                            <span
                              className={`font-bold ${healthColor(site.health_score)}`}
                            >
                              {formatNumberFa(site.health_score)}
                            </span>
                          ) : (
                            <span className="text-muted-foreground text-xs">در حال بررسی</span>
                          )}
                        </td>
                        <td className="py-3.5 text-right">
                          {site.open_alerts > 0 ? (
                            <span className="rounded-full bg-rose-500/15 px-2.5 py-1 text-[10px] font-semibold text-rose-400">
                              {formatNumberFa(site.open_alerts)}
                            </span>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </td>
                        <td className="py-3.5 text-right">
                          <Link
                            href={`/websites/${site.website_id}/opportunities`}
                            className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2.5 py-1 text-[10px] font-semibold text-amber-400 transition hover:bg-amber-500/25"
                          >
                            <TrendingUp className="h-3 w-3" />
                            {formatNumberFa(site.open_opportunities)}
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
