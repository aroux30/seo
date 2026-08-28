'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import toast from 'react-hot-toast';
import { api, ApiError } from '@/lib/api-client';
import { sanitizeHtml } from '@/lib/sanitize-html';
import {
  ArrowRight,
  Save,
  Send,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  FileText,
  Eye,
  Code,
  ExternalLink,
  Globe,
  Share2,
  History,
  Wand2,
  X,
  RefreshCw,
  Layers,
  Link2,
  HelpCircle,
} from 'lucide-react';
import { VersionHistoryPanel } from '@/components/VersionHistoryPanel';

// Shape written by backend `score_article_detailed()`. The previous
// `{label, status}` shape this file expected was never produced by the API, so
// the checklist always rendered empty.
interface ScoreCheck {
  name: string;
  passed: boolean;
  points: number;
  detail: string;
}

interface ScoreBreakdown {
  score: number;
  word_count: number;
  keyword_density: number;
  checks: ScoreCheck[];
}

interface ArticleDetail {
  id: string;
  title: string;
  slug: string;
  content_markdown: string;
  content_html: string;
  seo_score: number;
  seo_metadata: {
    target_keyword?: string;
    score_breakdown?: ScoreBreakdown;
  };
  status: string;
  wp_post_id?: number;
  published_url?: string;
  created_at: string;
}

// Keys mirror `add(...)` calls in backend/app/core/seo_score.py exactly. The
// previous keys (length_min, has_h2, …) belonged to an older scorer that no
// longer exists, so every checklist item fell back to its raw English name.
const CHECK_LABELS: Record<string, string> = {
  basic_title: 'کلمه کلیدی در عنوان سئو',
  basic_meta: 'کلمه کلیدی در توضیحات متا',
  basic_url: 'کلمه کلیدی در URL/اسلاگ',
  basic_first_10: 'کلمه کلیدی در ۱۰٪ ابتدای محتوا',
  basic_content: 'کلمه کلیدی در متن محتوا',
  basic_length: 'طول کافی محتوا (۶۰۰+ کلمه)',
  additional_subheading: 'کلمه کلیدی در زیرعنوان‌ها (H2-H4)',
  additional_image_alt: 'تصویر با alt حاوی کلمه کلیدی',
  additional_density: 'چگالی کلمه کلیدی در محدوده مجاز',
  additional_external_links: 'لینک به منابع خارجی',
  additional_internal_links: 'لینک‌سازی داخلی در محتوا',
  title_beginning: 'کلمه کلیدی در ابتدای عنوان',
  title_number: 'استفاده از عدد در عنوان',
  content_toc: 'ساختار بخش‌بندی (حداقل دو H2)',
  content_media: 'وجود تصویر یا ویدیو در محتوا',
};

// The score card used to read "عالی! ... کاملاً بهینه است" unconditionally, so a
// 30/100 article was still congratulated. Colour and wording now follow the
// number. Tailwind classes are written out in full rather than interpolated,
// because the JIT compiler only sees literal class strings.
function scoreVerdict(score: number): {
  text: string;
  className: string;
  ringClassName: string;
} {
  if (score >= 80) {
    return {
      text: 'عالی! ساختار محتوا و کلمات کلیدی بهینه است.',
      className: 'text-emerald-400',
      ringClassName: 'border-emerald-500',
    };
  }
  if (score >= 60) {
    return {
      text: 'قابل قبول، اما جای بهبود دارد.',
      className: 'text-amber-400',
      ringClassName: 'border-amber-500',
    };
  }
  return {
    text: 'نیاز به بهبود دارد. چک‌لیست زیر را بررسی کنید.',
    className: 'text-rose-400',
    ringClassName: 'border-rose-500',
  };
}

export default function ArticleEditorPage() {
  const params = useParams();
  const router = useRouter();
  const websiteId = params.id as string;
  const articleId = params.articleId as string;

  const [article, setArticle] = useState<ArticleDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);

  const [editTitle, setEditTitle] = useState('');
  const [editMarkdown, setEditMarkdown] = useState('');
  const [viewMode, setViewMode] = useState<'preview' | 'markdown'>('preview');
  const [showHistory, setShowHistory] = useState(false);
  const [showAiModal, setShowAiModal] = useState(false);
  const [refining, setRefining] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [selectedPreset, setSelectedPreset] = useState<string>('auto_fix_100');

  useEffect(() => {
    fetchArticle();
  }, [articleId]);

  const handleAiRefine = async (instructionText?: string, modeKey?: string) => {
    if (!article) return;
    const finalInstruction = (instructionText || aiPrompt).trim();
    if (!finalInstruction) {
      toast.error('لطفاً یک دستور برای هوش مصنوعی وارد کنید.');
      return;
    }
    setRefining(true);
    try {
      const updated = await api.post<ArticleDetail>(
        `/content/articles/detail/${articleId}/refine`,
        {
          instruction: finalInstruction,
          mode: modeKey || selectedPreset,
        }
      );
      setArticle(updated);
      setEditTitle(updated.title);
      setEditMarkdown(updated.content_markdown);
      setShowAiModal(false);
      setAiPrompt('');
      toast.success('مقاله با موفقیت توسط هوش مصنوعی ارتقا یافت و در تاریخچه ثبت شد!');
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'خطا در بازنویسی مقاله با هوش مصنوعی.');
    } finally {
      setRefining(false);
    }
  };

  // All three handlers go through the shared `api` client rather than raw fetch.
  // It resolves the API base from NEXT_PUBLIC_API_URL (so this page works off
  // localhost), reads the correct `access_token` key, sends the
  // X-Organization-Id header the backend's org guards require, and refreshes an
  // expired token instead of silently rendering an empty page.
  const fetchArticle = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await api.get<ArticleDetail>(`/content/articles/detail/${articleId}`);
      setArticle(data);
      setEditTitle(data.title);
      setEditMarkdown(data.content_markdown);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : 'خطا در دریافت مقاله. اتصال خود را بررسی کنید.';
      setLoadError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!article) return;
    setSaving(true);
    try {
      const updated = await api.patch<ArticleDetail>(`/content/articles/detail/${articleId}`, {
        title: editTitle,
        content_markdown: editMarkdown,
      });
      setArticle(updated);
      setEditTitle(updated.title);
      setEditMarkdown(updated.content_markdown);
      toast.success('تغییرات ذخیره شد.');
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'ذخیره تغییرات ناموفق بود.');
    } finally {
      setSaving(false);
    }
  };

  const handlePublishToWordPress = async (postStatus: 'draft' | 'publish') => {
    if (!article) return;
    setPublishing(true);
    try {
      const updated = await api.post<ArticleDetail>(
        `/content/articles/detail/${articleId}/publish`,
        { post_status: postStatus }
      );
      setArticle(updated);
      toast.success(
        postStatus === 'publish' ? 'مقاله در وردپرس منتشر شد.' : 'مقاله به عنوان پیش‌نویس ارسال شد.'
      );
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'انتشار در وردپرس ناموفق بود.');
    } finally {
      setPublishing(false);
    }
  };

  // Articles stored before the backend started sanitizing on write may still hold
  // a hostile payload, so strip again here. Declared above the early returns
  // below: a hook placed after a conditional return changes the hook order
  // between renders, which React rejects. Memoized so typing in the markdown
  // pane does not re-sanitize the whole body on every keystroke.
  const safeHtml = useMemo(
    () => sanitizeHtml(article?.content_html || ''),
    [article?.content_html]
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24" dir="rtl">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
      </div>
    );
  }

  if (!article) {
    return (
      <div className="p-12 text-center space-y-4" dir="rtl">
        <p className="text-white">{loadError || 'مقاله یافت نشد.'}</p>
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={fetchArticle}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors"
          >
            تلاش مجدد
          </button>
          <button
            onClick={() => router.push(`/websites/${websiteId}/content`)}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium transition-colors"
          >
            بازگشت به فهرست مقالات
          </button>
        </div>
      </div>
    );
  }

  const breakdown = article.seo_metadata?.score_breakdown;
  const checks = breakdown?.checks || [];
  const verdict = scoreVerdict(article.seo_score);

  return (
    <div className="space-y-6" dir="rtl">
      {/* Top Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-slate-900/60 p-5 rounded-2xl border border-slate-800 backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push(`/websites/${websiteId}/content`)}
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
          >
            <ArrowRight className="w-5 h-5" />
          </button>
          <div>
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              className="text-lg font-bold text-white bg-transparent border-b border-transparent hover:border-slate-700 focus:border-indigo-500 focus:outline-none w-full md:w-96"
            />
            <p className="text-xs text-slate-400 font-mono mt-0.5">/{article.slug}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowAiModal(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-sm font-medium transition-all shadow-lg shadow-purple-600/25 border border-purple-400/30"
          >
            <Sparkles className="w-4 h-4 text-purple-200 animate-pulse" />
            بهبود هوشمند با AI
          </button>

          <button
            onClick={() => setShowHistory(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium border border-slate-700 transition-all"
          >
            <History className="w-4 h-4 text-slate-400" />
            تاریخچه نسخه‌ها
          </button>

          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium border border-slate-700 transition-all"
          >
            <Save className="w-4 h-4 text-indigo-400" />
            {saving ? 'در حال ذخیره...' : 'ذخیره تغییرات'}
          </button>

          <button
            onClick={() => handlePublishToWordPress('publish')}
            disabled={publishing}
            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-sm font-medium transition-all shadow-lg shadow-emerald-600/20"
          >
            <Send className="w-4 h-4" />
            {publishing ? 'در حال انتشار...' : 'انتشار در وردپرس'}
          </button>
        </div>
      </div>

      {/* Main Grid: Content Editor + SEO Health Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Main Editor/Preview area - 3 columns */}
        <div className="lg:col-span-3 space-y-4">
          <div className="flex items-center justify-between bg-slate-900/60 border border-slate-800 rounded-xl px-4 py-2.5">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setViewMode('preview')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  viewMode === 'preview'
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Eye className="w-3.5 h-3.5" />
                پیش‌نمایش متن مقاله
              </button>
              <button
                onClick={() => setViewMode('markdown')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  viewMode === 'markdown'
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Code className="w-3.5 h-3.5" />
                ویرایش سورس Markdown
              </button>
            </div>
            <span className="text-xs text-slate-400">
              تعداد کلمات: {breakdown ? breakdown.word_count : '—'}
            </span>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 min-h-[600px]">
            {viewMode === 'preview' ? (
              <div
                className="prose prose-invert prose-indigo max-w-none text-slate-200 leading-relaxed space-y-4"
                dangerouslySetInnerHTML={{ __html: safeHtml }}
              />
            ) : (
              <textarea
                value={editMarkdown}
                onChange={(e) => setEditMarkdown(e.target.value)}
                className="w-full h-[600px] bg-slate-950 border border-slate-800 rounded-xl p-4 text-slate-200 font-mono text-sm leading-relaxed focus:outline-none focus:border-indigo-500"
              />
            )}
          </div>
        </div>

        {/* Sidebar - SEO Health Score & WordPress info */}
        <div className="space-y-6">
          {/* Overall Score Card */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 text-center">
            <h3 className="text-xs font-medium text-slate-400 mb-3">امتیاز سلامت سئو مقاله</h3>
            <div className={`inline-flex items-center justify-center w-24 h-24 rounded-full bg-slate-800/60 border-4 text-3xl font-black mb-3 ${verdict.ringClassName} ${verdict.className}`}>
              {article.seo_score}
              <span className="text-xs font-normal text-slate-400">/۱۰۰</span>
            </div>
            <p className={`text-xs font-medium ${verdict.className}`}>{verdict.text}</p>
          </div>

          {/* Key Metrics Breakdown */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3">
            <h4 className="text-sm font-bold text-white flex items-center gap-2 mb-3">
              <Sparkles className="w-4 h-4 text-indigo-400" />
              متریک‌های کلیدی محتوا
            </h4>
            {/* Every value below comes from the backend's score breakdown. The
                previous hardcoded fallbacks (1650 words, 1.8% density, 4 H2s,
                90 readability) rendered for every article regardless of its
                real content, so the panel looked populated even when nothing
                had been measured. An em dash is honest about missing data. */}
            <div className="flex items-center justify-between text-xs py-1.5 border-b border-slate-800/80">
              <span className="text-slate-400">تعداد کلمات کل:</span>
              <span className="text-white font-mono font-medium">
                {breakdown ? breakdown.word_count : '—'}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs py-1.5 border-b border-slate-800/80">
              <span className="text-slate-400">چگالی کلمه کلیدی:</span>
              <span className="text-emerald-400 font-mono font-medium">
                {breakdown ? `${breakdown.keyword_density}٪` : '—'}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs py-1.5 border-b border-slate-800/80">
              <span className="text-slate-400">کلمه کلیدی هدف:</span>
              <span className="text-white font-medium">
                {article.seo_metadata?.target_keyword || '—'}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs py-1.5">
              <span className="text-slate-400">چک‌های موفق:</span>
              <span className="text-white font-mono font-medium">
                {checks.length ? `${checks.filter((c) => c.passed).length}/${checks.length}` : '—'}
              </span>
            </div>
          </div>

          {/* SEO Checklist */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3">
            <h4 className="text-sm font-bold text-white mb-2">چک‌لیست استانداردهای سئو</h4>
            {checks.length === 0 && (
              <p className="text-xs text-slate-400 leading-relaxed">
                امتیاز این مقاله هنوز محاسبه نشده است. با ذخیره تغییرات، چک‌لیست به‌روز می‌شود.
              </p>
            )}
            {checks.map((chk) => (
              <div key={chk.name} className="flex items-start gap-2.5 text-xs text-slate-300">
                {chk.passed ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                )}
                <div className="min-w-0">
                  <span>{CHECK_LABELS[chk.name] || chk.name}</span>
                  {chk.detail && <p className="text-slate-500 mt-0.5">{chk.detail}</p>}
                </div>
              </div>
            ))}
          </div>

          {/* WordPress Status Card */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-4">
            <h4 className="text-sm font-bold text-white flex items-center gap-2">
              <Globe className="w-4 h-4 text-emerald-400" />
              وضعیت انتشار در وردپرس
            </h4>

            {article.wp_post_id ? (
              <div className="space-y-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-3 text-xs">
                <div className="flex items-center justify-between text-emerald-300">
                  <span>شناسه پست وردپرس:</span>
                  <span className="font-mono">#{article.wp_post_id}</span>
                </div>
                {article.published_url && (
                  <a
                    href={article.published_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 text-indigo-400 hover:underline pt-1 border-t border-emerald-500/20"
                  >
                    مشاهده در وب‌سایت
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            ) : (
              <p className="text-xs text-slate-400 leading-relaxed">
                این مقاله هنوز در وردپرس منتشر نشده است. با کلیک بر روی دکمه انتشار، مستقیماً از طریق REST API به سایت ارسال می‌شود.
              </p>
            )}

            <button
              onClick={() => handlePublishToWordPress('draft')}
              disabled={publishing}
              className="w-full py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-all"
            >
              ارسال به وردپرس به عنوان پیش‌نویس (Draft)
            </button>
          </div>
        </div>
      </div>

      {/* AI Refine Modal */}
      {showAiModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-xl p-6 space-y-6 shadow-2xl shadow-purple-950/50 relative">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-2xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">دستیار بهبود هوشمند با هوش مصنوعی</h3>
                  <p className="text-xs text-slate-400">اصلاح، بازنویسی و رساندن نمره سئوی مقاله به ۱۰۰٪</p>
                </div>
              </div>
              <button
                onClick={() => setShowAiModal(false)}
                disabled={refining}
                className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Quick Action Presets */}
            <div className="space-y-2.5">
              <label className="text-xs font-semibold text-slate-300">انتخاب سناریوی بهینه‌سازی سریع:</label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setSelectedPreset('auto_fix_100');
                    setAiPrompt('نمره سئو را به ۱۰۰ برسان: لینک‌های داخلی و خارجی معتبر اضافه کن، عنوان را سئو کن و کلمه کلیدی را در بخش‌های اصلی بهینه کن.');
                  }}
                  className={`p-3 rounded-2xl border text-right transition-all flex items-start gap-2.5 ${
                    selectedPreset === 'auto_fix_100'
                      ? 'bg-purple-600/15 border-purple-500/40 text-purple-200'
                      : 'bg-slate-800/40 border-slate-800 hover:border-slate-700 text-slate-300'
                  }`}
                >
                  <Wand2 className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-bold">ارتقای سئو به ۱۰۰٪</p>
                    <p className="text-[11px] text-slate-400 mt-0.5">رفع خطاهای لینک‌سازی و ساختار</p>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setSelectedPreset('expand');
                    setAiPrompt('حجم مقاله را گسترش بده: مثال‌های واقعی، بررسی دقیق‌تر جزئیات و ۲ زیرعنوان جدید به محتوا اضافه کن.');
                  }}
                  className={`p-3 rounded-2xl border text-right transition-all flex items-start gap-2.5 ${
                    selectedPreset === 'expand'
                      ? 'bg-purple-600/15 border-purple-500/40 text-purple-200'
                      : 'bg-slate-800/40 border-slate-800 hover:border-slate-700 text-slate-300'
                  }`}
                >
                  <Layers className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-bold">افزایش عمق و حجم</p>
                    <p className="text-[11px] text-slate-400 mt-0.5">توسعه سرفصل‌ها و توضیحات تکمیلی</p>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setSelectedPreset('links');
                    setAiPrompt('لینک‌سازی داخلی و خارجی را تقویت کن: ۲ لینک خارجی معتبر علمی و ۲ لینک داخلی به مقالات مرتبط اضافه کن.');
                  }}
                  className={`p-3 rounded-2xl border text-right transition-all flex items-start gap-2.5 ${
                    selectedPreset === 'links'
                      ? 'bg-purple-600/15 border-purple-500/40 text-purple-200'
                      : 'bg-slate-800/40 border-slate-800 hover:border-slate-700 text-slate-300'
                  }`}
                >
                  <Link2 className="w-4 h-4 text-teal-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-bold">تقویت لینک‌سازی</p>
                    <p className="text-[11px] text-slate-400 mt-0.5">تزریق مراجع خارجی و داخلی</p>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setSelectedPreset('faq');
                    setAiPrompt('یک بخش سوالات متداول (FAQ) حرفه‌ای با حداقل ۴ سوال پرتکرار و پاسخ‌های کاربردی به مقاله اضافه کن.');
                  }}
                  className={`p-3 rounded-2xl border text-right transition-all flex items-start gap-2.5 ${
                    selectedPreset === 'faq'
                      ? 'bg-purple-600/15 border-purple-500/40 text-purple-200'
                      : 'bg-slate-800/40 border-slate-800 hover:border-slate-700 text-slate-300'
                  }`}
                >
                  <HelpCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-bold">تکمیل بخش FAQ</p>
                    <p className="text-[11px] text-slate-400 mt-0.5">پاسخ‌های آماده برای فیچر اسنیپت</p>
                  </div>
                </button>
              </div>
            </div>

            {/* Custom Instruction Box */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300">یا متن دستور اختصاصی خود را بنویسید:</label>
              <textarea
                rows={3}
                value={aiPrompt}
                onChange={(e) => setAiPrompt(e.target.value)}
                placeholder="مثلاً: بخش نتیجه‌گیری را جذاب‌تر کن، مثال‌های عددی بیاور و نمره سئو را به حداکثر برسان..."
                className="w-full rounded-2xl bg-slate-950 border border-slate-800 p-3.5 text-xs text-white placeholder-slate-500 focus:border-purple-500 focus:outline-none resize-none leading-relaxed"
              />
            </div>

            {/* Actions */}
            <div className="flex items-center justify-between pt-2">
              <button
                type="button"
                onClick={() => setShowAiModal(false)}
                disabled={refining}
                className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-all"
              >
                انصراف
              </button>

              <button
                type="button"
                onClick={() => handleAiRefine()}
                disabled={refining || !aiPrompt.trim()}
                className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-lg shadow-purple-600/30 transition-all disabled:opacity-50"
              >
                {refining ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin text-purple-200" />
                    <span>در حال ارتقای هوشمند مقاله...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 text-purple-200" />
                    <span>اعمال و ارتقای مقاله</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      <VersionHistoryPanel
        articleId={articleId}
        isOpen={showHistory}
        onClose={() => setShowHistory(false)}
        onRollbackComplete={() => {
          setShowHistory(false);
          fetchArticle();
        }}
      />
    </div>
  );
}
