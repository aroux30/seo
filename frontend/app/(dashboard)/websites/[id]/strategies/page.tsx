"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
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
  Zap,
  ArrowRight,
  SlidersHorizontal,
  History,
  PlusCircle,
  BarChart3,
} from "lucide-react";
import toast from "react-hot-toast";

const FOCUS_AREAS = [
  { id: "", label: "استراتژی جامع ۳۶۰ درجه (توصیه‌شده)" },
  { id: "quick_wins", label: "⚡ دستاوردهای سریع و کلمات رتبه ۴ تا ۱۵ (Quick Wins)" },
  { id: "topical_authority", label: "👑 تسلط بر مرجعیت موضوعی (Topical Authority)" },
  { id: "revenue_ecommerce", label: "💰 کلمات تراکنشی و افزایش فروش (E-commerce)" },
  { id: "technical_recovery", label: "🛠️ رفع خطاهای فنی و هم‌نوع‌خواری (Technical Recovery)" },
  { id: "content_gap_expansion", label: "🔍 تسخیر شکاف‌های محتوایی عمیق (Content Gaps)" },
];

const AI_PROVIDERS = [
  { id: "", label: "ارائه‌دهنده پیش‌فرض سیستم (چرخش هوشمند)" },
  { id: "openai", label: "OpenAI (GPT-4o)" },
  { id: "gemini", label: "Google Gemini (Flash/Pro)" },
  { id: "deepseek", label: "DeepSeek (V3 / R1)" },
  { id: "claude", label: "Anthropic Claude" },
];

export default function WebsiteStrategiesPage() {
  const params = useParams();
  const router = useRouter();
  const websiteId = params.id as string;

  const [strategies, setStrategies] = useState<any[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [creatingBriefId, setCreatingBriefId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"clusters" | "gaps" | "roadmap">("clusters");
  const [error, setError] = useState<string | null>(null);
  const [copiedText, setCopiedText] = useState<string | null>(null);

  // Generation Modal / Options State
  const [showOptionsModal, setShowOptionsModal] = useState(false);
  const [selectedFocusArea, setSelectedFocusArea] = useState("");
  const [selectedProvider, setSelectedProvider] = useState("");

  useEffect(() => {
    loadStrategies();
  }, [websiteId]);

  const loadStrategies = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/strategies?website_id=${websiteId}`);
      const data = res?.data || res || [];
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
      const res = await api.get(`/strategies/${strategyId}`);
      const detail = res?.data || res;
      setSelectedStrategy(detail);
    } catch {
      // ignore
    }
  };

  const handleGenerateStrategy = async () => {
    setGenerating(true);
    setError(null);
    setShowOptionsModal(false);
    try {
      const payload: any = {};
      if (selectedFocusArea) payload.focus_area = selectedFocusArea;
      if (selectedProvider) payload.provider = selectedProvider;

      const res = await api.post(`/strategies/generate?website_id=${websiteId}`, payload);
      const newStrategy = res?.data || res;
      toast.success("استراتژی پیشرفته با موفقیت تدوین شد");
      await loadStrategies();
      if (newStrategy?.id) {
        await loadStrategyDetail(newStrategy.id);
      }
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
        toast.error(err.message);
      } else {
        const msg = err?.message || "خطا در تولید استراتژی هوش مصنوعی";
        setError(msg);
        toast.error(msg);
      }
    } finally {
      setGenerating(false);
    }
  };

  const handleCreateBriefFromGap = async (gap: any, idx: number) => {
    const gapKey = `${gap.target_keyword}-${idx}`;
    setCreatingBriefId(gapKey);
    try {
      await api.post("/content/briefs", {
        website_id: websiteId,
        target_keyword: gap.target_keyword,
        title: gap.suggested_title || gap.topic,
        search_intent: "informational",
        target_word_count: 1500,
      });
      toast.success(`بریف برای «${gap.target_keyword}» ساخته شد! به صفحه تولید محتوا منتقل می‌شوید.`);
      router.push(`/websites/${websiteId}/content`);
    } catch (err: any) {
      toast.error(err.message || "خطا در ساخت بریف محتوایی");
    } finally {
      setCreatingBriefId(null);
    }
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(text);
    toast.success("عنوان با موفقیت کپی شد");
    setTimeout(() => setCopiedText(null), 2000);
  };

  const getIntentBadge = (intent: string) => {
    const normalized = (intent || "").trim().toLowerCase();
    if (normalized === "transactional" || normalized === "تراکنشی") {
      return (
        <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-400 border border-emerald-500/20">
          تراکنشی (Transactional)
        </span>
      );
    }
    if (normalized === "commercial" || normalized === "تجاری") {
      return (
        <span className="rounded-full bg-purple-500/10 px-2.5 py-0.5 text-[11px] font-medium text-purple-400 border border-purple-500/20">
          تجاری (Commercial)
        </span>
      );
    }
    if (normalized === "navigational" || normalized === "ناوبری") {
      return (
        <span className="rounded-full bg-teal-500/10 px-2.5 py-0.5 text-[11px] font-medium text-teal-400 border border-teal-500/20">
          ناوبری (Navigational)
        </span>
      );
    }
    return (
      <span className="rounded-full bg-blue-500/10 px-2.5 py-0.5 text-[11px] font-medium text-blue-400 border border-blue-500/20">
        اطلاعاتی (Informational)
      </span>
    );
  };

  const getPriorityBadge = (prio: string) => {
    const normalized = (prio || "").trim().toLowerCase();
    if (normalized === "high" || normalized === "بالا") {
      return (
        <span className="rounded-md bg-rose-500/10 px-2 py-0.5 text-[11px] font-semibold text-rose-400">
          اولویت بالا
        </span>
      );
    }
    if (normalized === "low" || normalized === "پایین") {
      return (
        <span className="rounded-md bg-slate-500/10 px-2 py-0.5 text-[11px] font-semibold text-slate-400">
          اولویت پایین
        </span>
      );
    }
    return (
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
            موتور تحلیل داده‌های سرچ کنسول، ساختار سیلوی موضوعی، کشف شکاف‌های بازار و برنامه اقدام عملیاتی
          </p>
        </div>

        <div className="flex items-center gap-2">
          {strategies.length > 1 && (
            <div className="relative">
              <select
                value={selectedStrategy?.id || ""}
                onChange={(e) => loadStrategyDetail(e.target.value)}
                className="rounded-xl border border-white/10 bg-card px-3 py-2 text-xs text-white focus:border-amber-500 focus:outline-none"
              >
                {strategies.map((s, idx) => (
                  <option key={s.id} value={s.id}>
                    نسخه {strategies.length - idx}: {new Date(s.created_at).toLocaleDateString("fa-IR")} ({s.title?.slice(0, 25)}...)
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            onClick={() => setShowOptionsModal(true)}
            disabled={generating}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-amber-500/20 transition hover:from-amber-600 hover:to-orange-700 disabled:opacity-50"
          >
            <Sparkles className={`h-4 w-4 ${generating ? "animate-spin" : ""}`} />
            {generating ? "در حال تدوین استراتژی..." : "تولید استراتژی جدید"}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 text-xs text-muted-foreground space-y-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
          <span>در حال بارگذاری نقشه‌راه استراتژی...</span>
        </div>
      ) : strategies.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-white/10 bg-card p-12 text-center">
          <Compass className="h-12 w-12 text-amber-400/50 mb-3" />
          <h3 className="text-sm font-semibold text-white">
            هنوز استراتژی هوش مصنوعی برای این وب‌سایت ایجاد نشده است
          </h3>
          <p className="mt-1 text-xs text-muted-foreground max-w-md">
            موتور هوش مصنوعی با تجمیع داده‌های سرچ‌کنسول، وضعیت تکنیکال، توضیحات کسب‌وکار و مقالات موجود، یک نقشه راه اختصاصی تدوین می‌کند.
          </p>
          <button
            onClick={() => setShowOptionsModal(true)}
            disabled={generating}
            className="mt-4 inline-flex items-center gap-2 rounded-xl bg-amber-500 px-4 py-2.5 text-xs font-semibold text-white hover:bg-amber-600 transition"
          >
            <Sparkles className="h-4 w-4" />
            تنظیم و تولید اولین استراتژی سئو
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
                      <Cpu className="h-3 w-3 text-amber-400" />
                      موتور: {selectedStrategy.provider_used || "هوش مصنوعی چندمنبعی"}
                    </span>
                    <span className="text-[11px] text-muted-foreground">
                      تاریخ تدوین: {new Date(selectedStrategy.created_at).toLocaleDateString("fa-IR")}
                    </span>
                  </div>
                  <h2 className="text-base font-bold text-white">
                    {selectedStrategy.title}
                  </h2>
                  <p className="text-xs text-muted-foreground leading-relaxed max-w-4xl">
                    {selectedStrategy.executive_summary}
                  </p>
                  {selectedStrategy.target_audience && (
                    <div className="mt-3 inline-flex items-center gap-2 rounded-lg bg-white/5 px-3 py-1.5 text-[11px] text-muted-foreground border border-white/5">
                      <Target className="h-3.5 w-3.5 text-amber-400" />
                      <span>پرسونای مخاطبان هدف: {selectedStrategy.target_audience}</span>
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
                    className="rounded-2xl border border-white/10 bg-card p-5 shadow-xl space-y-4 hover:border-white/20 transition flex flex-col justify-between"
                  >
                    <div className="space-y-4">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="text-sm font-bold text-white">
                          {cluster.cluster_title}
                        </h3>
                        {getPriorityBadge(cluster.priority)}
                      </div>

                      <div className="rounded-xl bg-amber-500/5 border border-amber-500/10 p-3 space-y-1">
                        <span className="text-[11px] text-muted-foreground block">
                          صفحه ستون اصلی (Pillar Page):
                        </span>
                        <p className="text-sm font-bold text-amber-400">
                          {cluster.main_keyword}
                        </p>
                      </div>

                      <div className="space-y-2">
                        <span className="text-xs font-semibold text-white block">
                          مقالات خوشه‌ای اقماری (Cluster Articles):
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
                    </div>

                    <div className="pt-3 border-t border-white/5 flex items-center justify-between">
                      <span className="text-[11px] text-muted-foreground">
                        نیت سرچ کاربر:
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
                <div className="p-5 border-b border-white/10 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-white">
                      فرصت‌ها و شکاف‌های محتوایی بکر (Content Gaps)
                    </h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      موضوعات پرتقاضایی که سایت شما هنوز برای آن‌ها مقاله یا لندینگ‌پیج نساخته است.
                    </p>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-right text-xs">
                    <thead className="bg-white/5 text-muted-foreground">
                      <tr>
                        <th className="px-4 py-3 font-semibold">موضوع اصلی</th>
                        <th className="px-4 py-3 font-semibold">کلمه کلیدی هدف</th>
                        <th className="px-4 py-3 font-semibold">حجم جستجوی تخمینی</th>
                        <th className="px-4 py-3 font-semibold">سختی رقابت</th>
                        <th className="px-4 py-3 font-semibold">عنوان پیشنهادی سئوشده</th>
                        <th className="px-4 py-3 font-semibold text-center">اقدام سریع</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {selectedStrategy.content_gaps?.map((gap: any, idx: number) => {
                        const gapKey = `${gap.target_keyword}-${idx}`;
                        const isCreating = creatingBriefId === gapKey;
                        return (
                          <tr key={idx} className="hover:bg-white/[0.02] transition">
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
                              <div className="flex items-center justify-center gap-1.5">
                                <button
                                  onClick={() => handleCreateBriefFromGap(gap, idx)}
                                  disabled={isCreating}
                                  title="تبدیل مستقیم به بریف محتوایی و تولید مقاله"
                                  className="inline-flex items-center gap-1 rounded-lg bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 text-[11px] font-medium text-amber-400 hover:bg-amber-500/20 transition disabled:opacity-50"
                                >
                                  <PlusCircle className={`h-3 w-3 ${isCreating ? "animate-spin" : ""}`} />
                                  <span>{isCreating ? "در حال ساخت..." : "ساخت بریف"}</span>
                                </button>
                                <button
                                  onClick={() => handleCopy(gap.suggested_title)}
                                  className="inline-flex items-center gap-1 rounded-lg bg-white/5 px-2 py-1 text-[11px] font-medium text-muted-foreground hover:bg-white/10 hover:text-white transition"
                                >
                                  <Copy className="h-3 w-3" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
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
                        {item.task && item.task !== item.step && (
                          <p className="text-xs text-muted-foreground leading-relaxed mt-1">
                            {item.task}
                          </p>
                        )}
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

      {/* Generation Options Modal */}
      {showOptionsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-card p-6 shadow-2xl space-y-5">
            <div className="flex items-center gap-2 text-white">
              <SlidersHorizontal className="h-5 w-5 text-amber-400" />
              <h3 className="text-base font-bold">تنظیمات جهت‌گیری استراتژی سئو</h3>
            </div>

            <p className="text-xs text-muted-foreground leading-relaxed">
              مشخص کنید هوش مصنوعی روی کدام جنبه از سئوی وب‌سایت شما تمرکز ویژه‌تری داشته باشد:
            </p>

            <div className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-white">
                  محور و جهت‌گیری اصلی استراتژی (Focus Area)
                </label>
                <select
                  value={selectedFocusArea}
                  onChange={(e) => setSelectedFocusArea(e.target.value)}
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-xs text-white focus:border-amber-500 focus:outline-none"
                >
                  {FOCUS_AREAS.map((fa) => (
                    <option key={fa.id} value={fa.id}>
                      {fa.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-medium text-white">
                  ارائه‌دهنده هوش مصنوعی (AI Provider)
                </label>
                <select
                  value={selectedProvider}
                  onChange={(e) => setSelectedProvider(e.target.value)}
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-xs text-white focus:border-amber-500 focus:outline-none"
                >
                  {AI_PROVIDERS.map((pr) => (
                    <option key={pr.id} value={pr.id}>
                      {pr.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/10">
              <button
                type="button"
                onClick={() => setShowOptionsModal(false)}
                className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-white/5"
              >
                انصراف
              </button>
              <button
                type="button"
                onClick={handleGenerateStrategy}
                disabled={generating}
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-5 py-2 text-xs font-semibold text-white shadow-lg shadow-amber-500/20 hover:from-amber-600 hover:to-orange-700 disabled:opacity-50"
              >
                <Sparkles className="h-4 w-4" />
                <span>شروع تحلیل و تدوین نقشه راه</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
