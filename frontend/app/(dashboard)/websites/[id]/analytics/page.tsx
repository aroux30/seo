"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api-client";
import {
  BarChart2,
  TrendingUp,
  MousePointerClick,
  Eye,
  Award,
  RefreshCw,
  Search,
  FileText,
  Plug,
  Calendar,
  Filter,
  Globe,
  Monitor,
  ArrowUpDown,
  SlidersHorizontal,
} from "lucide-react";
import Link from "next/link";

export default function WebsiteAnalyticsPage() {
  const params = useParams();
  const websiteId = params.id as string;

  const [overview, setOverview] = useState<any>(null);
  const [queries, setQueries] = useState<any[]>([]);
  const [pages, setPages] = useState<any[]>([]);
  const [countries, setCountries] = useState<any[]>([]);
  const [devices, setDevices] = useState<any[]>([]);
  const [dates, setDates] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [activeTab, setActiveTab] = useState<"queries" | "pages" | "countries" | "devices" | "dates">("queries");
  
  // Filters
  const [dateRange, setDateRange] = useState<string>("28d");
  const [searchType, setSearchType] = useState<string>("web");
  const [sortBy, setSortBy] = useState<string>("clicks");
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  // Labels for sync status messages, keyed by the API search type.
  const SEARCH_TYPE_FA: Record<string, string> = {
    web: "وب (Web)",
    image: "تصاویر (Image)",
    video: "ویدیو (Video)",
    news: "اخبار (News)",
    discover: "کشف (Discover)",
    googleNews: "اخبار گوگل (Google News)",
    generative_ai: "هوش مصنوعی تولیدی (Generative AI)",
  };

  const getDaysFromRange = (range: string) => {
    switch(range) {
      case "24h": return 1;
      case "7d": return 7;
      case "28d": return 28;
      case "3m": return 90;
      case "6m": return 180;
      case "12m": return 365;
      case "16m": return 480;
      default: return 28;
    }
  };

  const formatCtr = (val: any) => {
    if (val === null || val === undefined || isNaN(Number(val))) return "0%";
    const num = Number(val);
    const pct = num > 0 && num <= 1 ? num * 100 : num;
    return `${pct.toFixed(1)}%`;
  };

  const formatPosition = (val: any) => {
    if (val === null || val === undefined || isNaN(Number(val))) return "0";
    return Number(val).toFixed(1);
  };

  useEffect(() => {
    loadData();
  }, [websiteId, sortBy]);

  const loadData = async (overrideDays?: number, overrideType?: string) => {
    setLoading(true);
    const currentDays = overrideDays ?? getDaysFromRange(dateRange);
    const currentType = overrideType ?? searchType;
    try {
      const typeParam = `&search_type=${currentType}`;
      const [ov, qs, ps, cs, ds, dts] = await Promise.all([
        api.get(`/analytics/gsc/overview/${websiteId}?days=${currentDays}${typeParam}`),
        api.get(`/analytics/gsc/queries/${websiteId}?sort_by=${sortBy}&limit=100${typeParam}`),
        api.get(`/analytics/gsc/pages/${websiteId}?sort_by=${sortBy}&limit=100${typeParam}`),
        api.get(`/analytics/gsc/countries/${websiteId}?sort_by=${sortBy}&limit=100${typeParam}`),
        api.get(`/analytics/gsc/devices/${websiteId}?sort_by=${sortBy}&limit=100${typeParam}`),
        api.get(`/analytics/gsc/dates/${websiteId}?days=${currentDays}&sort_by=${sortBy === "date" ? "date" : sortBy}&limit=365${typeParam}`),
      ]);
      setOverview(ov || { total_clicks: 0, total_impressions: 0, avg_ctr: 0, avg_position: 0 });
      setQueries(qs || []);
      setPages(ps || []);
      setCountries(cs || []);
      setDevices(ds || []);
      setDates(dts || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = async (newDateRange: string, newSearchType: string) => {
    setDateRange(newDateRange);
    setSearchType(newSearchType);

    const days = getDaysFromRange(newDateRange);

    setSyncing(true);
    setSyncMessage(null);
    api.clearCache();
    try {
      const res: any = await api.post(`/integrations/gsc/sync/${websiteId}?days=${days}&search_type=${newSearchType}`);
      const info = res?.data || res;
      const qCount = info?.queries_added ?? 0;
      const pCount = info?.pages_added ?? 0;
      const dtCount = info?.dates_added ?? 0;
      if (qCount === 0 && pCount === 0 && dtCount === 0 && newSearchType !== "web") {
        const typeFa = SEARCH_TYPE_FA[newSearchType] || newSearchType;
        const extra = newSearchType === "generative_ai"
          ? " گزارش «هوش مصنوعی تولیدی» گوگل تازه معرفی شده و هنوز برای همه سایت‌ها از طریق API در دسترس نیست؛ وقتی گوگل داده این گزارش را برای دامنه شما منتشر کند، همین‌جا نمایش داده می‌شود."
          : " اگر مطمئن هستید سرچ کنسول برای این نوع جستجو داده دارد، چند دقیقه بعد دوباره همگام‌سازی کنید.";
        setSyncMessage(`برای نوع جستجوی «${typeFa}» هیچ داده‌ای در گوگل سرچ کنسول یافت نشد.${extra}`);
      } else {
        setSyncMessage(`داده‌های «${SEARCH_TYPE_FA[newSearchType] || newSearchType}» برای بازه انتخابی همگام‌سازی شد (${qCount} کلمه کلیدی، ${pCount} صفحه، ${dtCount} روز).`);
      }
      api.clearCache();
      await loadData(days, newSearchType);
    } catch (err: any) {
      setSyncMessage(err?.message || "خطا در اعمال فیلترها. لطفاً اتصال اکانت را بررسی کنید.");
    } finally {
      setSyncing(false);
    }
  };

  const handleManualSync = async () => {
    setSyncing(true);
    setSyncMessage(null);
    api.clearCache();
    const days = getDaysFromRange(dateRange);
    try {
      const res: any = await api.post(`/integrations/gsc/sync/${websiteId}?days=${days}&search_type=${searchType}`);
      const info = res?.data || res;
      const qCount = info?.queries_added ?? 0;
      const pCount = info?.pages_added ?? 0;
      const dtCount = info?.dates_added ?? 0;
      if (qCount === 0 && pCount === 0 && dtCount === 0 && searchType !== "web") {
        const typeFa = SEARCH_TYPE_FA[searchType] || searchType;
        const extra = searchType === "generative_ai"
          ? " گزارش «هوش مصنوعی تولیدی» گوگل تازه معرفی شده و هنوز برای همه سایت‌ها از طریق API در دسترس نیست؛ وقتی گوگل داده این گزارش را برای دامنه شما منتشر کند، همین‌جا نمایش داده می‌شود."
          : " اگر مطمئن هستید سرچ کنسول برای این نوع جستجو داده دارد، چند دقیقه بعد دوباره تلاش کنید.";
        setSyncMessage(`همگام‌سازی انجام شد، اما برای نوع جستجوی «${typeFa}» هیچ رکوردی در سرچ کنسول وجود ندارد.${extra}`);
      } else {
        setSyncMessage(`داده‌های سرچ کنسول با موفقیت دریافت و همگام‌سازی شد (${qCount} کلمه کلیدی، ${pCount} صفحه، ${dtCount} روز).`);
      }
      api.clearCache();
      await loadData(days);
    } catch (err: any) {
      setSyncMessage(err?.message || "خطا در همگام‌سازی داده‌های سرچ کنسول. لطفاً اتصال اکانت را بررسی کنید.");
    } finally {
      setSyncing(false);
    }
  };

  // Search filtering
  const filteredQueries = queries.filter((q) =>
    q.query?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredPages = pages.filter((p) =>
    p.page_url?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  

  const COUNTRY_MAP: Record<string, string> = {
    "IRN": "ایران", "DEU": "آلمان", "AFG": "افغانستان", "USA": "ایالات متحده",
    "TUR": "ترکیه", "NLD": "هلند", "ARE": "امارات متحده عربی", "IRQ": "عراق",
    "GBR": "بریتانیا", "FRA": "فرانسه", "AZE": "جمهوری آذربایجان", "BEL": "بلژیک",
    "ROU": "رومانی", "RUS": "روسیه", "SAU": "عربستان سعودی", "SWE": "سوئد",
    "SYR": "سوریه", "VNM": "ویتنام", "CAN": "کانادا", "AUS": "استرالیا"
  };

  const getCountryName = (code: string) => {
    return COUNTRY_MAP[code.toUpperCase()] || code;
  };

  return (
    <div className="space-y-6">
      {/* Top action bar */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <BarChart2 className="h-6 w-6 text-primary" />
            تحلیل عملکرد گوگل سرچ کنسول (Search Console Analytics)
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            بررسی دقیق کلیک‌ها، ایمپرشن‌ها، CTR و رتبه میانگین کلمات کلیدی، صفحات، کشورها و دستگاه‌ها
          </p>
        </div>

        <button
          onClick={handleManualSync}
          disabled={syncing}
          className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-primary to-blue-600 px-5 py-2.5 text-xs font-bold text-white shadow-lg shadow-primary/20 hover:from-primary/90 hover:to-blue-700 disabled:opacity-50 transition"
        >
          <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} />
          <span>{syncing ? "در حال استخراج داده از گوگل..." : "همگام‌سازی مستقیم با سرچ کنسول"}</span>
        </button>
      </div>

      {syncMessage && (
        <div className="rounded-xl border border-primary/30 bg-primary/10 p-4 text-xs font-medium text-white shadow-md">
          {syncMessage}
        </div>
      )}

      {/* Filter Bar (Date Range, Search Type, Sort) */}
      <div className="rounded-2xl border border-white/10 bg-card/70 p-4 backdrop-blur-md flex flex-wrap items-center justify-between gap-4">
        {/* Left side: Date & Search Type filters */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Date range picker */}
          <div className="flex items-center gap-2 rounded-xl bg-white/5 border border-white/10 px-3 py-1.5 text-xs">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground font-medium">بازه زمانی:</span>
            <select
              value={dateRange}
              onChange={(e) => handleFilterChange(e.target.value, searchType)}
              className="bg-transparent font-semibold text-white focus:outline-none cursor-pointer"
            >
              <option value="24h" className="bg-card text-white">۲۴ ساعت گذشته</option>
              <option value="7d" className="bg-card text-white">۷ روز گذشته</option>
              <option value="28d" className="bg-card text-white">۲۸ روز گذشته (پیش‌فرض)</option>
              <option value="3m" className="bg-card text-white">۳ ماه گذشته</option>
              <option value="6m" className="bg-card text-white">۶ ماه گذشته</option>
              <option value="12m" className="bg-card text-white">۱۲ ماه گذشته</option>
              <option value="16m" className="bg-card text-white">۱۶ ماه گذشته</option>
            </select>
          </div>

          {/* Search Type picker */}
          <div className="flex items-center gap-2 rounded-xl bg-white/5 border border-white/10 px-3 py-1.5 text-xs">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground font-medium">نوع جستجو:</span>
            <select
              value={searchType}
              onChange={(e) => handleFilterChange(dateRange, e.target.value)}
              className="bg-transparent font-semibold text-white focus:outline-none cursor-pointer"
            >
              <option value="web" className="bg-card text-white">وب (Web)</option>
              <option value="image" className="bg-card text-white">تصاویر (Image)</option>
              <option value="video" className="bg-card text-white">ویدیو (Video)</option>
              <option value="news" className="bg-card text-white">اخبار (News)</option>
              <option value="discover" className="bg-card text-white">کشف (Discover)</option>
              <option value="googleNews" className="bg-card text-white">اخبار گوگل (Google News)</option>
              <option value="generative_ai" className="bg-card text-white">هوش مصنوعی تولیدی (Generative AI)</option>
            </select>
          </div>
        </div>

        {/* Right side: Sort Selector */}
        <div className="flex items-center gap-2 rounded-xl bg-white/5 border border-white/10 px-3 py-1.5 text-xs">
          <ArrowUpDown className="h-4 w-4 text-muted-foreground" />
          <span className="text-muted-foreground font-medium">مرتب‌سازی بر اساس:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-transparent font-semibold text-white focus:outline-none cursor-pointer"
          >
            <option value="clicks" className="bg-card text-white">تعداد کلیک (Clicks)</option>
            <option value="impressions" className="bg-card text-white">تعداد نمایش (Impressions)</option>
            <option value="ctr" className="bg-card text-white">نرخ کلیک (CTR)</option>
            <option value="position" className="bg-card text-white">بهترین رتبه (Position)</option>
          </select>
        </div>
      </div>

      {/* 4 Stats Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md transition hover:border-blue-500/30">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">کل کلیک‌ها (Total Clicks)</span>
            <div className="rounded-xl bg-blue-500/10 p-2 text-blue-400">
              <MousePointerClick className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-black text-white">
            {overview ? overview.total_clicks.toLocaleString() : "---"}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md transition hover:border-purple-500/30">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">کل نمایش‌ها (Total Impressions)</span>
            <div className="rounded-xl bg-purple-500/10 p-2 text-purple-400">
              <Eye className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-black text-white">
            {overview ? overview.total_impressions.toLocaleString() : "---"}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md transition hover:border-emerald-500/30">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">نرخ کلیک میانگین (Average CTR)</span>
            <div className="rounded-xl bg-emerald-500/10 p-2 text-emerald-400">
              <TrendingUp className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-black text-white">
            {overview ? `${overview.avg_ctr}%` : "---"}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/60 p-5 backdrop-blur-md transition hover:border-amber-500/30">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">رتبه میانگین (Average Position)</span>
            <div className="rounded-xl bg-amber-500/10 p-2 text-amber-400">
              <Award className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-black text-white">
            {overview ? overview.avg_position : "---"}
          </div>
        </div>
      </div>

      {/* Main Table Section with 5 GSC Tabs */}
      <div className="rounded-2xl border border-white/10 bg-card/60 p-6 shadow-xl backdrop-blur-md">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-white/10 pb-4">
          {/* Tabs */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setActiveTab("queries")}
              className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition ${
                activeTab === "queries"
                  ? "bg-primary text-white shadow-lg shadow-primary/20"
                  : "text-muted-foreground hover:bg-white/5 hover:text-white"
              }`}
            >
              <Search className="h-4 w-4" />
              <span>کلمات کلیدی (Queries) - {queries.length}</span>
            </button>

            <button
              onClick={() => setActiveTab("pages")}
              className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition ${
                activeTab === "pages"
                  ? "bg-primary text-white shadow-lg shadow-primary/20"
                  : "text-muted-foreground hover:bg-white/5 hover:text-white"
              }`}
            >
              <FileText className="h-4 w-4" />
              <span>صفحات (Pages) - {pages.length}</span>
            </button>

            <button
              onClick={() => setActiveTab("countries")}
              className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition ${
                activeTab === "countries"
                  ? "bg-primary text-white shadow-lg shadow-primary/20"
                  : "text-muted-foreground hover:bg-white/5 hover:text-white"
              }`}
            >
              <Globe className="h-4 w-4" />
              <span>کشورها (Countries) - {countries.length}</span>
            </button>

            <button
              onClick={() => setActiveTab("devices")}
              className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition ${
                activeTab === "devices"
                  ? "bg-primary text-white shadow-lg shadow-primary/20"
                  : "text-muted-foreground hover:bg-white/5 hover:text-white"
              }`}
            >
              <Monitor className="h-4 w-4" />
              <span>دستگاه‌ها (Devices) - {devices.length}</span>
            </button>

            <button
              onClick={() => setActiveTab("dates")}
              className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition ${
                activeTab === "dates"
                  ? "bg-primary text-white shadow-lg shadow-primary/20"
                  : "text-muted-foreground hover:bg-white/5 hover:text-white"
              }`}
            >
              <Calendar className="h-4 w-4" />
              <span>روزها (Days) - {dates.length}</span>
            </button>
          </div>

          {/* Search Filter Input */}
          <div className="relative w-full sm:w-64">
            <Search className="absolute right-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="جستجو در نتایج..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-white/5 py-2 pr-9 pl-4 text-xs text-white placeholder-muted-foreground focus:border-primary focus:outline-none"
            />
          </div>
        </div>

        {loading ? (
          <div className="py-12 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
            <RefreshCw className="h-4 w-4 animate-spin text-primary" />
            در حال بارگذاری داده‌های واقعی گوگل سرچ کنسول...
          </div>
        ) : activeTab === "queries" ? (
          filteredQueries.length === 0 ? (
            <div className="py-16 text-center text-xs text-muted-foreground flex flex-col items-center gap-4">
              <Search className="h-10 w-10 text-muted-foreground/30" />
              <p>داده‌ای برای کلمات کلیدی یافت نشد.</p>
              <p className="max-w-md opacity-80">
                اگر حساب گوگل سرچ کنسول را متصل نکرده‌اید، ابتدا از بخش <strong>اتصالات</strong> آن را فعال کنید، سپس روی دکمه «همگام‌سازی مستمر» کلیک کنید.
              </p>
              <Link
                href={`/websites/${websiteId}/integrations`}
                className="mt-2 flex items-center gap-2 rounded-xl bg-primary/20 px-4 py-2 font-semibold text-primary transition hover:bg-primary/30"
              >
                <Plug className="h-4 w-4" />
                رفتن به صفحه اتصالات و اتصال سرچ کنسول
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-white/10 text-muted-foreground">
                  <tr>
                    <th className="pb-3 text-right">کلمه کلیدی (Query)</th>
                    <th className="pb-3 text-right cursor-pointer hover:text-white" onClick={() => setSortBy("clicks")}>کلیک‌ها (Clicks) ↕</th>
                    <th className="pb-3 text-right cursor-pointer hover:text-white" onClick={() => setSortBy("impressions")}>نمایش‌ها (Impressions) ↕</th>
                    <th className="pb-3 text-right cursor-pointer hover:text-white" onClick={() => setSortBy("ctr")}>نرخ کلیک (CTR) ↕</th>
                    <th className="pb-3 text-right cursor-pointer hover:text-white" onClick={() => setSortBy("position")}>رتبه میانگین (Position) ↕</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {filteredQueries.map((q) => (
                    <tr key={q.id || q.query} className="transition hover:bg-white/5">
                      <td className="py-3.5 text-right font-bold text-white">
                        {q.query}
                      </td>
                      <td className="py-3.5 text-right font-bold text-emerald-400">
                        {q.clicks.toLocaleString()}
                      </td>
                      <td className="py-3.5 text-right text-white">
                        {q.impressions.toLocaleString()}
                      </td>
                      <td className="py-3.5 text-right text-muted-foreground font-semibold">
                        {formatCtr(q.ctr)}
                      </td>
                      <td className="py-3.5 text-right">
                        <span className="rounded-full bg-amber-500/15 px-2.5 py-1 font-bold text-amber-400">
                          {formatPosition(q.position)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : activeTab === "pages" ? (
          filteredPages.length === 0 ? (
            <div className="py-16 text-center text-xs text-muted-foreground flex flex-col items-center gap-4">
              <FileText className="h-10 w-10 text-muted-foreground/30" />
              <p>داده‌ای برای صفحات یافت نشد.</p>
              <Link
                href={`/websites/${websiteId}/integrations`}
                className="mt-2 flex items-center gap-2 rounded-xl bg-primary/20 px-4 py-2 font-semibold text-primary transition hover:bg-primary/30"
              >
                <Plug className="h-4 w-4" />
                رفتن به صفحه اتصالات
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-white/10 text-muted-foreground">
                  <tr>
                    <th className="pb-3 text-right">آدرس صفحه (URL)</th>
                    <th className="pb-3 text-right cursor-pointer hover:text-white" onClick={() => setSortBy("clicks")}>کلیک‌ها ↕</th>
                    <th className="pb-3 text-right cursor-pointer hover:text-white" onClick={() => setSortBy("impressions")}>نمایش‌ها ↕</th>
                    <th className="pb-3 text-right cursor-pointer hover:text-white" onClick={() => setSortBy("ctr")}>نرخ کلیک ↕</th>
                    <th className="pb-3 text-right cursor-pointer hover:text-white" onClick={() => setSortBy("position")}>رتبه میانگین ↕</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {filteredPages.map((p) => (
                    <tr key={p.id || p.page_url} className="transition hover:bg-white/5">
                      <td className="py-3.5 text-right font-medium text-blue-400" dir="ltr">
                        <a href={p.page_url} target="_blank" rel="noreferrer" className="hover:underline">
                          {p.page_url}
                        </a>
                      </td>
                      <td className="py-3.5 text-right font-bold text-emerald-400">
                        {p.clicks.toLocaleString()}
                      </td>
                      <td className="py-3.5 text-right text-white">
                        {p.impressions.toLocaleString()}
                      </td>
                      <td className="py-3.5 text-right text-muted-foreground font-semibold">
                        {formatCtr(p.ctr)}
                      </td>
                      <td className="py-3.5 text-right">
                        <span className="rounded-full bg-amber-500/15 px-2.5 py-1 font-bold text-amber-400">
                          {formatPosition(p.position)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : activeTab === "countries" ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-white/10 text-muted-foreground">
                <tr>
                  <th className="pb-3 text-right">کشور (Country)</th>
                  <th className="pb-3 text-right">کلیک‌ها</th>
                  <th className="pb-3 text-right">نمایش‌ها</th>
                  <th className="pb-3 text-right">نرخ کلیک</th>
                  <th className="pb-3 text-right">رتبه میانگین</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {countries.map((c) => (
                  <tr key={c.country} className="transition hover:bg-white/5">
                    <td className="py-3.5 text-right font-bold text-white">{getCountryName(c.country)}</td>
                    <td className="py-3.5 text-right font-bold text-emerald-400">{c.clicks.toLocaleString()}</td>
                    <td className="py-3.5 text-right text-white">{c.impressions.toLocaleString()}</td>
                    <td className="py-3.5 text-right text-muted-foreground">{formatCtr(c.ctr)}</td>
                    <td className="py-3.5 text-right">
                      <span className="rounded-full bg-amber-500/15 px-2.5 py-1 font-bold text-amber-400">{formatPosition(c.position)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : activeTab === "devices" ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-white/10 text-muted-foreground">
                <tr>
                  <th className="pb-3 text-right">دستگاه (Device)</th>
                  <th className="pb-3 text-right">کلیک‌ها</th>
                  <th className="pb-3 text-right">نمایش‌ها</th>
                  <th className="pb-3 text-right">نرخ کلیک</th>
                  <th className="pb-3 text-right">رتبه میانگین</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {devices.map((d) => (
                  <tr key={d.device} className="transition hover:bg-white/5">
                    <td className="py-3.5 text-right font-bold text-white">{d.device}</td>
                    <td className="py-3.5 text-right font-bold text-emerald-400">{d.clicks.toLocaleString()}</td>
                    <td className="py-3.5 text-right text-white">{d.impressions.toLocaleString()}</td>
                    <td className="py-3.5 text-right text-muted-foreground">{formatCtr(d.ctr)}</td>
                    <td className="py-3.5 text-right">
                      <span className="rounded-full bg-amber-500/15 px-2.5 py-1 font-bold text-amber-400">{formatPosition(d.position)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-white/10 text-muted-foreground">
                <tr>
                  <th className="pb-3 text-right cursor-pointer hover:text-white" onClick={() => setSortBy("date")}>روز (Date) ↕</th>
                  <th className="pb-3 text-right cursor-pointer hover:text-white" onClick={() => setSortBy("clicks")}>کلیک‌ها ↕</th>
                  <th className="pb-3 text-right cursor-pointer hover:text-white" onClick={() => setSortBy("impressions")}>نمایش‌ها ↕</th>
                  <th className="pb-3 text-right cursor-pointer hover:text-white" onClick={() => setSortBy("ctr")}>نرخ کلیک ↕</th>
                  <th className="pb-3 text-right cursor-pointer hover:text-white" onClick={() => setSortBy("position")}>رتبه میانگین ↕</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {dates.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-xs text-muted-foreground">
                      داده‌ای برای روزها در این بازه زمانی یافت نشد. برای دریافت داده‌های تازه، روی دکمه «همگام‌سازی مستقیم با سرچ کنسول» کلیک کنید.
                    </td>
                  </tr>
                ) : (
                  dates.map((d) => (
                    <tr key={d.id || d.date_metric} className="transition hover:bg-white/5">
                      <td className="py-3.5 text-right font-bold text-white" dir="ltr">
                        {d.date_metric} ({new Date(d.date_metric).toLocaleDateString('fa-IR')})
                      </td>
                      <td className="py-3.5 text-right font-bold text-emerald-400">{d.clicks.toLocaleString()}</td>
                      <td className="py-3.5 text-right text-white">{d.impressions.toLocaleString()}</td>
                      <td className="py-3.5 text-right text-muted-foreground">{formatCtr(d.ctr)}</td>
                      <td className="py-3.5 text-right">
                        <span className="rounded-full bg-amber-500/15 px-2.5 py-1 font-bold text-amber-400">{formatPosition(d.position)}</span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
