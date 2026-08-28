'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import toast from 'react-hot-toast';
import { api } from '@/lib/api-client';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import {
  FileText,
  Plus,
  Sparkles,
  CheckCircle2,
  Clock,
  Send,
  Edit3,
  BookOpen,
  TrendingUp,
  AlertCircle,
  Trash2,
  X,
  ExternalLink,
  Layers,
} from 'lucide-react';

interface ContentBrief {
  id: string;
  title: string;
  target_keyword: string;
  search_intent: string;
  target_word_count: number;
  status: string;
  created_at: string;
}

interface ContentArticle {
  id: string;
  title: string;
  slug: string;
  seo_score: number;
  status: string;
  wp_post_id?: number;
  published_url?: string;
  created_at: string;
}

export default function ContentHubPage() {
  const params = useParams();
  const router = useRouter();
  const websiteId = params.id as string;

  const [activeTab, setActiveTab] = useState<'articles' | 'briefs'>('articles');
  const [articles, setArticles] = useState<ContentArticle[]>([]);
  const [briefs, setBriefs] = useState<ContentBrief[]>([]);
  const [loading, setLoading] = useState(true);
  // Distinguished from "genuinely empty": on a network/API failure the empty
  // state used to claim «هنوز مقاله‌ای تولید نشده است» while data existed.
  const [loadError, setLoadError] = useState<string | null>(null);

  // Modal states
  const [showArticleModal, setShowArticleModal] = useState(false);
  const [showBriefModal, setShowBriefModal] = useState(false);
  const [targetKeyword, setTargetKeyword] = useState('');
  const [customTitle, setCustomTitle] = useState('');
  const [submitting, setSubmitting] = useState(false);
  // Set when the article modal is opened from a brief card («تبدیل به مقاله»).
  // Without it the generated article was never linked back to its brief.
  const [activeBriefId, setActiveBriefId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  // The article awaiting confirmation in the custom dialog (replaces the
  // native window.confirm, which browsers rate-limit and cannot style).
  const [pendingDelete, setPendingDelete] = useState<ContentArticle | null>(null);
  const [pendingBriefDelete, setPendingBriefDelete] = useState<ContentBrief | null>(null);
  const [deletingBriefId, setDeletingBriefId] = useState<string | null>(null);

  const handleDeleteBrief = async () => {
    if (!pendingBriefDelete) return;
    const brief = pendingBriefDelete;
    setDeletingBriefId(brief.id);
    try {
      await api.delete(`/content/briefs/detail/${brief.id}`);
      toast.success('بریِف حذف شد.');
      setPendingBriefDelete(null);
      await fetchData();
    } catch (err) {
      console.error('Error deleting brief:', err);
      toast.error(err instanceof Error && 'message' in err ? err.message : 'حذف بریِف ناموفق بود.');
    } finally {
      setDeletingBriefId(null);
    }
  };

  const handleDeleteArticle = async () => {
    if (!pendingDelete) return;
    const art = pendingDelete;
    setDeletingId(art.id);
    try {
      await api.delete(`/content/articles/detail/${art.id}`);
      toast.success('مقاله حذف شد.');
      setPendingDelete(null);
      await fetchData();
    } catch (err) {
      console.error('Error deleting article:', err);
      toast.error('حذف مقاله ناموفق بود.');
    } finally {
      setDeletingId(null);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [websiteId]);

  const fetchData = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [artData, briefData] = await Promise.all([
        api.get(`/content/articles/${websiteId}`),
        api.get(`/content/briefs/${websiteId}`),
      ]);
      setArticles(artData || []);
      setBriefs(briefData || []);
    } catch (err) {
      console.error('Error loading content hub:', err);
      setLoadError('بارگذاری مرکز محتوا ناموفق بود. اتصال خود را بررسی کنید.');
    } finally {
      setLoading(false);
    }
  };

  const openArticleModal = (brief?: ContentBrief) => {
    setActiveBriefId(brief?.id ?? null);
    setTargetKeyword(brief?.target_keyword ?? '');
    setCustomTitle(brief?.title ?? '');
    setShowArticleModal(true);
  };

  const handleCreateBrief = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetKeyword) return;
    setSubmitting(true);
    try {
      await api.post(`/content/briefs/${websiteId}/generate`, {
        target_keyword: targetKeyword,
        title: customTitle || undefined,
        target_word_count: 1500,
        search_intent: 'informational',
      });
      toast.success('بریِف محتوایی تولید شد.');
      setShowBriefModal(false);
      setTargetKeyword('');
      setCustomTitle('');
      await fetchData();
      setActiveTab('briefs');
    } catch (err) {
      console.error('Error generating brief:', err);
      toast.error('تولید بریِف ناموفق بود. لطفا دوباره تلاش کنید.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateArticle = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetKeyword && !customTitle) return;
    setSubmitting(true);
    try {
      const newArt = await api.post(`/content/articles/${websiteId}/generate`, {
        target_keyword: targetKeyword || undefined,
        title: customTitle || undefined,
        brief_id: activeBriefId || undefined,
      });
      toast.success('مقاله با موفقیت نگارش شد.');
      setShowArticleModal(false);
      setTargetKeyword('');
      setCustomTitle('');
      setActiveBriefId(null);
      if (newArt && newArt.id) {
        router.push(`/websites/${websiteId}/content/${newArt.id}`);
      }
    } catch (err) {
      console.error('Error generating article:', err);
      // Surface the backend's own Persian detail (e.g. «ارتباط با سرور هوش
      // مصنوعی قطع است») instead of a blanket message that hides the cause.
      const backendMsg =
        err && typeof err === 'object' && 'message' in err && (err as Error).message;
      toast.error(
        typeof backendMsg === 'string' && backendMsg.length > 0
          ? backendMsg
          : 'نگارش مقاله ناموفق بود. اتصال و سهمیه هوش مصنوعی را بررسی کنید.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'published':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3.5 h-3.5" />
            منتشر شده در وردپرس
          </span>
        );
      case 'review':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Clock className="w-3.5 h-3.5" />
            آماده بررسی و ویرایش
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-500/10 text-slate-400 border border-slate-500/20">
            <FileText className="w-3.5 h-3.5" />
            پیش‌نویس اولیه
          </span>
        );
    }
  };

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-slate-900/60 p-6 rounded-2xl border border-slate-800 backdrop-blur-xl">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Sparkles className="w-7 h-7 text-indigo-400" />
            مرکز تولید محتوای هوشمند و پیلار پیج (AI Content Engine)
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            نگارش خودکار مقالات تخصصی سئو شده به زبان فارسی با ساختار H1/H2، چگالی استاندارد کلمه کلیدی و انتشار مستقیم در وردپرس
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowBriefModal(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium transition-all border border-slate-700"
          >
            <Layers className="w-4 h-4 text-indigo-400" />
            تولید بریِف محتوایی
          </button>
          <button
            onClick={() => openArticleModal()}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-sm font-medium transition-all shadow-lg shadow-indigo-600/20"
          >
            <Plus className="w-4 h-4" />
            نگارش مقاله جدید با AI
          </button>
        </div>
      </div>

      {/* Load failure banner — never masquerade as the empty state */}
      {loadError && (
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 justify-between bg-red-500/10 border border-red-500/30 rounded-2xl p-4">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
            <span className="text-sm text-red-300">{loadError}</span>
          </div>
          <button
            onClick={fetchData}
            className="px-4 py-2 rounded-xl bg-red-500/20 hover:bg-red-500/30 text-red-200 text-xs font-medium transition-all border border-red-500/30 shrink-0"
          >
            تلاش مجدد
          </button>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-800">
        <button
          onClick={() => setActiveTab('articles')}
          className={`flex items-center gap-2.5 px-6 py-3.5 text-sm font-medium border-b-2 transition-all ${
            activeTab === 'articles'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileText className="w-4 h-4" />
          مقالات تولید شده ({articles.length})
        </button>
        <button
          onClick={() => setActiveTab('briefs')}
          className={`flex items-center gap-2.5 px-6 py-3.5 text-sm font-medium border-b-2 transition-all ${
            activeTab === 'briefs'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <BookOpen className="w-4 h-4" />
          بریِف‌های محتوایی ({briefs.length})
        </button>
      </div>

      {/* Tab Content */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
        </div>
      ) : !loadError && activeTab === 'articles' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {articles.length === 0 ? (
            <div className="col-span-full bg-slate-900/40 border border-slate-800/80 rounded-2xl p-12 text-center">
              <Sparkles className="w-12 h-12 text-slate-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-white mb-2">هنوز مقاله‌ای تولید نشده است</h3>
              <p className="text-slate-400 text-sm max-w-md mx-auto mb-6">
                با کلیک بر روی دکمه «نگارش مقاله جدید با AI» اولین مقاله سئو شده خود را با ساختار کامل نگارش کنید.
              </p>
              <button
                onClick={() => openArticleModal()}
                className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-all"
              >
                نگارش اولین مقاله
              </button>
            </div>
          ) : (
            articles.map((art) => (
              <div
                key={art.id}
                onClick={() => router.push(`/websites/${websiteId}/content/${art.id}`)}
                className="group bg-slate-900/60 hover:bg-slate-900 border border-slate-800 hover:border-indigo-500/40 rounded-2xl p-6 transition-all cursor-pointer flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    {getStatusBadge(art.status)}
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                        امتیاز سئو: {art.seo_score}/۱۰۰
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setPendingDelete(art);
                        }}
                        disabled={deletingId === art.id}
                        title="حذف مقاله"
                        className="rounded-lg p-1.5 text-slate-500 transition-all hover:bg-red-500/15 hover:text-red-400 disabled:opacity-50"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                  <h3 className="text-base font-bold text-white group-hover:text-indigo-400 transition-colors line-clamp-2 mb-2">
                    {art.title}
                  </h3>
                  <p className="text-xs text-slate-400 font-mono mb-4 truncate">/{art.slug}</p>
                </div>

                <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                  <span>
                    تاریخ تولید:{" "}
                    {new Date(art.created_at).toLocaleString("fa-IR", {
                      year: "numeric",
                      month: "2-digit",
                      day: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                  <span className="flex items-center gap-1 text-indigo-400 font-medium">
                    مشاهده و ویرایش
                    <Edit3 className="w-3.5 h-3.5" />
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {briefs.length === 0 ? (
            <div className="col-span-full bg-slate-900/40 border border-slate-800/80 rounded-2xl p-12 text-center">
              <Layers className="w-12 h-12 text-slate-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-white mb-2">هیچ بریِفی ثبت نشده است</h3>
              <p className="text-slate-400 text-sm max-w-md mx-auto mb-6">
                با ایجاد بریِف محتوایی، ساختار تیترها و سوالات متداول را قبل از نگارش مقاله بهینه‌سازی کنید.
              </p>
              <button
                onClick={() => setShowBriefModal(true)}
                className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-all"
              >
                ایجاد اولین بریِف
              </button>
            </div>
          ) : (
            briefs.map((brief) => (
              <div
                key={brief.id}
                className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20">
                      کلمه هدف: {brief.target_keyword}
                    </span>
                    <span className="text-xs text-slate-400">
                      ~{brief.target_word_count} کلمه
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-white mb-3">{brief.title}</h3>
                  <p className="text-xs text-slate-400 mb-4">
                    نیت جستجو: {brief.search_intent === 'informational' ? 'آموزشی و اطلاعاتی' : 'خرید و تجاری'}
                  </p>
                </div>

                <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between">
                  <span className="text-xs text-slate-400">
                    {new Date(brief.created_at).toLocaleString("fa-IR", {
                      year: "numeric",
                      month: "2-digit",
                      day: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setPendingBriefDelete(brief)}
                      disabled={deletingBriefId === brief.id}
                      title="حذف بریِف"
                      className="rounded-lg p-1.5 text-slate-500 transition-all hover:bg-red-500/15 hover:text-red-400 disabled:opacity-50"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => openArticleModal(brief)}
                      className="px-3.5 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-400 border border-indigo-500/20 text-xs font-medium transition-all"
                    >
                      تبدیل به مقاله
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Modal - Create Article */}
      {showArticleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 w-full max-w-md space-y-5">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-indigo-400" />
                نگارش مقاله هوشمند با AI
              </h3>
              <button
                onClick={() => { setShowArticleModal(false); setActiveBriefId(null); }}
                className="text-slate-400 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateArticle} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  کلمه کلیدی اصلی / هدف مقاله
                </label>
                <input
                  type="text"
                  value={targetKeyword}
                  onChange={(e) => setTargetKeyword(e.target.value)}
                  placeholder="مثال: سئو وب‌سایت در سال ۲۰۲۶"
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  عنوان دلخواه مقاله (اختیاری)
                </label>
                <input
                  type="text"
                  value={customTitle}
                  onChange={(e) => setCustomTitle(e.target.value)}
                  placeholder="در صورت خالی بودن توسط AI انتخاب می‌شود..."
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="pt-3 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => { setShowArticleModal(false); setActiveBriefId(null); }}
                  className="px-4 py-2 rounded-xl text-slate-400 hover:text-white text-sm"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={submitting || (!targetKeyword && !customTitle)}
                  className="px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium transition-all"
                >
                  {submitting ? 'در حال نگارش و تحلیل...' : 'شروع نگارش مقاله'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal - Create Brief */}
      {showBriefModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 w-full max-w-md space-y-5">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Layers className="w-5 h-5 text-purple-400" />
                تولید ساختار و بریِف محتوا
              </h3>
              <button
                onClick={() => setShowBriefModal(false)}
                className="text-slate-400 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateBrief} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  کلمه کلیدی هدف
                </label>
                <input
                  type="text"
                  value={targetKeyword}
                  onChange={(e) => setTargetKeyword(e.target.value)}
                  placeholder="مثال: آموزش سئو تکنیکال"
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  عنوان پیشنهادی بریِف (اختیاری)
                </label>
                <input
                  type="text"
                  value={customTitle}
                  onChange={(e) => setCustomTitle(e.target.value)}
                  placeholder="در صورت خالی بودن به طور خودکار تعیین می‌شود..."
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="pt-3 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowBriefModal(false)}
                  className="px-4 py-2 rounded-xl text-slate-400 hover:text-white text-sm"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={submitting || !targetKeyword}
                  className="px-6 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-sm font-medium transition-all"
                >
                  {submitting ? 'در حال تولید ساختار...' : 'تولید بریِف'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {/* Delete confirmation — article */}
      <ConfirmDialog
        isOpen={!!pendingDelete}
        title="حذف مقاله"
        description={
          pendingDelete
            ? `مقاله «${pendingDelete.title}» حذف شود؟ این عمل بازگشت‌پذیر نیست.`
            : ""
        }
        confirmLabel="حذف کن"
        loading={deletingId !== null}
        onConfirm={handleDeleteArticle}
        onClose={() => setPendingDelete(null)}
      />

      {/* Delete confirmation — brief */}
      <ConfirmDialog
        isOpen={!!pendingBriefDelete}
        title="حذف بریِف محتوایی"
        description={
          pendingBriefDelete
            ? `بریِف «${pendingBriefDelete.title}» حذف شود؟ مقاله‌هایی که قبلاً از آن ساخته شده‌اند سر جایشان می‌مانند.`
            : ""
        }
        confirmLabel="حذف کن"
        loading={deletingBriefId !== null}
        onConfirm={handleDeleteBrief}
        onClose={() => setPendingBriefDelete(null)}
      />
    </div>
  );
}
