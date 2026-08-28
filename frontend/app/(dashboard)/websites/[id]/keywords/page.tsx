"use client";

import { StyledSelect } from "@/components/StyledSelect";
import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api-client";
import {
  KeyRound,
  Plus,
  Trash2,
  TrendingUp,
  Search,
  Tag,
  Target,
  ExternalLink,
  AlertTriangle,
  LineChart as LineChartIcon,
} from "lucide-react";
import toast from "react-hot-toast";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export default function WebsiteKeywordsPage() {
  const params = useParams();
  const websiteId = params.id as string;

  const [keywords, setKeywords] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Form
  const [keywordText, setKeywordText] = useState("");
  const [searchVolume, setSearchVolume] = useState<number>(1000);
  const [difficulty, setDifficulty] = useState<number>(35);
  const [targetUrl, setTargetUrl] = useState("");
  const [intent, setIntent] = useState("informational");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Delete modal
  const [deleteModal, setDeleteModal] = useState<{ open: boolean; item: any; loading: boolean }>({
    open: false,
    item: null,
    loading: false,
  });

  // Rankings modal
  const [rankingsModal, setRankingsModal] = useState<{ open: boolean; item: any; data: any[]; loading: boolean }>({
    open: false,
    item: null,
    data: [],
    loading: false,
  });

  useEffect(() => {
    loadKeywords();
  }, [websiteId]);

  const loadKeywords = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/keywords/${websiteId}`);
      setKeywords(res || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const handleAddKeyword = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await api.post(`/keywords?website_id=${websiteId}`, {
        keyword: keywordText,
        search_volume: Number(searchVolume),
        difficulty: Number(difficulty),
        target_page_url: targetUrl || null,
        intent: intent,
        tags: ["سئو", "اصلی"],
      });
      setIsModalOpen(false);
      setKeywordText("");
      setTargetUrl("");
      await loadKeywords();
      toast.success("کلمه کلیدی هدف با موفقیت اضافه شد");
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("خطا در افزودن کلمه کلیدی");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const submitDeleteKeyword = async () => {
    if (!deleteModal.item) return;
    setDeleteModal((prev) => ({ ...prev, loading: true }));
    try {
      await api.delete(`/keywords/${deleteModal.item.id}`);
      await loadKeywords();
      toast.success("کلمه کلیدی با موفقیت حذف شد");
      setDeleteModal({ open: false, item: null, loading: false });
    } catch (err: any) {
      toast.error(err.message || "خطا در حذف کلمه کلیدی");
      setDeleteModal((prev) => ({ ...prev, loading: false }));
    }
  };

  const openRankingsModal = async (keyword: any) => {
    setRankingsModal({ open: true, item: keyword, data: [], loading: true });
    try {
      const res = await api.get(`/keywords/${keyword.id}/rankings`);
      // Only use the real data returned from the API
      let data = res || [];
      setRankingsModal({ open: true, item: keyword, data, loading: false });
    } catch {
      toast.error("خطا در دریافت تاریخچه رتبه");
      setRankingsModal({ open: false, item: null, data: [], loading: false });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-lg font-bold text-white">
            مدیریت کلمات کلیدی هدف (Target Keywords Manager)
          </h2>
          <p className="text-xs text-muted-foreground">
            پایش رتبه‌ها، سختی کلمات، حجم جستجو و تخصیص به صفحات هدف در سایت
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-xs font-semibold text-primary-foreground shadow-lg shadow-primary/20 hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          <span>افزودن کلمه کلیدی هدف</span>
        </button>
      </div>

      {/* Keywords Table */}
      <div className="rounded-2xl border border-white/10 bg-card/60 p-6 shadow-xl backdrop-blur-md">
        {loading ? (
          <div className="py-12 text-center text-xs text-muted-foreground">
            در حال بارگذاری کلمات کلیدی...
          </div>
        ) : keywords.length === 0 ? (
          <div className="py-12 text-center text-xs text-muted-foreground">
            هنوز کلمه کلیدی هدف ثبت نشده است. روی «افزودن کلمه کلیدی هدف» کلیک کنید.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-white/10 text-muted-foreground">
                <tr>
                  <th className="pb-3 text-right">کلمه کلیدی هدف</th>
                  <th className="pb-3 text-right">قصد جستجو (Intent)</th>
                  <th className="pb-3 text-right">حجم جستجو (Volume)</th>
                  <th className="pb-3 text-right">سختی (KD %)</th>
                  <th className="pb-3 text-right">صفحه هدف (Target URL)</th>
                  <th className="pb-3 text-right">آخرین رتبه</th>
                  <th className="pb-3 text-right">بهترین رتبه</th>
                  <th className="pb-3 text-center">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {keywords.map((k) => (
                  <tr key={k.id} className="transition hover:bg-white/5">
                    <td className="py-3.5 text-right font-bold text-white">
                      {k.keyword}
                    </td>
                    <td className="py-3.5 text-right">
                      <span className="rounded-lg bg-blue-500/15 px-2.5 py-1 text-[11px] font-medium text-blue-400">
                        {k.intent === "informational"
                          ? "آموزشی / اطلاعاتی"
                          : k.intent === "commercial"
                          ? "تجاری / مقایسه‌ای"
                          : k.intent === "transactional"
                          ? "خرید / تراکنش"
                          : k.intent}
                      </span>
                    </td>
                    <td className="py-3.5 text-right font-medium text-white">
                      {k.search_volume ? k.search_volume.toLocaleString() : "---"}
                    </td>
                    <td className="py-3.5 text-right">
                      <span
                        className={`rounded-full px-2.5 py-1 font-semibold ${
                          k.difficulty && k.difficulty > 60
                            ? "bg-red-500/15 text-red-400"
                            : k.difficulty && k.difficulty > 30
                            ? "bg-amber-500/15 text-amber-400"
                            : "bg-emerald-500/15 text-emerald-400"
                        }`}
                      >
                        {k.difficulty || 0}%
                      </span>
                    </td>
                    <td className="py-3.5 text-right text-muted-foreground" dir="ltr">
                      {k.target_page_url ? (
                        <span className="inline-flex items-center gap-1 text-blue-400">
                          <span>{k.target_page_url}</span>
                        </span>
                      ) : (
                        "---"
                      )}
                    </td>
                    <td className="py-3.5 text-right">
                      {k.last_position ? (
                        <span className="rounded-full bg-emerald-500/15 px-2.5 py-1 font-bold text-emerald-400">
                          {k.last_position}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">محاسبه نشده</span>
                      )}
                    </td>
                    <td className="py-3.5 text-right">
                      {k.best_position ? (
                        <span className="rounded-full bg-purple-500/15 px-2.5 py-1 font-bold text-purple-400">
                          {k.best_position}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">---</span>
                      )}
                    </td>
                    <td className="py-3.5 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <button
                          onClick={() => openRankingsModal(k)}
                          className="rounded-lg p-1.5 text-muted-foreground transition hover:bg-blue-500/20 hover:text-blue-400"
                          title="نمودار رتبه"
                        >
                          <LineChartIcon className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => setDeleteModal({ open: true, item: k, loading: false })}
                          className="rounded-lg p-1.5 text-muted-foreground transition hover:bg-red-500/20 hover:text-red-400"
                          title="حذف کلمه کلیدی"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Keyword Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-card p-6 shadow-2xl">
            <h3 className="text-base font-bold text-white">
              افزودن کلمه کلیدی هدف جدید
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              مشخصات کلمه کلیدی و هدف‌گذاری سئو را وارد کنید.
            </p>

            <form onSubmit={handleAddKeyword} className="mt-5 space-y-4">
              {error && (
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-400">
                  {error}
                </div>
              )}

              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  کلمه کلیدی
                </label>
                <input
                  type="text"
                  required
                  value={keywordText}
                  onChange={(e) => setKeywordText(e.target.value)}
                  placeholder="مثلاً: آموزش سئو سایت"
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-xs text-white placeholder-muted-foreground focus:border-primary focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">
                    حجم جستجوی ماهانه (تخمینی)
                  </label>
                  <input
                    type="number"
                    value={searchVolume}
                    onChange={(e) => setSearchVolume(Number(e.target.value))}
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-xs text-white placeholder-muted-foreground focus:border-primary focus:outline-none"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">
                    سختی کلمه (KD 0-100)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={difficulty}
                    onChange={(e) => setDifficulty(Number(e.target.value))}
                    className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-xs text-white placeholder-muted-foreground focus:border-primary focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  قصد جستجو (Search Intent)
                </label>
                <StyledSelect
                  value={intent}
                  onChange={setIntent}
                  options={[
                    { value: "informational", label: "آموزشی / اطلاعاتی (Informational)" },
                    { value: "commercial", label: "مقایسه‌ای / تجاری (Commercial)" },
                    { value: "transactional", label: "خرید / اقدام (Transactional)" },
                  ]}
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  آدرس صفحه هدف (Target URL - اختیاری)
                </label>
                <input
                  type="text"
                  value={targetUrl}
                  onChange={(e) => setTargetUrl(e.target.value)}
                  placeholder="/blog/what-is-seo"
                  className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-xs text-white placeholder-muted-foreground focus:border-primary focus:outline-none"
                  dir="ltr"
                />
              </div>

              <div className="mt-6 flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="rounded-xl px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-white/5 hover:text-white"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="rounded-xl bg-primary px-5 py-2 text-xs font-semibold text-primary-foreground shadow-lg shadow-primary/20 hover:bg-primary/90 disabled:opacity-50"
                >
                  {submitting ? "در حال ثبت..." : "ذخیره کلمه کلیدی"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Keyword Confirm Modal */}
      {deleteModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-red-500/30 bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-red-400">
              <AlertTriangle className="h-6 w-6 shrink-0" />
              <h3 className="text-base font-bold text-white">حذف کلمه کلیدی</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              آیا از حذف کلمه کلیدی «{deleteModal.item?.keyword}» اطمینان دارید؟
            </p>
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setDeleteModal({ open: false, item: null, loading: false })}
                className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-white/5"
              >
                انصراف
              </button>
              <button
                type="button"
                onClick={submitDeleteKeyword}
                disabled={deleteModal.loading}
                className="rounded-xl bg-red-500 px-4 py-2 text-xs font-bold text-white shadow-lg shadow-red-500/20 hover:bg-red-600 disabled:opacity-50"
              >
                {deleteModal.loading ? "در حال حذف..." : "بله، حذف کن"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rankings Chart Modal */}
      {rankingsModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-2xl rounded-2xl border border-white/10 bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-blue-400">
              <LineChartIcon className="h-6 w-6 shrink-0" />
              <h3 className="text-base font-bold text-white">تاریخچه رتبه: {rankingsModal.item?.keyword}</h3>
            </div>
            
            <div className="h-64 w-full mt-4">
              {rankingsModal.loading ? (
                <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                  در حال دریافت اطلاعات...
                </div>
              ) : rankingsModal.data.length === 0 ? (
                <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                  رتبه‌ای برای این کلمه ثبت نشده است.
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={rankingsModal.data}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                    <XAxis 
                      dataKey="check_date" 
                      stroke="#ffffff50" 
                      fontSize={11} 
                      tickFormatter={(val) => new Date(val).toLocaleDateString('fa-IR')}
                    />
                    <YAxis 
                      reversed 
                      stroke="#ffffff50" 
                      fontSize={11} 
                      domain={[1, 'dataMax']}
                    />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#ffffff20', borderRadius: '8px', fontSize: '12px' }}
                      itemStyle={{ color: '#fff' }}
                      labelFormatter={(label) => new Date(label as string).toLocaleDateString('fa-IR')}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="position" 
                      stroke="#3b82f6" 
                      strokeWidth={3}
                      activeDot={{ r: 6 }} 
                      name="رتبه (Position)"
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-4">
              <button
                type="button"
                onClick={() => setRankingsModal({ open: false, item: null, data: [], loading: false })}
                className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-white/5"
              >
                بستن
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
