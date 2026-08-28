"use client";

/**
 * Agent Activity Center — org-level view of what every AI agent did.
 *
 * The token-usage chart is built from plain divs on purpose: no chart library is
 * installed in this project, and adding one for a single sparkline is not worth
 * the dependency. Bar heights are a percentage of the peak day, which the
 * backend already computes, so the bars never need a client-side max pass.
 *
 * Every hook in this component runs before any conditional return. A hook placed
 * after an early return changes hook order between renders and React rejects it;
 * that has already broken a page in this codebase.
 */

import { StyledSelect } from "@/components/StyledSelect";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/context/auth-context";
import { ApiError } from "@/lib/api-client";
import {
  listAgentActivity,
  getAgentActivitySummary,
  getAgentTokenUsage,
  formatTokensFa,
  formatCostUsd,
  formatConfidenceFa,
  formatPercentFa,
  formatDurationFa,
  formatDateTimeFa,
  formatChartDayFa,
  formatJsonBlock,
  labelFa,
  AGENT_TYPE_LABELS_FA,
  AGENT_STATUS_LABELS_FA,
  AGENT_PROVIDER_LABELS_FA,
  type AgentActivity,
  type AgentActivitySummary,
  type AgentTokenUsageSeries,
} from "@/lib/agent-activity";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  BarChart2,
  CheckCircle2,
  ChevronDown,
  Clock,
  Cpu,
  Eye,
  Filter,
  RefreshCw,
  Sparkles,
  Target,
  TrendingUp,
  Zap,
} from "lucide-react";

const TYPE_TABS: { id: string; label: string }[] = [
  { id: "all", label: "همه عامل‌ها" },
  { id: "audit", label: "حسابرسی" },
  { id: "strategy", label: "استراتژی" },
  { id: "brief", label: "بریف" },
  { id: "article", label: "مقاله" },
  { id: "opportunity", label: "فرصت" },
  { id: "alert", label: "هشدار" },
  { id: "automation", label: "اتوماسیون" },
  { id: "other", label: "سایر" },
];

const STATUS_FILTERS: { id: string; label: string }[] = [
  { id: "all", label: "همه وضعیت‌ها" },
  { id: "success", label: "موفق" },
  { id: "failed", label: "ناموفق" },
  { id: "partial", label: "نیمه‌موفق" },
  { id: "skipped", label: "رد شده" },
];

const RANGE_OPTIONS: { id: number; label: string }[] = [
  { id: 7, label: "۷ روز اخیر" },
  { id: 30, label: "۳۰ روز اخیر" },
  { id: 90, label: "۹۰ روز اخیر" },
];

function statusBadge(status: string) {
  switch (status) {
    case "success":
      return (
        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-400">
          <CheckCircle2 className="h-3.5 w-3.5" />
          {labelFa(AGENT_STATUS_LABELS_FA, status)}
        </span>
      );
    case "failed":
      return (
        <span className="inline-flex items-center gap-1 rounded-full border border-rose-500/20 bg-rose-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-rose-400">
          <AlertCircle className="h-3.5 w-3.5" />
          {labelFa(AGENT_STATUS_LABELS_FA, status)}
        </span>
      );
    case "partial":
      return (
        <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-amber-400">
          <AlertTriangle className="h-3.5 w-3.5" />
          {labelFa(AGENT_STATUS_LABELS_FA, status)}
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-white/5 px-2.5 py-0.5 text-[11px] font-semibold text-muted-foreground">
          {labelFa(AGENT_STATUS_LABELS_FA, status)}
        </span>
      );
  }
}

/** Confidence colour: high is reassuring, low deserves a second look. */
function confidenceColor(score: number | null): string {
  if (score === null) return "text-muted-foreground";
  if (score >= 80) return "text-emerald-400";
  if (score >= 50) return "text-amber-400";
  return "text-rose-400";
}

export default function AgentActivityPage() {
  const { websites } = useAuth();

  const [items, setItems] = useState<AgentActivity[]>([]);
  const [summary, setSummary] = useState<AgentActivitySummary | null>(null);
  const [usage, setUsage] = useState<AgentTokenUsageSeries | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [websiteFilter, setWebsiteFilter] = useState("all");
  const [rangeDays, setRangeDays] = useState(30);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, sum, tokens] = await Promise.all([
        listAgentActivity({
          website_id: websiteFilter === "all" ? undefined : websiteFilter,
          agent_type: typeFilter === "all" ? undefined : typeFilter,
          status: statusFilter === "all" ? undefined : statusFilter,
          days: rangeDays,
          limit: 100,
        }),
        getAgentActivitySummary(rangeDays),
        getAgentTokenUsage(rangeDays),
      ]);
      setItems(Array.isArray(list) ? list : []);
      setSummary(sum);
      setUsage(tokens);
    } catch (err: any) {
      setError(
        err instanceof ApiError ? err.message : "خطا در دریافت فعالیت عامل‌های هوش مصنوعی"
      );
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [typeFilter, statusFilter, websiteFilter, rangeDays]);

  useEffect(() => {
    load();
  }, [load]);

  const websiteNameById = useMemo(() => {
    const map: Record<string, string> = {};
    websites.forEach((w) => {
      map[w.id] = w.domain;
    });
    return map;
  }, [websites]);

  // Bar heights are relative to the peak day so the tallest bar always fills the
  // track; an absolute scale would flatten every bar on a low-volume org.
  const chartBars = useMemo(() => {
    if (!usage || usage.points.length === 0) return [];
    const peak = usage.peak_tokens > 0 ? usage.peak_tokens : 1;
    return usage.points.map((p) => ({
      ...p,
      heightPercent: Math.max(2, Math.round((p.total_tokens / peak) * 100)),
    }));
  }, [usage]);

  const toggleExpanded = (id: string) => {
    setExpandedId((current) => (current === id ? null : id));
  };

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">مرکز فعالیت عامل‌های هوش مصنوعی</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            هر عامل چه کاری انجام داد، با چه میزان اطمینان، با چه هزینه‌ای و بر اساس چه داده‌ای
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-white/10 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          {loading ? "در حال بروزرسانی..." : "بروزرسانی"}
        </button>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">تعداد اجرا</span>
            <div className="rounded-xl bg-primary/10 p-2 text-primary">
              <Activity className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-bold text-white">
            {summary ? formatTokensFa(summary.total_runs) : "—"}
          </div>
          {summary?.most_active_agent && (
            <p className="mt-2 truncate text-[11px] text-muted-foreground">
              فعال‌ترین: {summary.most_active_agent}
            </p>
          )}
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">نرخ موفقیت</span>
            <div className="rounded-xl bg-emerald-500/10 p-2 text-emerald-400">
              <CheckCircle2 className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-bold text-emerald-400">
            {summary ? formatPercentFa(summary.success_rate) : "—"}
          </div>
          {summary && summary.failed_runs > 0 && (
            <p className="mt-2 text-[11px] text-rose-400">
              {formatTokensFa(summary.failed_runs)} اجرای ناموفق
            </p>
          )}
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">مجموع توکن</span>
            <div className="rounded-xl bg-blue-500/10 p-2 text-blue-400">
              <Cpu className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-bold text-white">
            {summary ? formatTokensFa(summary.total_tokens) : "—"}
          </div>
          {summary && (
            <p className="mt-2 text-[11px] text-muted-foreground">
              ورودی {formatTokensFa(summary.total_prompt_tokens)} / خروجی{" "}
              {formatTokensFa(summary.total_completion_tokens)}
            </p>
          )}
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">هزینه تخمینی</span>
            <div className="rounded-xl bg-amber-500/10 p-2 text-amber-400">
              <Zap className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-bold text-white" dir="ltr">
            {summary ? formatCostUsd(summary.total_cost_usd) : "—"}
          </div>
          {summary && summary.unpriced_runs > 0 && (
            <p className="mt-2 text-[11px] text-muted-foreground">
              {formatTokensFa(summary.unpriced_runs)} اجرا بدون نرخ مشخص
            </p>
          )}
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">میانگین اطمینان</span>
            <div className="rounded-xl bg-purple-500/10 p-2 text-purple-400">
              <Target className="h-5 w-5" />
            </div>
          </div>
          <div
            className={`mt-4 text-3xl font-bold ${confidenceColor(
              summary?.avg_confidence ?? null
            )}`}
          >
            {summary ? formatConfidenceFa(summary.avg_confidence) : "—"}
          </div>
          {summary?.avg_duration_ms !== null && summary?.avg_duration_ms !== undefined && (
            <p className="mt-2 text-[11px] text-muted-foreground">
              میانگین زمان: {formatDurationFa(summary.avg_duration_ms)}
            </p>
          )}
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

      {/* Token usage chart — plain divs, no chart library installed */}
      <div className="rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <BarChart2 className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-bold text-white">مصرف توکن روزانه</h2>
          </div>
          {usage && (
            <div className="flex flex-wrap items-center gap-4 text-[11px] text-muted-foreground">
              <span>
                مجموع: <span className="font-bold text-white">{formatTokensFa(usage.total_tokens)}</span>
              </span>
              <span>
                هزینه:{" "}
                <span className="font-bold text-white" dir="ltr">
                  {formatCostUsd(usage.total_cost_usd)}
                </span>
              </span>
              <span>
                بیشترین روز:{" "}
                <span className="font-bold text-white">{formatTokensFa(usage.peak_tokens)}</span>
              </span>
            </div>
          )}
        </div>

        {loading ? (
          <div className="mt-5 h-32 animate-pulse rounded-xl bg-white/[0.04]" />
        ) : chartBars.length === 0 || usage?.total_tokens === 0 ? (
          <div className="mt-5 flex h-32 flex-col items-center justify-center rounded-xl border border-dashed border-white/10 text-center">
            <Cpu className="h-7 w-7 text-muted-foreground/40" />
            <p className="mt-2 text-xs text-muted-foreground">
              در این بازه زمانی مصرف توکنی ثبت نشده است
            </p>
          </div>
        ) : (
          <div className="mt-5">
            {/* dir=ltr: the series runs oldest -> newest left to right like any
                time axis, even inside an RTL page. */}
            <div className="flex h-32 items-end gap-[3px]" dir="ltr">
              {chartBars.map((bar) => (
                <div
                  key={bar.date}
                  className="group relative flex h-full flex-1 items-end"
                  title={`${bar.date} — ${bar.total_tokens} توکن`}
                >
                  <div
                    className="w-full rounded-t bg-gradient-to-t from-primary/40 to-primary transition group-hover:from-primary/60 group-hover:to-primary"
                    style={{ height: `${bar.heightPercent}%` }}
                  />
                  <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 hidden -translate-x-1/2 whitespace-nowrap rounded-lg border border-white/10 bg-black/90 px-2 py-1 text-[10px] text-white group-hover:block">
                    <span dir="rtl">
                      {formatChartDayFa(bar.date)} — {formatTokensFa(bar.total_tokens)} توکن
                      {bar.runs > 0 ? ` / ${formatTokensFa(bar.runs)} اجرا` : ""}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-2 flex items-center justify-between text-[10px] text-muted-foreground" dir="ltr">
              <span>{formatChartDayFa(chartBars[0]?.date)}</span>
              <span>{formatChartDayFa(chartBars[chartBars.length - 1]?.date)}</span>
            </div>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="rounded-2xl border border-white/10 bg-card/80 p-4 backdrop-blur-md">
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-1 rounded-xl bg-white/5 p-1">
            {TYPE_TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setTypeFilter(tab.id)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  typeFilter === tab.id
                    ? "bg-white/10 text-white shadow-sm"
                    : "text-muted-foreground hover:text-white"
                }`}
              >
                {tab.label}
                {summary?.by_agent_type?.[tab.id] !== undefined && (
                  <span className="mr-1.5 text-[10px] text-muted-foreground">
                    {formatTokensFa(summary.by_agent_type[tab.id])}
                  </span>
                )}
              </button>
            ))}
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="sm:w-44">
              <StyledSelect
                value={statusFilter}
                onChange={setStatusFilter}
                options={STATUS_FILTERS.map((s) => ({ value: s.id, label: s.label }))}
                placeholder="فیلتر وضعیت"
              />
            </div>

            <div className="sm:w-48">
              <StyledSelect
                value={websiteFilter}
                onChange={setWebsiteFilter}
                options={[
                  { value: "all", label: "همه وب‌سایت‌ها" },
                  ...websites.map((w) => ({ value: w.id, label: w.domain })),
                ]}
                placeholder="همه وب‌سایت‌ها"
              />
            </div>

            <div className="sm:w-40">
              <StyledSelect
                value={String(rangeDays)}
                onChange={(v) => setRangeDays(Number(v))}
                options={RANGE_OPTIONS.map((r) => ({ value: String(r.id), label: r.label }))}
                placeholder="بازه زمانی"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Activity list */}
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
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-white/10 bg-card/80 py-16 text-center backdrop-blur-md">
          <Sparkles className="mx-auto h-10 w-10 text-muted-foreground/50" />
          <h3 className="mt-3 text-sm font-semibold text-white">
            فعالیتی با این فیلترها یافت نشد
          </h3>
          <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-muted-foreground">
            به‌محض اجرای عامل‌های هوش مصنوعی (حسابرسی، استراتژی، تولید محتوا یا تشخیص فرصت)،
            سابقه کامل تصمیم‌های آن‌ها همین‌جا ثبت می‌شود.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((a) => {
            const isExpanded = expandedId === a.id;
            return (
              <div
                key={a.id}
                className="rounded-2xl border border-white/10 bg-card/80 shadow-lg backdrop-blur-md transition hover:border-white/20"
              >
                {/* Summary row */}
                <div className="p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 flex-1 space-y-2.5">
                      <div className="flex flex-wrap items-center gap-2">
                        {statusBadge(a.status)}
                        <span className="rounded-full bg-white/5 px-2.5 py-0.5 text-[11px] font-semibold text-muted-foreground">
                          {labelFa(AGENT_TYPE_LABELS_FA, a.agent_type)}
                        </span>
                        <span className="inline-flex items-center gap-1 rounded-full bg-white/5 px-2.5 py-0.5 text-[11px] text-muted-foreground">
                          <Cpu className="h-3 w-3" />
                          {labelFa(AGENT_PROVIDER_LABELS_FA, a.provider)}
                        </span>
                        {websiteNameById[a.website_id] && (
                          <span className="text-[11px] text-muted-foreground" dir="ltr">
                            {websiteNameById[a.website_id]}
                          </span>
                        )}
                      </div>

                      <h3 className="text-sm font-bold text-white">{a.agent_name}</h3>
                      <p className="text-xs leading-relaxed text-muted-foreground">
                        {a.action_taken}
                      </p>

                      {a.error_message && (
                        <div className="rounded-lg border border-rose-500/20 bg-rose-500/5 p-2.5 text-[11px] leading-relaxed text-rose-300">
                          <span className="font-semibold">خطا: </span>
                          {a.error_message}
                        </div>
                      )}

                      <div className="flex flex-wrap items-center gap-4 border-t border-white/5 pt-3 text-[11px]">
                        <span className="text-muted-foreground">
                          اطمینان:{" "}
                          <span className={`font-bold ${confidenceColor(a.confidence_score)}`}>
                            {formatConfidenceFa(a.confidence_score)}
                          </span>
                        </span>
                        <span className="text-muted-foreground">
                          توکن:{" "}
                          <span className="font-bold text-white">
                            {formatTokensFa(a.prompt_tokens + a.completion_tokens)}
                          </span>
                        </span>
                        <span className="text-muted-foreground">
                          هزینه:{" "}
                          <span className="font-bold text-white" dir="ltr">
                            {formatCostUsd(a.estimated_cost_usd)}
                          </span>
                        </span>
                        {a.duration_ms !== null && (
                          <span className="text-muted-foreground">
                            زمان:{" "}
                            <span className="font-bold text-white">
                              {formatDurationFa(a.duration_ms)}
                            </span>
                          </span>
                        )}
                        <span className="text-muted-foreground">
                          {formatDateTimeFa(a.created_at)}
                        </span>
                      </div>
                    </div>

                    <button
                      onClick={() => toggleExpanded(a.id)}
                      aria-expanded={isExpanded}
                      className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-muted-foreground transition hover:bg-white/10 hover:text-white"
                    >
                      <ChevronDown
                        className={`h-3.5 w-3.5 transition-transform ${
                          isExpanded ? "rotate-180" : ""
                        }`}
                      />
                      {isExpanded ? "بستن جزئیات" : "مشاهده جزئیات"}
                    </button>
                  </div>
                </div>

                {/* Expanded audit trail */}
                {isExpanded && (
                  <div className="space-y-4 border-t border-white/10 bg-black/20 p-5">
                    <div>
                      <div className="flex items-center gap-2">
                        <TrendingUp className="h-3.5 w-3.5 text-primary" />
                        <h4 className="text-xs font-bold text-white">تصمیم عامل</h4>
                      </div>
                      <p className="mt-2 rounded-xl border border-white/10 bg-white/[0.02] p-3 text-xs leading-relaxed text-muted-foreground">
                        {a.decision_summary || "این عامل خلاصه تصمیمی ثبت نکرده است."}
                      </p>
                    </div>

                    {a.related_entity_type && (
                      <div className="text-[11px] text-muted-foreground">
                        خروجی مرتبط:{" "}
                        <span className="font-semibold text-white">{a.related_entity_type}</span>
                        {a.related_entity_id && (
                          <span className="mr-2 font-mono text-[10px]" dir="ltr">
                            {a.related_entity_id}
                          </span>
                        )}
                      </div>
                    )}

                    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <Eye className="h-3.5 w-3.5 text-blue-400" />
                          <h4 className="text-xs font-bold text-white">داده ورودی</h4>
                        </div>
                        <pre
                          dir="ltr"
                          className="mt-2 max-h-64 overflow-auto rounded-xl border border-white/10 bg-black/50 p-3 text-[10px] leading-relaxed text-blue-200"
                        >
                          {formatJsonBlock(a.input_context)}
                        </pre>
                      </div>

                      <div>
                        <div className="flex items-center gap-2">
                          <Sparkles className="h-3.5 w-3.5 text-emerald-400" />
                          <h4 className="text-xs font-bold text-white">نتیجه خروجی</h4>
                        </div>
                        <pre
                          dir="ltr"
                          className="mt-2 max-h-64 overflow-auto rounded-xl border border-white/10 bg-black/50 p-3 text-[10px] leading-relaxed text-emerald-200"
                        >
                          {formatJsonBlock(a.output_result)}
                        </pre>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-4 border-t border-white/5 pt-3 text-[11px] text-muted-foreground">
                      <span>
                        توکن ورودی:{" "}
                        <span className="font-bold text-white">
                          {formatTokensFa(a.prompt_tokens)}
                        </span>
                      </span>
                      <span>
                        توکن خروجی:{" "}
                        <span className="font-bold text-white">
                          {formatTokensFa(a.completion_tokens)}
                        </span>
                      </span>
                      <span className="font-mono text-[10px]" dir="ltr">
                        {a.id}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
