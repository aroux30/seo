"use client";

/**
 * KPI dashboard — organization-level performance snapshot.
 *
 * One GET /kpi/summary feeds everything: production volume chart (recharts,
 * already a dependency), quality averages, AI agent reliability and automation
 * health. Numbers are computed server-side from real rows — nothing here is
 * hardcoded or mocked.
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { ApiError } from "@/lib/api-client";
import { formatNumberFa, labelFa } from "@/lib/insights";
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  FileText,
  Gauge,
  RefreshCw,
  Send,
  ShieldAlert,
  Target,
  TrendingUp,
} from "lucide-react";

interface KpiSummary {
  content: {
    articles_total: number;
    articles_published: number;
    articles_this_week: number;
    avg_seo_score: number;
    briefs_total: number;
    strategies_total: number;
    weekly_production: { label: string; articles: number }[];
  };
  ai: {
    total_runs: number;
    success_rate: number;
    avg_duration_ms: number;
    total_tokens: number;
  };
  automations: {
    total_runs: number;
    success_rate: number;
    avg_duration_ms: number;
  };
  seo: {
    audits_total: number;
    opportunities_open: number;
    alerts_active: number;
  };
  generated_at: string;
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-emerald-400";
  if (score >= 60) return "text-amber-400";
  return "text-rose-400";
}

function rateColor(rate: number): string {
  if (rate >= 90) return "text-emerald-400";
  if (rate >= 70) return "text-amber-400";
  return "text-rose-400";
}

export default function KpiPage() {
  const [data, setData] = useState<KpiSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { api } = await import("@/lib/api-client");
      setData(await api.get<KpiSummary>("/kpi/summary"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "خطا در دریافت شاخص‌ها");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const cards = data
    ? [
        {
          label: "کل مقالات",
          value: formatNumberFa(data.content.articles_total),
          sub: `${formatNumberFa(data.content.articles_this_week)} این هفته`,
          icon: FileText,
          tone: "text-indigo-400",
        },
        {
          label: "میانگین امتیاز سئو",
          value: formatNumberFa(data.content.avg_seo_score),
          sub: "از ۱۰۰",
          icon: Gauge,
          tone: scoreColor(data.content.avg_seo_score),
        },
        {
          label: "منتشر شده در وردپرس",
          value: formatNumberFa(data.content.articles_published),
          sub: `${formatNumberFa(data.content.briefs_total)} بریِف · ${formatNumberFa(data.content.strategies_total)} استراتژی`,
          icon: Send,
          tone: "text-emerald-400",
        },
        {
          label: "نرخ موفقیت عوامل AI",
          value: `${formatNumberFa(data.ai.success_rate)}٪`,
          sub: `${formatNumberFa(data.ai.total_runs)} اجرا · ${formatNumberFa(Math.round((data.ai.avg_duration_ms || 0) / 1000))} ثانیه میانگین`,
          icon: Bot,
          tone: rateColor(data.ai.success_rate),
        },
        {
          label: "نرخ موفقیت اتوماسیون‌ها",
          value: `${formatNumberFa(data.automations.success_rate)}٪`,
          sub: `${formatNumberFa(data.automations.total_runs)} اجرا`,
          icon: Activity,
          tone: rateColor(data.automations.success_rate),
        },
        {
          label: "فرصت‌های باز",
          value: formatNumberFa(data.seo.opportunities_open),
          sub: `${formatNumberFa(data.seo.alerts_active)} هشدار فعال`,
          icon: Target,
          tone: "text-sky-400",
        },
        {
          label: "آدیت‌های فنی",
          value: formatNumberFa(data.seo.audits_total),
          sub: "کل تاریخچه",
          icon: ShieldAlert,
          tone: "text-violet-400",
        },
        {
          label: "توکن مصرفی AI",
          value: formatNumberFa(data.ai.total_tokens),
          sub: "مجموع prompt + completion",
          icon: TrendingUp,
          tone: "text-purple-400",
        },
      ]
    : [];

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Gauge className="h-6 w-6 text-emerald-400" />
            شاخص‌های عملکرد (KPI)
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            تصویر واقعی و زنده از تولید محتوا، کیفیت سئو، پایداری عوامل هوش مصنوعی و سلامت اتوماسیون‌ها
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-white/10 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          بروزرسانی
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs text-red-300">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-28 animate-pulse rounded-2xl bg-white/5" />
          ))}
        </div>
      ) : data ? (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {cards.map((c) => {
              const Icon = c.icon;
              return (
                <div key={c.label} className="rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-muted-foreground">{c.label}</span>
                    <Icon className={`h-4 w-4 ${c.tone}`} />
                  </div>
                  <p className={`mt-2 text-2xl font-bold ${c.tone}`}>{c.value}</p>
                  <p className="mt-1 text-[11px] text-muted-foreground">{c.sub}</p>
                </div>
              );
            })}
          </div>

          {/* Weekly production chart */}
          <div className="rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md">
            <h3 className="mb-4 flex items-center gap-2 text-sm font-bold text-white">
              <TrendingUp className="h-4 w-4 text-emerald-400" />
              روند تولید محتوای هفتگی (۶ هفته اخیر)
            </h3>
            <div className="h-64" dir="ltr">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.content.weekly_production}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="label" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fill: "#94a3b8", fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      background: "#0f172a",
                      border: "1px solid rgba(255,255,255,0.1)",
                      borderRadius: 12,
                      color: "#fff",
                    }}
                    formatter={(v) => [formatNumberFa(Number(v)), "مقاله"]}
                  />
                  <Bar dataKey="articles" fill="#6366f1" radius={[8, 8, 0, 0]} maxBarSize={48} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Health summary strip */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md">
              <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-white">
                <Bot className="h-4 w-4 text-indigo-400" />
                سلامت عوامل هوش مصنوعی
              </h3>
              <div className="space-y-2 text-xs text-muted-foreground">
                <div className="flex items-center justify-between">
                  <span>وضعیت کلی</span>
                  <span className={`inline-flex items-center gap-1 font-semibold ${rateColor(data.ai.success_rate)}`}>
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {data.ai.success_rate >= 90 ? "پایدار" : data.ai.success_rate >= 70 ? "قابل قبول" : "نیاز به بررسی"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span>میانگین زمان هر اجرا</span>
                  <span className="text-white">{formatNumberFa(Math.round((data.ai.avg_duration_ms || 0) / 1000))} ثانیه</span>
                </div>
              </div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md">
              <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-white">
                <Activity className="h-4 w-4 text-amber-400" />
                سلامت اتوماسیون‌های n8n
              </h3>
              <div className="space-y-2 text-xs text-muted-foreground">
                <div className="flex items-center justify-between">
                  <span>وضعیت کلی</span>
                  <span className={`inline-flex items-center gap-1 font-semibold ${rateColor(data.automations.success_rate)}`}>
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {data.automations.success_rate >= 90 ? "پایدار" : data.automations.success_rate >= 70 ? "قابل قبول" : "نیاز به بررسی"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span>میانگین زمان اجرا</span>
                  <span className="text-white">{formatNumberFa(data.automations.avg_duration_ms)} میلی‌ثانیه</span>
                </div>
              </div>
            </div>
          </div>

          <p className="text-center text-[10px] text-muted-foreground">
            آخرین بروزرسانی: {new Date(data.generated_at).toLocaleString("fa-IR")}
          </p>
        </>
      ) : null}
    </div>
  );
}
