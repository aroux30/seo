"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api-client";
import {
  Sparkles,
  Target,
  Compass,
  TrendingUp,
  CheckCircle2,
  Copy,
  Layers,
  FileText,
  Clock,
  Briefcase,
  AlertCircle,
  Cpu,
} from "lucide-react";

export default function WebsiteStrategiesPage() {
  const params = useParams();
  const websiteId = params.id as string;

  const [strategies, setStrategies] = useState<any[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState<"clusters" | "gaps" | "roadmap">("clusters");
  const [error, setError] = useState<string | null>(null);
  const [copiedText, setCopiedText] = useState<string | null>(null);

  useEffect(() => {
    loadStrategies();
  }, [websiteId]);

  const loadStrategies = async () => {
    setLoading(true);
    try {
      const list = await api.get(`/strategies?website_id=${websiteId}`);
      const data = list || [];
      setStrategies(data);
      if (data.length > 0) {
        await loadStrategyDetail(data[0].id);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const loadStrategyDetail = async (strategyId: string) => {
    try {
      const detail = await api.get(`/strategies/${strategyId}`);
      setSelectedStrategy(detail);
    } catch {
      // ignore
    }
  };

  const handleGenerateStrategy = async () => {
    setGenerating(true);
    setError(null);
    try {
      const res = await api.post(`/strategies/generate?website_id=${websiteId}`, {});
      if (res && res.id) {
        await loadStrategies();
      }
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("خطا در تولید استراتژی هوش مصنوعی");
      }
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(text);
    setTimeout(() => setCopiedText(null), 2000);
  };

  const getIntentBadge = (intent: string) => {
    switch (intent) {
      case "transactional":
        return (
          <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-400 border border-emerald-500/20">
            تراکنشی (Transactional)
          </span>
        );
      case "commercial":
        return (
          <span className="rounded-full bg-purple-500/10 px-2.5 py-0.5 text-[11px] font-medium text-purple-400 border border-purple-500/20">
            تجاری (Commercial)
          </span>
        );
      default:
        return (
          <span className="rounded-full bg-blue-500/10 px-2.5 py-0.5 text-[11px] font-medium text-blue-400 border border-blue-500/20">
            اطلاعاتی (Informational)
          </span>
        );
    }
  };

  const getPriorityBadge = (prio: string) => {
    return prio === "high" ? (
      <span className="rounded-md bg-rose-500/10 px-2 py-0.5 text-[11px] font-semibold text-rose-400">
        اولویت بالا
      </span>
    ) : (
      <span className="rounded-md bg-amber-500/10 px-2 py-0.5 text-[11px] font-semibold text-amber-400">
        اولویت متوسط
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-amber-400" />
            استراتژی هوشمند سئو (AI SEO Strategy Roadmap)
          </h1>
          <p className="text-xs text-muted-foreground mt-1">
            تحلیل کلمات کلیدی، تولید خوشه‌های موضوعی، کشف شکاف‌های محتوا و برنامه عملیاتی
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleGenerateStrategy}
            disabled={generating}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-amber-500/20 transition hover:from-amber-600 hover:to-orange-700 disabled:opacity-50"
          >
            <Sparkles className={`h-4 w-4 ${generating ? "animate-spin" : ""}`} />
            {generating ? "در حال تحلیل و تولید..." : "تولید استراتژی هوشمند جدید"}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 p-4 text-xs text-rose-300">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16 text-xs text-muted-foreground">
          در حال بارگذاری نقشه‌راه استراتژی...
        </div>
      ) : strategies.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-white/10 bg-card p-12 text-center">
          <Compass className="h-12 w-12 text-amber-400/50 mb-3" />
          <h3 className="text-sm font-semibold text-white">
            هنوز استراتژی هوش مصنوعی برای این وب‌سایت ایجاد نشده است
          </h3>
          <p className="mt-1 text-xs text-muted-foreground max-w-sm">
            با کلیک بر روی دکمه زیر، موتور هوش مصنوعی سایت شما را تحلیل کرده و برنامه اجرایی ۴ ماهه تولید می‌کند.
          </p>
          <button
            onClick={handleGenerateStrategy}
            disabled={generating}
            className="mt-4 inline-flex items-center gap-2 rounded-xl bg-amber-500 px-4 py-2 text-xs font-semibold text-white hover:bg-amber-600 transition"
          >
            <Sparkles className="h-4 w-4" />
            تولید اولین استراتژی سئو
          </button>
        </div>
      ) : (
        selectedStrategy && (
          <div className="space-y-6">
            {/* Executive Summary Banner */}
            <div className="relative overflow-hidden rounded-2xl border border-amber-500/20 bg-gradient-to-br from-amber-500/10 via-card to-card p-6 shadow-xl">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-amber-500/20 px-2.5 py-0.5 text-xs font-semibold text-amber-400">
                      خلاصه مدیریتی (Executive Summary)
                    </span>
                    <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                      <Cpu className="h-3 w-3" />
                      تولیدشده هوشمند (AI Strategy)
                    </span>
                  </div>
                  <h2 className="text-base font-bold text-white">
                    {selectedStrategy.title}
                  </h2>
                  <p className="text-xs text-muted-foreground leading-relaxed max-w-4xl">
                    {selectedStrategy.executive_summary}
                  </p>
                  {selectedStrategy.target_audience && (
                    <div className="mt-3 inline-flex items-center gap-2 rounded-lg bg-white/5 px-3 py-1.5 text-[11px] text-muted-foreground">
                      <Target className="h-3.5 w-3.5 text-amber-400" />
                      <span>مخاطبین هدف: {selectedStrategy.target_audience}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Strategy Navigation Tabs */}
            <div className="flex items-center gap-2 border-b border-white/10 pb-2">
              {[
                {
                  id: "clusters",
                  label: `خوشه‌های موضوعی (${selectedStrategy.keyword_clusters?.length || 0})`,
                  icon: Layers,
                },
                {
                  id: "gaps",
                  label: `شکاف‌های محتوایی (${selectedStrategy.content_gaps?.length || 0})`,
                  icon: FileText,
                },
                {
                  id: "roadmap",
                  label: `برنامه اقدام عملیاتی (${selectedStrategy.action_items?.length || 0})`,
                  icon: Briefcase,
                },
              ].map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-semibold transition ${
                      activeTab === tab.id
                        ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                        : "text-muted-foreground hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {/* Tab 1: Keyword Clusters */}
            {activeTab === "clusters" && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                {selectedStrategy.keyword_clusters?.map((cluster: any, idx: number) => (
                  <div
                    key={idx}
                    className="rounded-2xl border border-white/10 bg-card p-5 shadow-xl space-y-4 hover:border-white/20 transition"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="text-sm font-bold text-white">
                        {cluster.cluster_title}
                      </h3>
                      {getPriorityBadge(cluster.priority)}
                    </div>

                    <div className="rounded-xl bg-white/5 p-3 space-y-1">
                      <span className="text-[11px] text-muted-foreground">
                        کلمه کلیدی اصلی (Pillar Page):
                      </span>
                      <p className="text-sm font-bold text-amber-400">
                        {cluster.main_keyword}
                      </p>
                    </div>

                    <div className="space-y-2">
                      <span className="text-xs font-semibold text-white block">
                        کلمات کلیدی فرعی (Cluster Articles):
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {cluster.secondary_keywords?.map((sk: string, sidx: number) => (
                          <span
                            key={sidx}
                            className="rounded-lg bg-white/5 px-2.5 py-1 text-xs text-muted-foreground border border-white/5"
                          >
                            {sk}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="pt-2 border-t border-white/5 flex items-center justify-between">
                      <span className="text-[11px] text-muted-foreground">
                        نوع نیت کاربر:
                      </span>
                      {getIntentBadge(cluster.intent)}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Tab 2: Content Gaps */}
            {activeTab === "gaps" && (
              <div className="rounded-2xl border border-white/10 bg-card overflow-hidden shadow-xl">
                <div className="p-5 border-b border-white/10">
                  <h3 className="text-sm font-bold text-white">
                    فرصت‌ها و شکاف‌های محتوایی (Content Gaps)
                  </h3>
                  <p className="text-xs text-muted-foreground mt-1">
                    موضوعاتی که رقبا در آن رتبه دارند یا پتانسیل جذب ترافیک بالایی در بازار دارند.
                  </p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-right text-xs">
                    <thead className="bg-white/5 text-muted-foreground">
                      <tr>
                        <th className="px-4 py-3 font-semibold">موضوع اصلی</th>
                        <th className="px-4 py-3 font-semibold">کلمه کلیدی هدف</th>
                        <th className="px-4 py-3 font-semibold">حجم جستجوی تخمینی</th>
                        <th className="px-4 py-3 font-semibold">سختی رقابت</th>
                        <th className="px-4 py-3 font-semibold">عنوان پیشنهادی مقاله</th>
                        <th className="px-4 py-3 font-semibold text-center">عملیات</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {selectedStrategy.content_gaps?.map((gap: any, idx: number) => (
                        <tr key={idx} className="hover:bg-white/[0.02]">
                          <td className="px-4 py-3 font-semibold text-white">
                            {gap.topic}
                          </td>
                          <td className="px-4 py-3 text-amber-400 font-medium">
                            {gap.target_keyword}
                          </td>
                          <td className="px-4 py-3 text-muted-foreground">
                            {gap.search_volume_estimate?.toLocaleString("fa-IR")} جستجو/ماه
                          </td>
                          <td className="px-4 py-3">
                            <span className="rounded-full bg-white/5 px-2.5 py-0.5 text-[11px] text-white">
                              {gap.difficulty} / ۱۰۰
                            </span>
                          </td>
                          <td className="px-4 py-3 text-white font-medium">
                            {gap.suggested_title}
                          </td>
                          <td className="px-4 py-3 text-center">
                            <button
                              onClick={() => handleCopy(gap.suggested_title)}
                              className="inline-flex items-center gap-1 rounded-lg bg-white/5 px-2.5 py-1 text-[11px] font-medium text-muted-foreground hover:bg-white/10 hover:text-white transition"
                            >
                              <Copy className="h-3 w-3" />
                              {copiedText === gap.suggested_title ? "کپی شد!" : "کپی عنوان"}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Tab 3: Action Items Roadmap */}
            {activeTab === "roadmap" && (
              <div className="space-y-4">
                {selectedStrategy.action_items?.map((item: any, idx: number) => (
                  <div
                    key={idx}
                    className="rounded-2xl border border-white/10 bg-card p-5 shadow-xl flex flex-col md:flex-row md:items-center md:justify-between gap-4"
                  >
                    <div className="flex items-start gap-4">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-amber-500/10 text-amber-400 font-bold text-sm">
                        {idx + 1}
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="rounded-md bg-white/5 px-2 py-0.5 text-[11px] text-muted-foreground">
                            مسئول: {item.department}
                          </span>
                          <span className="rounded-md bg-white/5 px-2 py-0.5 text-[11px] text-muted-foreground flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            زمان‌بندی: {item.timeline}
                          </span>
                          {getPriorityBadge(item.impact)}
                        </div>
                        <h4 className="text-sm font-bold text-white">
                          {item.step}
                        </h4>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center gap-1 rounded-xl bg-white/5 px-3 py-1.5 text-xs font-semibold text-muted-foreground">
                        وضعیت: در انتظار اجرا
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      )}
    </div>
  );
}
